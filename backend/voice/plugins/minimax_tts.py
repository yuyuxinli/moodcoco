"""MinimaxTTSPlugin — LiveKit TTS plugin wrapping vendored MiniMaxTTSService.

Implements synthesize() (non-streaming chunked) via MiniMaxTTSService.synthesize_bytes().
The bytes returned by the vendor are MP3-encoded; AudioEmitter handles decoding via
the codecs pipeline (mime_type="audio/mp3").

Sync→async bridge: MiniMaxTTSService.synthesize_bytes() is an async method already;
we call it directly inside the ChunkedStream._run() coroutine running in the event loop.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any

import httpx

from livekit.agents.tts import TTS, TTSCapabilities, ChunkedStream, SynthesizedAudio
from livekit.agents.tts.tts import AudioEmitter
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions
from livekit.agents import APIConnectionError, APIStatusError, APITimeoutError

from backend.voice._vendor.psy.tts.service import MiniMaxTTSService
from backend.voice._vendor.psy.tts.types import MiniMaxAccountConfig
from backend.voice._vendor.psy.tts.router import MiniMaxAccountRouter, MiniMaxAccountState
from backend.voice._vendor.psy.tts.client import MiniMaxTTSClient

logger = logging.getLogger("voice.plugins.minimax_tts")

_DEFAULT_SAMPLE_RATE = 32_000
_DEFAULT_NUM_CHANNELS = 1
_DEFAULT_MODEL = "speech-01"
_DEFAULT_VOICE_ID = "female-shaonv"

# Chunk size for pushing audio bytes to the emitter (64 KB).
_CHUNK_SIZE = 64 * 1024


# ---------------------------------------------------------------------------
# Exception hierarchy (per F1 §4.2 / §6)
# ---------------------------------------------------------------------------


class MinimaxTTSError(Exception):
    """Base class for all MiniMax TTS plugin errors.

    Attributes:
        status_code: HTTP status code from the MiniMax API, if applicable.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MinimaxTTSAuthError(MinimaxTTSError):
    """MiniMax TTS request rejected due to invalid or missing API key (HTTP 401/403)."""


class MinimaxTTSRateLimitError(MinimaxTTSError):
    """MiniMax TTS API returned HTTP 429 — rate limit exceeded."""

    def __init__(self, message: str = "MiniMax TTS rate limit exceeded (429)") -> None:
        super().__init__(message, status_code=429)


class MinimaxTTSNetworkError(MinimaxTTSError):
    """Network-level failure when calling the MiniMax TTS API (timeout at HTTP layer excluded)."""


class MinimaxTTSTimeoutError(MinimaxTTSError):
    """MiniMax TTS HTTP call timed out before receiving a response."""


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class MinimaxTTSPlugin(TTS):
    """LiveKit ``TTS`` plugin wrapping the vendored ``MiniMaxTTSService``.

    Implements ``synthesize()`` (non-streaming / chunked) via
    ``MiniMaxTTSService.synthesize_bytes()``.  The result is pushed to the
    ``AudioEmitter`` in chunks of ``_CHUNK_SIZE`` bytes so that LiveKit's
    codecs pipeline can start decoding early.

    Args:
        api_key: MiniMax API key.  Falls back to ``MINIMAX_API_KEY`` env var.
        model: MiniMax TTS model name.  Falls back to ``MINIMAX_TTS_MODEL``
            env var; default ``"speech-01"``.
        voice_id: Voice ID.  Falls back to ``MINIMAX_TTS_VOICE_ID`` env var;
            default ``"female-shaonv"``.
        sample_rate: Output audio sample rate in Hz.  Default 32 000.
        _service: Optional pre-built ``MiniMaxTTSService`` for test injection.
            When provided, ``api_key`` / ``model`` / ``voice_id`` are ignored.

    Raises:
        ValueError: If ``api_key`` cannot be resolved (neither kwarg nor env var).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        voice_id: str | None = None,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        _service: MiniMaxTTSService | None = None,
    ) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=_DEFAULT_NUM_CHANNELS,
        )

        if _service is not None:
            self._service = _service
        else:
            resolved_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
            resolved_model = (
                model
                or os.environ.get("MINIMAX_TTS_MODEL", _DEFAULT_MODEL)
            )
            resolved_voice = (
                voice_id
                or os.environ.get("MINIMAX_TTS_VOICE_ID", _DEFAULT_VOICE_ID)
            )
            self._service = _build_service(
                api_key=resolved_key,
                model=resolved_model,
                voice_id=resolved_voice,
            )

        self._model_name = model or os.environ.get("MINIMAX_TTS_MODEL", _DEFAULT_MODEL)
        self._voice_id = voice_id or os.environ.get("MINIMAX_TTS_VOICE_ID", _DEFAULT_VOICE_ID)

    @property
    def model(self) -> str:
        """Return the MiniMax TTS model identifier."""
        return self._model_name

    @property
    def provider(self) -> str:
        """Return the provider name."""
        return "minimax"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        **kwargs: Any,
    ) -> "MinimaxChunkedStream":
        """Return a ``ChunkedStream`` that fetches audio from MiniMax TTS.

        Args:
            text: Text to synthesise.
            conn_options: Connection / retry options supplied by the base class.
            **kwargs: Accepts optional ``session_id`` and ``turn_id`` for
                structured logging.

        Returns:
            ``MinimaxChunkedStream`` instance (async-iterable of
            ``SynthesizedAudio``).

        Raises:
            MinimaxTTSError: propagated from ``_run()`` if the HTTP call fails.
        """
        session_id: str = kwargs.get("session_id", "")
        turn_id: str = kwargs.get("turn_id", uuid.uuid4().hex[:8])
        return MinimaxChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            session_id=session_id,
            turn_id=turn_id,
        )

    async def aclose(self) -> None:
        """Close underlying HTTP connections held by the vendor service."""
        await self._service.close()


# ---------------------------------------------------------------------------
# Chunked stream
# ---------------------------------------------------------------------------


class MinimaxChunkedStream(ChunkedStream):
    """``ChunkedStream`` implementation for ``MinimaxTTSPlugin``.

    Calls ``MiniMaxTTSService.synthesize_bytes()`` and pushes the resulting
    bytes to the ``AudioEmitter`` in ``_CHUNK_SIZE`` chunks.
    """

    def __init__(
        self,
        *,
        tts: MinimaxTTSPlugin,
        input_text: str,
        conn_options: APIConnectOptions,
        session_id: str = "",
        turn_id: str = "",
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._session_id = session_id or ""
        self._turn_id = turn_id or uuid.uuid4().hex[:8]

    async def _run(self, output_emitter: AudioEmitter) -> None:
        """Fetch audio from MiniMax TTS and push bytes to ``output_emitter``.

        Args:
            output_emitter: Provided by the base class ``_main_task``; used to
                emit ``SynthesizedAudio`` frames to downstream consumers.

        Raises:
            MinimaxTTSRateLimitError: HTTP 429 from the MiniMax API.
            MinimaxTTSAuthError: HTTP 401/403 from the MiniMax API.
            MinimaxTTSNetworkError: Network-level failure (``httpx.RequestError``).
            MinimaxTTSTimeoutError: HTTP call timed out (``httpx.TimeoutException``).
            MinimaxTTSError: Empty audio response or other MiniMax error.
            APIStatusError: Re-raised for LiveKit retry logic on 4xx/5xx.
        """
        session_id = self._session_id
        turn_id = self._turn_id
        text = self._input_text
        tts_plugin: MinimaxTTSPlugin = self._tts  # type: ignore[assignment]

        logger.info(
            "minimax_tts_synthesize_start",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "text_len": len(text),
                "voice_id": tts_plugin._voice_id,
            },
        )

        t_start = time.monotonic()

        try:
            audio_bytes, _meta = await tts_plugin._service.synthesize_bytes(text)
        except httpx.TimeoutException as exc:
            latency_ms = round((time.monotonic() - t_start) * 1000)
            logger.error(
                "minimax_tts_timeout",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                },
                exc_info=True,
            )
            raise MinimaxTTSTimeoutError(f"MiniMax TTS request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            latency_ms = round((time.monotonic() - t_start) * 1000)
            status_code = exc.response.status_code
            if status_code == 429:
                logger.error(
                    "minimax_tts_rate_limit",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "status_code": status_code,
                    },
                    exc_info=True,
                )
                raise MinimaxTTSRateLimitError() from exc
            if status_code in (401, 403):
                logger.error(
                    "minimax_tts_auth_error",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "status_code": status_code,
                    },
                    exc_info=True,
                )
                raise MinimaxTTSAuthError(
                    f"MiniMax TTS authentication failed (HTTP {status_code})",
                    status_code=status_code,
                ) from exc
            logger.error(
                "minimax_tts_http_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "status_code": status_code,
                },
                exc_info=True,
            )
            raise MinimaxTTSError(
                f"MiniMax TTS HTTP error {status_code}",
                status_code=status_code,
            ) from exc
        except httpx.RequestError as exc:
            latency_ms = round((time.monotonic() - t_start) * 1000)
            logger.error(
                "minimax_tts_network_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                    "error": str(exc),
                },
                exc_info=True,
            )
            raise MinimaxTTSNetworkError(f"MiniMax TTS network error: {exc}") from exc

        if not audio_bytes:
            logger.error(
                "minimax_tts_empty_audio",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                },
            )
            raise MinimaxTTSError("MiniMax TTS returned empty audio response")

        latency_ms = round((time.monotonic() - t_start) * 1000)
        logger.info(
            "minimax_tts_synthesize_done",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "audio_bytes": len(audio_bytes),
                "latency_ms": latency_ms,
            },
        )

        # Initialize the emitter — vendor returns MP3 bytes.
        request_id = uuid.uuid4().hex
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._tts.sample_rate,
            num_channels=self._tts.num_channels,
            mime_type="audio/mp3",
            stream=False,
        )

        # Push audio in chunks so the codec pipeline can start early.
        offset = 0
        total = len(audio_bytes)
        while offset < total:
            chunk = audio_bytes[offset : offset + _CHUNK_SIZE]
            output_emitter.push(chunk)
            offset += len(chunk)

        output_emitter.flush()


# ---------------------------------------------------------------------------
# Internal factory
# ---------------------------------------------------------------------------


def _build_service(*, api_key: str, model: str, voice_id: str) -> MiniMaxTTSService:
    """Build a ``MiniMaxTTSService`` from explicit credentials.

    Args:
        api_key: MiniMax API key.
        model: TTS model name, e.g. ``"speech-01"``.
        voice_id: Voice ID, e.g. ``"female-shaonv"``.

    Returns:
        Configured ``MiniMaxTTSService`` instance.
    """

    class _Settings:
        MINIMAX_API_KEY = api_key
        MINIMAX_TTS_MODEL = model
        MINIMAX_TTS_VOICE_ID = voice_id

    return MiniMaxTTSService.from_settings(_Settings())
