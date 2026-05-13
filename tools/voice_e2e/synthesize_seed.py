from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import time
import wave
from pathlib import Path

from dotenv import load_dotenv

from backend.voice.plugins.minimax_tts import _build_service


DEFAULT_TEXT = "我和我妈昨天大吵了一架，我感觉特别委屈"
DEFAULT_VOICE = "Tingting"
DEFAULT_PROVIDER = "minimax"
TMP_MP3_PATH = Path("/tmp/moodcoco-seed-source.mp3")
TMP_AIFF_PATH = Path("/tmp/moodcoco-seed-source.aiff")
TMP_SWIFT_PATH = Path("/tmp/moodcoco-seed-synth.swift")


def _convert_to_wav(input_path: Path, output_path: Path, *, sample_rate: int) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg command not found")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-sample_fmt",
            "s16",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output_path


def _assert_nonempty_wav(path: Path) -> Path:
    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getnframes() <= 0:
            raise RuntimeError(f"generated empty wav file: {path}")
    return path


def _wait_for_audio_file(path: Path, *, timeout_s: float = 20.0) -> Path:
    deadline = time.monotonic() + timeout_s
    last_size = -1
    stable_hits = 0

    while time.monotonic() < deadline:
        if path.exists():
            size = path.stat().st_size
            if size > 4096:
                if size == last_size:
                    stable_hits += 1
                    if stable_hits >= 2:
                        return path
                else:
                    stable_hits = 0
                last_size = size
        time.sleep(0.25)

    raise RuntimeError(f"audio file did not materialize in time: {path}")


async def _synthesize_with_minimax_async(
    *,
    text: str,
    output_path: Path,
    sample_rate: int = 16_000,
) -> Path:
    load_dotenv()
    minimax_api_key = os.environ.get("MINIMAX_API_KEY", "")
    minimax_model = os.environ.get("MINIMAX_TTS_MODEL", "speech-01")
    minimax_voice_id = os.environ.get("MINIMAX_TTS_VOICE_ID", "female-shaonv")
    if not minimax_api_key:
        raise RuntimeError("MINIMAX_API_KEY is required for seed synthesis")

    service = _build_service(
        api_key=minimax_api_key,
        model=minimax_model,
        voice_id=minimax_voice_id,
    )
    try:
        audio_bytes, _meta = await service.synthesize_bytes(text)
        if not audio_bytes:
            raise RuntimeError("MiniMax TTS returned empty audio bytes")
        TMP_MP3_PATH.write_bytes(audio_bytes)
        wav_path = _convert_to_wav(TMP_MP3_PATH, output_path, sample_rate=sample_rate)
        return _assert_nonempty_wav(wav_path)
    finally:
        await service.close()
        TMP_MP3_PATH.unlink(missing_ok=True)


def synthesize_with_minimax(
    *,
    text: str,
    output_path: Path,
    sample_rate: int = 16_000,
) -> Path:
    return asyncio.run(
        _synthesize_with_minimax_async(
            text=text,
            output_path=output_path,
            sample_rate=sample_rate,
        )
    )


def synthesize_with_say(
    *,
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    sample_rate: int = 16_000,
) -> Path:
    if shutil.which("say") is None:
        return synthesize_with_swift(
            text=text,
            output_path=output_path,
            voice=voice,
            sample_rate=sample_rate,
        )

    try:
        subprocess.run(
            ["say", "-v", voice, "-o", str(TMP_AIFF_PATH), text],
            check=True,
            capture_output=True,
            text=True,
        )
        _wait_for_audio_file(TMP_AIFF_PATH)
        wav_path = _convert_to_wav(TMP_AIFF_PATH, output_path, sample_rate=sample_rate)
        return _assert_nonempty_wav(wav_path)
    except Exception:
        return synthesize_with_swift(
            text=text,
            output_path=output_path,
            voice=voice,
            sample_rate=sample_rate,
        )
    finally:
        TMP_AIFF_PATH.unlink(missing_ok=True)


def synthesize_with_swift(
    *,
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    sample_rate: int = 16_000,
) -> Path:
    if shutil.which("swift") is None:
        raise RuntimeError("swift command not found for macOS TTS fallback")

    resolved_voice_id = "com.apple.voice.compact.zh-CN.Tingting"
    if "eddy" in voice.lower():
        resolved_voice_id = "com.apple.eloquence.zh-CN.Eddy"

    swift_source = f"""
import AppKit
import Foundation

final class Delegate: NSObject, NSSpeechSynthesizerDelegate {{
    let sem = DispatchSemaphore(value: 0)
    func speechSynthesizer(_ sender: NSSpeechSynthesizer, didFinishSpeaking finishedSpeaking: Bool) {{
        sem.signal()
    }}
}}

let output = URL(fileURLWithPath: "{TMP_AIFF_PATH}")
try? FileManager.default.removeItem(at: output)
let voice = NSSpeechSynthesizer.VoiceName(rawValue: {json.dumps(resolved_voice_id)})
let synth = NSSpeechSynthesizer(voice: voice) ?? NSSpeechSynthesizer()
let delegate = Delegate()
synth.delegate = delegate
let ok = synth.startSpeaking({json.dumps(text, ensure_ascii=False)}, to: output)
if ok {{
    _ = delegate.sem.wait(timeout: .now() + 20)
}}
"""
    TMP_SWIFT_PATH.write_text(swift_source, encoding="utf-8")

    try:
        swift_env = os.environ.copy()
        swift_env.setdefault("CLANG_MODULE_CACHE_PATH", "/tmp/moodcoco-clang-module-cache")
        swift_env.setdefault("SWIFT_MODULECACHE_PATH", "/tmp/moodcoco-swift-module-cache")
        subprocess.run(
            ["swift", str(TMP_SWIFT_PATH)],
            check=True,
            capture_output=True,
            text=True,
            env=swift_env,
        )
        _wait_for_audio_file(TMP_AIFF_PATH)
        wav_path = _convert_to_wav(TMP_AIFF_PATH, output_path, sample_rate=sample_rate)
        return _assert_nonempty_wav(wav_path)
    finally:
        TMP_SWIFT_PATH.unlink(missing_ok=True)
        TMP_AIFF_PATH.unlink(missing_ok=True)


def synthesize_seed_audio(
    *,
    text: str,
    output_path: Path,
    provider: str = DEFAULT_PROVIDER,
    voice: str = DEFAULT_VOICE,
    sample_rate: int = 16_000,
) -> Path:
    if provider == "minimax":
        return synthesize_with_minimax(
            text=text,
            output_path=output_path,
            sample_rate=sample_rate,
        )
    if provider == "say":
        return synthesize_with_say(
            text=text,
            output_path=output_path,
            voice=voice,
            sample_rate=sample_rate,
        )
    raise ValueError(f"unsupported provider: {provider}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate seed Chinese audio for LiveKit E2E")
    parser.add_argument(
        "--text",
        default=DEFAULT_TEXT,
        help="Seed Chinese text to synthesize",
    )
    parser.add_argument(
        "--output",
        default="/tmp/moodcoco-seed.wav",
        help="Output wav path",
    )
    parser.add_argument(
        "--provider",
        choices=["minimax", "say"],
        default=DEFAULT_PROVIDER,
        help="Seed audio provider",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help="macOS say voice name",
    )
    args = parser.parse_args()

    output_path = synthesize_seed_audio(
        text=args.text,
        output_path=Path(args.output),
        provider=args.provider,
        voice=args.voice,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
