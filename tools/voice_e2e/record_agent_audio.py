from __future__ import annotations

import asyncio
import contextlib
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

from livekit import rtc


@dataclass
class AgentAudioRecorder:
    output_path: Path
    sample_rate: int = 48_000
    num_channels: int = 1
    _frame_count: int = 0
    _last_frame_at: float | None = None
    _started: asyncio.Event = field(default_factory=asyncio.Event)
    _stream: rtc.AudioStream | None = None
    _task: asyncio.Task[None] | None = None

    async def start(self, track: rtc.Track) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = rtc.AudioStream.from_track(
            track=track,
            sample_rate=self.sample_rate,
            num_channels=self.num_channels,
        )
        self._task = asyncio.create_task(self._run(), name="agent-audio-recorder")

    async def _run(self) -> None:
        assert self._stream is not None
        with wave.open(str(self.output_path), "wb") as wav_file:
            wav_file.setnchannels(self.num_channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            async for event in self._stream:
                wav_file.writeframes(event.frame.data)
                self._frame_count += 1
                self._last_frame_at = time.monotonic()
                self._started.set()

    async def wait_until_started(self, timeout_s: float) -> None:
        await asyncio.wait_for(self._started.wait(), timeout=timeout_s)

    async def wait_for_idle(self, idle_timeout_s: float, max_wait_s: float) -> bool:
        started_at = time.monotonic()
        while time.monotonic() - started_at < max_wait_s:
            if self._frame_count == 0:
                await asyncio.sleep(0.2)
                continue
            if self._last_frame_at is None:
                await asyncio.sleep(0.2)
                continue
            if time.monotonic() - self._last_frame_at >= idle_timeout_s:
                return True
            await asyncio.sleep(0.2)
        return False

    async def aclose(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._stream is not None:
            await self._stream.aclose()

    @property
    def frame_count(self) -> int:
        return self._frame_count
