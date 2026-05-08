"""Xfyun IAT streaming ASR helpers and LiveKit STT plugin."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import hmac
import inspect
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Any
from urllib.parse import urlencode, urlparse

import websockets
from livekit.agents.stt import (
    RecognizeStream,
    STT,
    STTCapabilities,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
)
from livekit.agents.types import (
    APIConnectOptions,
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    NotGivenOr,
)
from livekit.agents.utils import AudioBuffer

from backend.voice.plugins._context import (
    set_latest_voice_turn_id,
    voice_session_ctx,
    voice_turn_ctx,
)
from backend.voice.streaming_events import VoiceStreamEvent

_DEFAULT_IAT_URL = "wss://ws-api.xfyun.cn/v2/iat"
_DEFAULT_SAMPLE_RATE = 16_000
logger = logging.getLogger("voice.plugins.xfyun_streaming_stt")

VoiceEventPublisher = Callable[[VoiceStreamEvent], Awaitable[None]]


@dataclass(slots=True)
class XfyunTranscriptEvent:
    text: str
    is_final: bool
    segments: list[str] = field(default_factory=list)
    pgs: str | None = None
    rg: list[int] | None = None


def parse_xfyun_iat_message(message: dict[str, Any]) -> XfyunTranscriptEvent:
    code = int(message.get("code", 0))
    if code != 0:
        raise RuntimeError(f"Xfyun streaming ASR error: {message}")
    data = message.get("data") or {}
    result = data.get("result") or {}
    segments: list[str] = []
    for item in result.get("ws") or []:
        candidates = item.get("cw") or []
        if candidates:
            text = str(candidates[0].get("w") or "")
            if text:
                segments.append(text)
    return XfyunTranscriptEvent(
        text="".join(segments),
        is_final=int(data.get("status", 0)) == 2,
        segments=segments,
        pgs=result.get("pgs"),
        rg=result.get("rg"),
    )


class TranscriptAggregator:
    def __init__(self) -> None:
        self._segments: list[str] = []
        self.final_text = ""

    def update(
        self,
        segments: list[str],
        *,
        is_final: bool,
        pgs: str | None = None,
        rg: list[int] | None = None,
    ) -> str:
        cleaned = [segment for segment in segments if segment]
        if pgs == "rpl":
            if not rg or len(rg) != 2:
                raise RuntimeError("Xfyun rpl event missing rg range")
            start = max(rg[0] - 1, 0)
            end = max(rg[1], start)
            self._segments[start:end] = cleaned
        elif pgs == "apd" or pgs is None:
            self._segments.extend(cleaned)
        else:
            raise RuntimeError(f"unknown Xfyun pgs mode: {pgs}")
        current = "".join(self._segments)
        if is_final:
            self.final_text = current
        return current


def build_xfyun_iat_url(
    *,
    base_url: str,
    api_key: str,
    api_secret: str,
    now: datetime | None = None,
) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc
    path = parsed.path or "/v2/iat"
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    date = format_datetime(timestamp, usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", '
        f'algorithm="hmac-sha256", '
        f'headers="host date request-line", '
        f'signature="{signature}"'
    )
    authorization = base64.b64encode(
        authorization_origin.encode("utf-8")
    ).decode("utf-8")
    return f"{base_url}?{urlencode({'authorization': authorization, 'date': date, 'host': host})}"


class XfyunStreamingASRClient:
    def __init__(
        self,
        *,
        app_id: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
        websocket_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._app_id = app_id or os.environ["XFYUN_APP_ID"]
        self._api_key = api_key or os.environ["XFYUN_API_KEY"]
        self._api_secret = api_secret or os.environ["XFYUN_API_SECRET"]
        self._base_url = base_url or os.environ.get("XFYUN_ASR_URL", _DEFAULT_IAT_URL)
        self._sample_rate = sample_rate
        self._websocket_factory = websocket_factory
        self._ws: Any | None = None

    async def start(self) -> None:
        url = build_xfyun_iat_url(
            base_url=self._base_url,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        if self._websocket_factory is None:
            self._ws = await websockets.connect(url)
        else:
            self._ws = self._websocket_factory(url)

    async def send_pcm(self, pcm: bytes, *, status: int) -> None:
        await self._send(
            {
                "header": {
                    "app_id": self._app_id,
                    "status": status,
                },
                "parameter": {
                    "iat": {
                        "domain": "slm",
                        "language": "zh_cn",
                        "accent": "mandarin",
                        "dwa": "wpgs",
                        "eos": 60000,
                        "result": {
                            "encoding": "utf8",
                            "compress": "raw",
                            "format": "plain",
                        },
                    }
                },
                "payload": {
                    "audio": {
                        "encoding": "raw",
                        "sample_rate": self._sample_rate,
                        "audio": base64.b64encode(pcm).decode("utf-8"),
                    }
                },
            }
        )

    async def events(self) -> AsyncIterator[XfyunTranscriptEvent]:
        while True:
            message = json.loads(await self._require_ws().recv())
            event = parse_xfyun_iat_message(message)
            yield event
            if event.is_final:
                break

    async def close(self) -> None:
        ws = self._ws
        if ws is not None:
            close = getattr(ws, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result
            self._ws = None

    async def _send(self, payload: dict[str, Any]) -> None:
        await self._require_ws().send(json.dumps(payload, ensure_ascii=False))

    def _require_ws(self) -> Any:
        if self._ws is None:
            raise RuntimeError("Xfyun streaming ASR websocket is not started")
        return self._ws


def _stt_capabilities() -> STTCapabilities:
    params = inspect.signature(STTCapabilities).parameters
    kwargs: dict[str, Any] = {
        "streaming": True,
        "interim_results": True,
    }
    if "offline_recognize" in params:
        kwargs["offline_recognize"] = False
    return STTCapabilities(**kwargs)


class XfyunStreamingSTTPlugin(STT):
    def __init__(
        self,
        *,
        client_factory: Callable[[], XfyunStreamingASRClient] | None = None,
        event_publisher: VoiceEventPublisher | None = None,
        language: str = "zh-cn",
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
    ) -> None:
        super().__init__(capabilities=_stt_capabilities())
        self._client_factory = client_factory or XfyunStreamingASRClient
        self._event_publisher = event_publisher
        self._language = language
        self._sample_rate = sample_rate

    @property
    def model(self) -> str:
        return "xfyun-iat-streaming"

    @property
    def provider(self) -> str:
        return "xfyun"

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> SpeechEvent:
        raise RuntimeError("XfyunStreamingSTTPlugin only supports streaming STT")

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> RecognizeStream:
        return XfyunRecognizeStream(
            stt=self,
            conn_options=conn_options,
            sample_rate=self._sample_rate,
            client=self._client_factory(),
            event_publisher=self._event_publisher,
            language=self._language,
        )


class XfyunRecognizeStream(RecognizeStream):
    def __init__(
        self,
        *,
        stt: STT,
        conn_options: APIConnectOptions,
        sample_rate: int,
        client: XfyunStreamingASRClient,
        event_publisher: VoiceEventPublisher | None,
        language: str,
    ) -> None:
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=sample_rate)
        self._client = client
        self._event_publisher = event_publisher
        self._language = language
        self._aggregator = TranscriptAggregator()
        self._turn_id = uuid.uuid4().hex[:8]

    async def _run(self) -> None:
        session_id = voice_session_ctx.get() or "unknown"
        voice_turn_ctx.set(self._turn_id)
        set_latest_voice_turn_id(session_id, self._turn_id)
        logger.info(
            "voice_streaming_stt_started",
            extra={"session_id": session_id, "turn_id": self._turn_id},
        )
        await self._client.start()
        input_task = asyncio.create_task(self._send_audio_from_input())
        receive_task = asyncio.create_task(self._emit_transcripts())
        try:
            done, _pending = await asyncio.wait(
                {input_task, receive_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                task.result()
            if input_task in done and receive_task not in done:
                await receive_task
            elif receive_task in done and input_task not in done:
                input_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await input_task
        finally:
            for task in (input_task, receive_task):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            await self._client.close()

    async def _send_audio_from_input(self) -> None:
        status = 0
        async for item in self._input_ch:
            if isinstance(item, RecognizeStream._FlushSentinel):
                await self._client.send_pcm(b"", status=2)
                status = 0
                continue
            await self._client.send_pcm(bytes(item.data), status=status)
            status = 1

    async def _emit_transcripts(self) -> None:
        async for transcript in self._client.events():
            text = self._aggregator.update(
                transcript.segments,
                is_final=transcript.is_final,
                pgs=transcript.pgs,
                rg=transcript.rg,
            )
            speech_type = (
                SpeechEventType.FINAL_TRANSCRIPT
                if transcript.is_final
                else SpeechEventType.INTERIM_TRANSCRIPT
            )
            self._event_ch.send_nowait(
                SpeechEvent(
                    type=speech_type,
                    alternatives=[
                        SpeechData(
                            language=self._language,
                            text=text,
                            confidence=1.0 if text else 0.0,
                        )
                    ],
                )
            )
            if self._event_publisher is not None:
                await self._event_publisher(
                    VoiceStreamEvent(
                        type="user_final" if transcript.is_final else "user_partial",
                        session_id=voice_session_ctx.get() or "unknown",
                        turn_id=self._turn_id,
                        text=text,
                        is_final=transcript.is_final,
                    )
                )
