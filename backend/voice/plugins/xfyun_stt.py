"""XfyunSTTPlugin — LiveKit STT plugin wrapping vendored XfyunASR.

Demo-phase: batch (non-streaming) recognition only.
AudioBuffer is serialised to a temporary PCM file, passed to XfyunASR.recognize(),
then the file is cleaned up regardless of success or failure (OQ-3).

Sync→async bridge: XfyunASR.recognize() is blocking; we dispatch it to a thread
pool via asyncio.to_thread() so the event loop is never stalled (OQ-11).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import time
from contextvars import ContextVar

from livekit.agents import APIConnectionError
from livekit.agents.stt import (
    STT,
    STTCapabilities,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
)
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.agents.utils import AudioBuffer
from livekit.agents.utils.audio import combine_frames

from backend.voice._vendor.psy.stt.speech_to_text_xfyun_service import XfyunASR

logger = logging.getLogger("voice.plugins.xfyun_stt")

_DEFAULT_LANGUAGE = "zh-cn"
_DEFAULT_SAMPLE_RATE = 16_000

voice_session_ctx: ContextVar[str | None] = ContextVar(
    "voice_session_ctx", default=None
)
voice_turn_ctx: ContextVar[str | None] = ContextVar("voice_turn_ctx", default=None)


# ---------------------------------------------------------------------------
# Exception hierarchy (per F1 §4.1 / §6)
# ---------------------------------------------------------------------------


class XfyunSTTError(Exception):
    """Base class for all Xfyun STT plugin errors."""

    def __init__(self, message: str = "", *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.xfyun_message = message


class XfyunSTTNetworkError(XfyunSTTError):
    """WebSocket connection to Xfyun failed, dropped, or timed out."""


class XfyunSTTAuthError(XfyunSTTError):
    """Xfyun rejected the request due to invalid credentials."""


class XfyunSTTTimeoutError(XfyunSTTError):
    """Recognition exceeded the 60-second hard timeout."""


class XfyunSTTRateLimitError(XfyunSTTError):
    """Xfyun rejected the request due to rate limiting or quota pressure."""


class XfyunRecognitionError(XfyunSTTError):
    """Xfyun returned a recognition-domain non-zero error code."""


class XfyunVendorError(XfyunSTTError):
    """Vendored XfyunASR surfaced a non-zero response code."""


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class XfyunSTTPlugin(STT):
    """LiveKit ``STT`` subclass wrapping the vendored ``XfyunASR`` service.

    Capabilities: offline batch recognition only (no streaming, no interim
    results).  A fresh ``XfyunASR`` instance is constructed once at plugin
    init; individual recognize calls share it (the underlying service is
    stateless per call).

    Args:
        app_id: Xfyun application ID.  Falls back to ``XFYUN_APPID`` env var.
        api_key: Xfyun API key.  Falls back to ``XFYUN_API_KEY`` env var.
        api_secret: Xfyun API secret.  Falls back to ``XFYUN_API_SECRET`` env var.
        language: BCP-47 language tag returned in ``SpeechData``.  Defaults to
            ``"zh-cn"`` (the only dialect supported by ``XfyunASR``).
        sample_rate: Sample rate of incoming PCM audio in Hz.  Defaults to 16 000.

    Note:
        Credentials are read from environment variables lazily by ``XfyunASR``
        itself; passing them here allows test injection without env mutation.
    """

    def __init__(
        self,
        *,
        app_id: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        language: str = _DEFAULT_LANGUAGE,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
    ) -> None:
        super().__init__(
            capabilities=STTCapabilities(
                streaming=False,
                interim_results=False,
                offline_recognize=True,
            )
        )
        # Allow test injection by setting env vars before constructing XfyunASR.
        if app_id is not None:
            os.environ["XFYUN_APP_ID"] = app_id
        if api_key is not None:
            os.environ["XFYUN_API_KEY"] = api_key
        if api_secret is not None:
            os.environ["XFYUN_API_SECRET"] = api_secret

        self._asr = XfyunASR()
        self._language = language
        self._sample_rate = sample_rate

    @property
    def model(self) -> str:
        """Return the Xfyun model identifier."""
        return "xfyun-slm"

    @property
    def provider(self) -> str:
        """Return the provider name."""
        return "xfyun"

    # ------------------------------------------------------------------
    # Core implementation
    # ------------------------------------------------------------------

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> SpeechEvent:
        """Persist ``AudioBuffer`` PCM to a temp file, call ``XfyunASR.recognize()``.

        The temp file is always removed in a ``finally`` block so no PCM
        fragments are left on disk after the call completes (success or error).

        Args:
            buffer: Accumulated ``rtc.AudioFrame`` list from the LiveKit room.
            language: Optional language hint (ignored — plugin hard-codes zh-cn).
            conn_options: Connection / retry options supplied by the base class.

        Returns:
            ``SpeechEvent`` with ``type=FINAL_TRANSCRIPT``.  ``alternatives[0].text``
            is the recognised string (may be empty if Xfyun returned nothing).

        Raises:
            XfyunSTTNetworkError: If the underlying WebSocket call fails due to a
                network or connection error.
            XfyunSTTAuthError: If Xfyun rejects the request due to invalid
                credentials (auth-related error strings detected in exception message).
            XfyunSTTTimeoutError: If ``XfyunASR.recognize()`` blocks longer than
                ``conn_options.timeout`` seconds (falls back to 60 s hard limit).
            APIConnectionError: Re-raised from ``XfyunSTTNetworkError`` so that the
                LiveKit base class retry logic triggers correctly.
        """
        session_id = voice_session_ctx.get()
        turn_id = voice_turn_ctx.get()

        # Measure audio duration for logging.
        combined = combine_frames(buffer) if isinstance(buffer, list) else buffer
        pcm_bytes = bytes(combined.data)
        audio_duration_s = len(pcm_bytes) / 2 / self._sample_rate  # 16-bit mono

        logger.info(
            "xfyun_stt_recognize_start",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "audio_duration_s": round(audio_duration_s, 3),
            },
        )

        t_start = time.monotonic()
        tmp_path: str | None = None

        try:
            # Write PCM to a temporary file; XfyunASR.recognize() needs a path.
            with tempfile.NamedTemporaryFile(
                suffix=".pcm", delete=False
            ) as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(pcm_bytes)

            # Run the blocking call in a thread pool (OQ-11).
            result_text: str = await asyncio.to_thread(
                self._recognize_with_vendor_errors, tmp_path
            )

        except Exception as exc:
            latency_ms = round((time.monotonic() - t_start) * 1000)
            code = _extract_xfyun_code(exc)
            message = _extract_xfyun_message(exc)
            error_cls = _classify_xfyun_error(code, message)
            if isinstance(exc, XfyunRecognitionError) and code in (None, 0):
                error_cls = XfyunRecognitionError

            if code not in (None, 0):
                logger.error(
                    "xfyun_stt_xfyun_error",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "code": code,
                        "xfyun_message": message,
                        "latency_ms": latency_ms,
                    },
                    exc_info=True,
                )

            if error_cls is XfyunRecognitionError:
                result_text = ""

            elif error_cls is XfyunSTTAuthError:
                logger.error(
                    "xfyun_stt_auth_error",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "error": message,
                        "latency_ms": latency_ms,
                    },
                    exc_info=True,
                )
                raise XfyunSTTAuthError(message, code=code) from exc

            elif error_cls is XfyunSTTTimeoutError:
                logger.error(
                    "xfyun_stt_timeout",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "error": message,
                        "latency_ms": latency_ms,
                    },
                    exc_info=True,
                )
                raise XfyunSTTTimeoutError(message, code=code) from exc

            elif error_cls is XfyunSTTRateLimitError:
                logger.error(
                    "xfyun_stt_rate_limited",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "error": message,
                        "latency_ms": latency_ms,
                    },
                    exc_info=True,
                )
                raise XfyunSTTRateLimitError(message, code=code) from exc

            else:
                # Default: treat as network / connection error.
                logger.error(
                    "xfyun_stt_network_error",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "error": message,
                        "latency_ms": latency_ms,
                    },
                    exc_info=True,
                )
                network_err = XfyunSTTNetworkError(message, code=code)
                # Re-raise as APIConnectionError so the LiveKit retry loop fires.
                raise APIConnectionError(message) from network_err

        finally:
            # Always clean up the temp file (OQ-3).
            if tmp_path is not None and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        latency_ms = round((time.monotonic() - t_start) * 1000)

        if not result_text:
            logger.warning(
                "xfyun_stt_empty_result",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                },
            )
        else:
            logger.info(
                "xfyun_stt_recognize_done",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "text_len": len(result_text),
                    "latency_ms": latency_ms,
                },
            )

        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                SpeechData(
                    language=self._language,
                    text=result_text,
                    confidence=1.0 if result_text else 0.0,
                )
            ],
        )

    async def aclose(self) -> None:
        """No persistent connections to close (stateless per-recognize)."""

    def _recognize_with_vendor_errors(self, tmp_path: str) -> str:
        """Call vendored recognizer and recover its swallowed non-zero code."""
        vendor_logger = logging.getLogger(
            "backend.voice._vendor.psy.stt.speech_to_text_xfyun_service"
        )
        handler = _XfyunErrorCaptureHandler()
        vendor_logger.addHandler(handler)
        try:
            result = self._asr.recognize(tmp_path)
        finally:
            vendor_logger.removeHandler(handler)

        if result == "" and handler.error is not None:
            raise handler.error
        return result


# ---------------------------------------------------------------------------
# Error-classification helpers
# ---------------------------------------------------------------------------


_VENDOR_ERROR_RE = re.compile(r"code=(?P<code>-?\d+), message=(?P<message>.*)")
_AUTH_ERROR_CODES = {10105, 10106, 10107, 10110, 11200}
_RATE_LIMIT_ERROR_CODES = {10114, 10162}
_TIMEOUT_ERROR_CODES = {10165}


class _XfyunErrorCaptureHandler(logging.Handler):
    """Capture Xfyun header.code from the vendored logger without editing vendor."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.error: XfyunVendorError | None = None

    def emit(self, record: logging.LogRecord) -> None:
        match = _VENDOR_ERROR_RE.search(record.getMessage())
        if match is None:
            return

        code = int(match.group("code"))
        message = match.group("message").strip()
        self.error = XfyunVendorError(message, code=code)


def _classify_xfyun_error(
    code: int | None, message: str
) -> type[XfyunSTTError]:
    """Map Xfyun response codes to stable plugin exception classes."""
    if code not in (None, 0):
        if code in _AUTH_ERROR_CODES:
            return XfyunSTTAuthError
        if code in _RATE_LIMIT_ERROR_CODES:
            return XfyunSTTRateLimitError
        if code in _TIMEOUT_ERROR_CODES:
            return XfyunSTTTimeoutError
        if 10800 <= code <= 10899:
            return XfyunRecognitionError
        return XfyunSTTNetworkError

    # Fallback for exceptions that do not carry Xfyun header.code.
    # Prefer the official code map above; see https://www.xfyun.cn/document/error-code.
    msg = message.lower()
    auth_keywords = (
        "auth",
        "401",
        "403",
        "forbidden",
        "unauthorized",
        "invalid key",
        "api_key",
        "api key",
        "secret",
    )
    if any(kw in msg for kw in auth_keywords):
        return XfyunSTTAuthError

    timeout_keywords = ("timeout", "timed out", "time out", "deadline")
    if any(kw in msg for kw in timeout_keywords):
        return XfyunSTTTimeoutError

    return XfyunSTTNetworkError


def _extract_xfyun_code(exc: Exception) -> int | None:
    """Return an Xfyun error code from an exception when one is available."""
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


def _extract_xfyun_message(exc: Exception) -> str:
    """Return the Xfyun message payload or fall back to str(exc)."""
    message = getattr(exc, "xfyun_message", None)
    return message if isinstance(message, str) and message else str(exc)
