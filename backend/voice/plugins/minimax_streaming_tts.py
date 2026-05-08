"""MiniMax WebSocket T2A streaming client and LiveKit TTS adapter."""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import websockets
from livekit.agents.tts import TTS, TTSCapabilities


@dataclass(slots=True)
class MiniMaxStreamingTTSConfig:
    api_key: str
    group_id: str
    model: str = "speech-2.8-turbo"
    voice_id: str = "Chinese (Mandarin)_Cute_Spirit"
    sample_rate: int = 32000
    channel: int = 1
    audio_format: str = "pcm"
    language_boost: str = "Chinese"

    @classmethod
    def from_env(cls) -> "MiniMaxStreamingTTSConfig":
        return cls(
            api_key=os.environ["MINIMAX_API_KEY"],
            group_id=os.environ["MINIMAX_GROUP_ID"],
            model=os.environ.get("MINIMAX_TTS_MODEL", "speech-2.8-turbo"),
            voice_id=os.environ.get(
                "MINIMAX_TTS_VOICE_ID",
                "Chinese (Mandarin)_Cute_Spirit",
            ),
        )


class MiniMaxStreamingTTSClient:
    def __init__(
        self,
        *,
        config: MiniMaxStreamingTTSConfig,
        websocket_factory: Callable[[str, dict[str, str]], Any] | None = None,
    ) -> None:
        self._config = config
        self._websocket_factory = websocket_factory
        self._ws: Any | None = None

    async def start(self) -> None:
        url = f"wss://api.minimax.io/ws/v1/t2a_v2?GroupId={self._config.group_id}"
        headers = {"Authorization": f"Bearer {self._config.api_key}"}
        if self._websocket_factory is None:
            self._ws = await websockets.connect(url, additional_headers=headers)
        else:
            self._ws = self._websocket_factory(url, headers)

        await self._expect_ok("connected_success")
        await self._send(
            {
                "event": "task_start",
                "model": self._config.model,
                "language_boost": self._config.language_boost,
                "voice_setting": {
                    "voice_id": self._config.voice_id,
                    "speed": 1,
                    "vol": 1,
                    "pitch": 0,
                },
                "audio_setting": {
                    "sample_rate": self._config.sample_rate,
                    "format": self._config.audio_format,
                    "channel": self._config.channel,
                },
            }
        )
        await self._expect_ok("task_started")

    async def synthesize_sentence(self, text: str) -> AsyncIterator[bytes]:
        await self._send({"event": "task_continue", "text": text})
        while True:
            message = await self._recv()
            audio_hex = (message.get("data") or {}).get("audio")
            if audio_hex:
                yield bytes.fromhex(audio_hex)
            if message.get("is_final"):
                break

    async def finish(self) -> None:
        await self._send({"event": "task_finish"})
        ws = self._require_ws()
        await ws.close()

    async def _send(self, payload: dict[str, Any]) -> None:
        await self._require_ws().send(json.dumps(payload, ensure_ascii=False))

    async def _recv(self) -> dict[str, Any]:
        return json.loads(await self._require_ws().recv())

    async def _expect_ok(self, event_name: str) -> None:
        message = await self._recv()
        if message.get("event") != event_name:
            raise RuntimeError(f"expected {event_name}, got {message}")
        status = (message.get("base_resp") or {}).get("status_code", 0)
        if status != 0:
            raise RuntimeError(f"MiniMax TTS error: {message}")

    def _require_ws(self) -> Any:
        if self._ws is None:
            raise RuntimeError("MiniMax streaming TTS websocket is not started")
        return self._ws


class MiniMaxStreamingTTSPlugin(TTS):
    def __init__(self, *, config: MiniMaxStreamingTTSConfig | None = None) -> None:
        config = config or MiniMaxStreamingTTSConfig.from_env()
        super().__init__(
            capabilities=TTSCapabilities(streaming=True),
            sample_rate=config.sample_rate,
            num_channels=config.channel,
        )
        self.config = config

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def provider(self) -> str:
        return "minimax"
