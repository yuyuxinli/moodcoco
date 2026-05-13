from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import time
import wave
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents.utils.participant import wait_for_agent
from livekit.api import AccessToken, VideoGrants

from tools.voice_e2e.record_agent_audio import AgentAudioRecorder
from tools.voice_e2e.synthesize_seed import DEFAULT_TEXT, synthesize_seed_audio

DEFAULT_ROOM = "moodcoco-voice"
DEFAULT_AGENT_AUDIO = Path("/tmp/moodcoco-agent-output.wav")
DEFAULT_SEED_AUDIO = Path("/tmp/moodcoco-seed.wav")


def _build_token(*, room_name: str, identity: str) -> str:
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("LIVEKIT_API_KEY / LIVEKIT_API_SECRET are required")

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


def _read_wav(path: Path) -> tuple[bytes, int, int]:
    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getsampwidth() != 2:
            raise RuntimeError(f"expected 16-bit PCM wav, got {wav_file.getsampwidth() * 8}-bit")
        return (
            wav_file.readframes(wav_file.getnframes()),
            wav_file.getframerate(),
            wav_file.getnchannels(),
        )


async def _publish_wav(
    *,
    room: rtc.Room,
    wav_path: Path,
    track_name: str = "fake-user-mic",
    frame_ms: int = 20,
) -> None:
    pcm_bytes, sample_rate, num_channels = _read_wav(wav_path)
    samples_per_channel = int(sample_rate * frame_ms / 1000)
    frame_bytes = samples_per_channel * num_channels * 2

    audio_source = rtc.AudioSource(sample_rate, num_channels, queue_size_ms=1000)
    local_track = rtc.LocalAudioTrack.create_audio_track(track_name, audio_source)
    options = rtc.TrackPublishOptions()
    options.source = rtc.TrackSource.SOURCE_MICROPHONE
    await room.local_participant.publish_track(local_track, options)

    for offset in range(0, len(pcm_bytes), frame_bytes):
        chunk = pcm_bytes[offset : offset + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk += b"\x00" * (frame_bytes - len(chunk))
        frame = rtc.AudioFrame(
            data=chunk,
            sample_rate=sample_rate,
            num_channels=num_channels,
            samples_per_channel=samples_per_channel,
        )
        await audio_source.capture_frame(frame)

    await audio_source.wait_for_playout()
    await audio_source.aclose()


async def run_fake_user(
    *,
    room_name: str,
    audio_path: Path,
    agent_audio_path: Path,
    wait_for_agent_s: float,
    wait_for_reply_s: float,
    idle_timeout_s: float,
) -> None:
    load_dotenv()
    livekit_url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    participant_identity = f"fake-user-{int(time.time())}"
    token = _build_token(room_name=room_name, identity=participant_identity)

    room = rtc.Room()
    recorder = AgentAudioRecorder(output_path=agent_audio_path)
    recorder_started = asyncio.Event()

    @room.on("track_subscribed")
    def _on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_AGENT:
            return
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if recorder._task is None:
            asyncio.create_task(recorder.start(track))
            recorder_started.set()

    try:
        await room.connect(livekit_url, token)
        await _publish_wav(room=room, wav_path=audio_path)

        await asyncio.wait_for(
            wait_for_agent(room),
            timeout=wait_for_agent_s,
        )
        await asyncio.wait_for(recorder_started.wait(), timeout=wait_for_agent_s)
        await recorder.wait_until_started(timeout_s=wait_for_reply_s)
        await recorder.wait_for_idle(
            idle_timeout_s=idle_timeout_s,
            max_wait_s=wait_for_reply_s,
        )
    finally:
        with contextlib.suppress(Exception):
            await recorder.aclose()
        with contextlib.suppress(Exception):
            await room.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description="LiveKit fake-user voice E2E runner")
    parser.add_argument("--audio", help="Path to a 16-bit PCM wav file")
    parser.add_argument("--room", default=DEFAULT_ROOM, help="LiveKit room name")
    parser.add_argument(
        "--seed-provider",
        choices=["say", "minimax"],
        default="say",
        help="Provider used when --audio is omitted",
    )
    parser.add_argument(
        "--agent-audio-output",
        default=str(DEFAULT_AGENT_AUDIO),
        help="Path to store the agent's returned wav audio",
    )
    parser.add_argument(
        "--wait-for-agent",
        type=float,
        default=20.0,
        help="Seconds to wait for the agent participant to appear",
    )
    parser.add_argument(
        "--wait-for-reply",
        type=float,
        default=45.0,
        help="Max seconds to wait for the agent reply audio",
    )
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=3.0,
        help="Seconds of remote audio silence before finishing the recording",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio) if args.audio else DEFAULT_SEED_AUDIO
    if not audio_path.exists():
        synthesize_seed_audio(
            text=DEFAULT_TEXT,
            output_path=audio_path,
            provider=args.seed_provider,
        )

    asyncio.run(
        run_fake_user(
            room_name=args.room,
            audio_path=audio_path,
            agent_audio_path=Path(args.agent_audio_output),
            wait_for_agent_s=args.wait_for_agent,
            wait_for_reply_s=args.wait_for_reply,
            idle_timeout_s=args.idle_timeout,
        )
    )
    print(Path(args.agent_audio_output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
