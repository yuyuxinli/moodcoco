"""persona_agent.py — second AI participant in moodcoco-voice room.

Plays the role of a persona (default: 玉玉, an 18-y/o student venting about her
mom). Joins LiveKit room as a regular publisher so coco's STT picks up its
voice and runs the full fast/slow pipeline. The agent then listens to coco's
reply, runs STT itself, generates the next persona line via LLM, synthesizes
via MiniMax T2A v2, and publishes back. Loops until stopped.

Architecture:
    persona ──audio──▶ LiveKit room ──audio──▶ coco-agent
    persona ◀─audio── LiveKit room ◀─audio── coco-agent

    persona internal:
        on coco audio idle 1.5s →
            buffer→pcm→XfyunASR (via patched plugin) →
            doubao-lite (persona prompt) →
            MiniMax T2A v2 → publish
"""
from __future__ import annotations

import argparse
import asyncio
import audioop
import contextlib
import json
import os
import signal
import sys
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from dotenv import load_dotenv
from livekit import rtc
from livekit.api import AccessToken, VideoGrants


DEFAULT_ROOM = "moodcoco-voice"
DEFAULT_IDENTITY = "persona-yuyu"
DEFAULT_OPENING_LINE = "可可，我和我妈昨天大吵了一架，我感觉特别委屈。"

PERSONA_SYSTEM_PROMPT = (
    "你扮演 18 岁女生玉玉，刚和妈妈吵架。说话短、口语化、情绪化、自然真实，"
    "像在对朋友（可可）抱怨。每次只说 1 到 2 句中文，10-30 字。"
    "不要任何旁白、动作描写、心理活动；不要分析、建议、总结。"
    "直接说出你这一轮想说的话。如果可可问问题就回答她，如果可可在共情就继续抱怨。"
)


def _stop_path(identity: str) -> Path:
    return Path(f"/tmp/{identity}.stop")


def _build_token(*, room_name: str, identity: str) -> str:
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("LIVEKIT_API_KEY / LIVEKIT_API_SECRET required")
    return (
        AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )


@dataclass
class CocoListener:
    """Subscribe to coco's audio track, buffer 48k PCM, expose 'utterance ready'."""
    sample_rate: int = 48_000
    silence_threshold_rms: int = 200
    # fast filler often runs ~1s before slow_v1 starts; wait long enough so
    # we treat (filler + slow_v1) as a single utterance.
    idle_seconds: float = 3.5

    _frames: list[bytes] = field(default_factory=list)
    _has_voice_in_current_utterance: bool = False
    _last_voice_at: float | None = None
    _last_frame_at: float | None = None
    _stream: rtc.AudioStream | None = None
    _task: asyncio.Task | None = None
    _utterance_event: asyncio.Event = field(default_factory=asyncio.Event)
    _last_pcm: bytes = b""

    def attach(self, track: rtc.Track) -> None:
        self._stream = rtc.AudioStream.from_track(
            track=track, sample_rate=self.sample_rate, num_channels=1
        )
        self._task = asyncio.create_task(self._run(), name="coco-listener")

    async def _run(self) -> None:
        assert self._stream is not None
        async for event in self._stream:
            data = bytes(event.frame.data)
            now = time.monotonic()
            self._last_frame_at = now
            try:
                rms = audioop.rms(data, 2)
            except audioop.error:
                rms = 0
            if rms > self.silence_threshold_rms:
                self._has_voice_in_current_utterance = True
                self._last_voice_at = now
                self._frames.append(data)
            elif self._has_voice_in_current_utterance:
                # silence after speech: still capture short tail
                self._frames.append(data)
                if (now - (self._last_voice_at or now)) >= self.idle_seconds:
                    self._finalize_utterance()

    def _finalize_utterance(self) -> None:
        if not self._frames:
            return
        self._last_pcm = b"".join(self._frames)
        self._frames = []
        self._has_voice_in_current_utterance = False
        self._utterance_event.set()

    async def wait_for_utterance(self, max_wait_s: float) -> bytes | None:
        try:
            await asyncio.wait_for(self._utterance_event.wait(), timeout=max_wait_s)
        except asyncio.TimeoutError:
            return None
        self._utterance_event.clear()
        pcm = self._last_pcm
        self._last_pcm = b""
        return pcm

    async def aclose(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._stream is not None:
            await self._stream.aclose()


def resample_48k_to_16k(pcm_48k: bytes) -> bytes:
    """48 kHz mono 16-bit → 16 kHz mono 16-bit using audioop."""
    converted, _state = audioop.ratecv(pcm_48k, 2, 1, 48000, 16000, None)
    return converted


def stt_xfyun_via_plugin(pcm_16k: bytes) -> str:
    """Run our patched Xfyun plugin (with wpgs rebuild) on raw 16k PCM."""
    import tempfile
    from backend.voice.plugins.xfyun_stt import XfyunSTTPlugin

    plugin = XfyunSTTPlugin()
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as f:
        f.write(pcm_16k)
        tmp = f.name
    try:
        return plugin._recognize_with_vendor_errors(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


async def call_persona_llm(history: list[dict]) -> str:
    """Doubao lite chat completion for persona's next utterance."""
    api_key = os.environ["DOUBAO_API_KEY"]
    base_url = os.environ.get("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
    # Use lite for speed; fall back to whatever DOUBAO_MODEL is set if user prefers.
    model = os.environ.get("PERSONA_LLM_MODEL", "doubao-seed-2-0-lite-260215")

    body = {
        "model": model,
        "messages": [{"role": "system", "content": PERSONA_SYSTEM_PROMPT}, *history],
        "temperature": 0.9,
        "max_tokens": 80,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        r.raise_for_status()
        data = r.json()
        msg = data["choices"][0]["message"]
        return (msg.get("content") or msg.get("reasoning_content") or "").strip()


async def minimax_tts_to_pcm(text: str, *, sample_rate: int = 48_000) -> bytes:
    """Synthesize text via MiniMax T2A v2 → 48 kHz mono 16-bit PCM bytes.

    Uses MP3 wire format (smaller payload), then ffmpeg-decoded to PCM in-process.
    """
    api_key = os.environ["MINIMAX_API_KEY"]
    model = os.environ.get("MINIMAX_TTS_MODEL", "speech-2.6-hd")
    voice_id = os.environ.get("PERSONA_VOICE_ID", "Chinese (Mandarin)_Cute_Spirit")

    body = {
        "model": model,
        "text": text,
        "stream": False,
        "voice_setting": {"voice_id": voice_id, "speed": 1.05, "vol": 1.0, "pitch": 0},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
        "subtitle_enable": False,
        "output_format": "hex",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.minimaxi.com/v1/t2a_v2",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
        )
        r.raise_for_status()
        result = r.json()
        if result.get("base_resp", {}).get("status_code") != 0:
            raise RuntimeError(f"MiniMax T2A failed: {result.get('base_resp')}")
        mp3_bytes = bytes.fromhex(result["data"]["audio"])

    # ffmpeg decode mp3 → s16le PCM at desired sample rate
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_bytes)
        mp3_path = f.name
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path,
             "-f", "s16le", "-ac", "1", "-ar", str(sample_rate),
             "-loglevel", "error", "-"],
            check=True, capture_output=True,
        )
        return proc.stdout
    finally:
        with contextlib.suppress(OSError):
            os.unlink(mp3_path)


async def publish_pcm(*, source: rtc.AudioSource, pcm: bytes,
                     sample_rate: int = 48_000, frame_ms: int = 20) -> None:
    """Push 48 kHz mono 16-bit PCM into the LiveKit AudioSource."""
    samples_per_channel = int(sample_rate * frame_ms / 1000)
    frame_bytes = samples_per_channel * 2  # 16-bit mono
    for offset in range(0, len(pcm), frame_bytes):
        chunk = pcm[offset:offset + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk += b"\x00" * (frame_bytes - len(chunk))
        frame = rtc.AudioFrame(
            data=chunk, sample_rate=sample_rate, num_channels=1,
            samples_per_channel=samples_per_channel,
        )
        await source.capture_frame(frame)


async def run_persona(
    *,
    room_name: str,
    identity: str,
    opening: str,
    max_turns: int,
) -> None:
    load_dotenv("/Users/jianghongwei/Documents/moodcoco/.env")
    lk_url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    token = _build_token(room_name=room_name, identity=identity)

    room = rtc.Room()
    listener = CocoListener()
    coco_attached = asyncio.Event()

    @room.on("track_subscribed")
    def _on_track(track, publication, participant):
        # Only listen to participants whose identity starts with "agent-" or
        # equals "coco" — never to ourselves.
        if participant.identity == identity:
            return
        if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            return
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        listener.attach(track)
        coco_attached.set()
        print(f"[persona] attached to coco track ({participant.identity})", file=sys.stderr)

    audio_source = rtc.AudioSource(48_000, 1, queue_size_ms=2000)
    local_track = rtc.LocalAudioTrack.create_audio_track("persona-mic", audio_source)
    publish_options = rtc.TrackPublishOptions()
    publish_options.source = rtc.TrackSource.SOURCE_MICROPHONE

    stop_path = _stop_path(identity)
    if stop_path.exists():
        stop_path.unlink()

    try:
        await room.connect(lk_url, token)
        await room.local_participant.publish_track(local_track, publish_options)
        print(f"[persona] connected as {identity}, published mic", file=sys.stderr)

        history: list[dict] = []
        # Opening utterance — persona speaks first to seed the conversation.
        print(f"[persona] T0 → {opening}", file=sys.stderr)
        history.append({"role": "assistant", "content": opening})
        opening_pcm = await minimax_tts_to_pcm(opening)
        await publish_pcm(source=audio_source, pcm=opening_pcm)

        # Wait for coco to attach & finish first reply.
        await asyncio.wait_for(coco_attached.wait(), timeout=120.0)

        for turn in range(1, max_turns + 1):
            if stop_path.exists():
                print(f"[persona] stop file detected, exiting", file=sys.stderr)
                break

            # Listen for coco's reply (utterance = silence ≥ 1.5s after voice).
            print(f"[persona] turn {turn}: waiting for coco...", file=sys.stderr)
            # Wait indefinitely (in 30s slices) so the loop never times out;
            # only the stop file or coco silence (handled below) ends it.
            coco_pcm_48k = None
            while coco_pcm_48k is None:
                if stop_path.exists():
                    print(f"[persona] stop file detected mid-wait, exiting", file=sys.stderr)
                    return
                coco_pcm_48k = await listener.wait_for_utterance(max_wait_s=30.0)
                if coco_pcm_48k is None:
                    print("[persona] still waiting for coco...", file=sys.stderr)
            if len(coco_pcm_48k) < 48_000 * 2 * 1:  # < 1s
                print(f"[persona] coco utterance too short ({len(coco_pcm_48k)} bytes), waiting", file=sys.stderr)
                continue

            # STT
            coco_pcm_16k = resample_48k_to_16k(coco_pcm_48k)
            t0 = time.time()
            coco_text = await asyncio.to_thread(stt_xfyun_via_plugin, coco_pcm_16k)
            stt_ms = (time.time() - t0) * 1000
            if not coco_text or coco_text == "。":
                print(f"[persona] coco STT empty/unusable ({coco_text!r}), skipping turn", file=sys.stderr)
                continue
            print(f"[persona] turn {turn} ⇐ coco said: {coco_text}  ({stt_ms:.0f}ms)", file=sys.stderr)
            history.append({"role": "user", "content": coco_text})

            # LLM
            t0 = time.time()
            persona_reply = await call_persona_llm(history)
            llm_ms = (time.time() - t0) * 1000
            if not persona_reply:
                persona_reply = "嗯。"
            print(f"[persona] turn {turn} ⇒ persona says: {persona_reply}  ({llm_ms:.0f}ms)", file=sys.stderr)
            history.append({"role": "assistant", "content": persona_reply})

            # TTS + publish
            t0 = time.time()
            pcm = await minimax_tts_to_pcm(persona_reply)
            tts_ms = (time.time() - t0) * 1000
            await publish_pcm(source=audio_source, pcm=pcm)
            print(f"[persona] turn {turn} published {len(pcm)} bytes  (tts {tts_ms:.0f}ms)", file=sys.stderr)
    finally:
        with contextlib.suppress(Exception):
            await listener.aclose()
        with contextlib.suppress(Exception):
            await audio_source.aclose()
        with contextlib.suppress(Exception):
            await room.disconnect()
        print("[persona] disconnected", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="persona AI for moodcoco voice room")
    parser.add_argument("--room", default=DEFAULT_ROOM)
    parser.add_argument("--identity", default=DEFAULT_IDENTITY)
    parser.add_argument("--opening", default=DEFAULT_OPENING_LINE)
    parser.add_argument("--max-turns", type=int, default=999)
    args = parser.parse_args()

    print(f"[persona] starting; touch /tmp/{args.identity}.stop to stop", file=sys.stderr)
    asyncio.run(run_persona(
        room_name=args.room,
        identity=args.identity,
        opening=args.opening,
        max_turns=args.max_turns,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
