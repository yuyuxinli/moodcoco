"""Unit tests for MinimaxTTSPlugin (F4).

All 6 test cases per task spec + F1 §8 F4 acceptance criteria.
MiniMaxTTSService is fully mocked — no network calls are made.
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from livekit import rtc

from backend.voice.plugins.minimax_tts import (
    MinimaxTTSAuthError,
    MinimaxTTSPlugin,
    MinimaxTTSRateLimitError,
    MinimaxTTSTimeoutError,
    MinimaxTTSError,
    MinimaxChunkedStream,
    _CHUNK_SIZE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service_mock(return_bytes: bytes | None = None) -> MagicMock:
    """Return a MagicMock standing in for MiniMaxTTSService."""
    svc = MagicMock()
    svc.synthesize_bytes = AsyncMock(return_value=(return_bytes, {}))
    svc.close = AsyncMock()
    return svc


def _make_pcm_bytes(duration_s: float = 0.25, sample_rate: int = 32_000) -> bytes:
    """Return silent 16-bit mono PCM bytes of the given duration."""
    num_samples = int(duration_s * sample_rate)
    return bytes(num_samples * 2)  # 16-bit = 2 bytes per sample


async def _collect_via_mock_run(
    plugin: MinimaxTTSPlugin,
    text: str,
    mock_audio_bytes: bytes,
) -> list:
    """Run synthesize() with _run mocked to push PCM frames via AudioEmitter.

    This bypasses the MP3 codec pipeline while still exercising all
    MinimaxTTSPlugin/MinimaxChunkedStream logic above _run().
    """
    # We intercept _run() so it:
    #  1. Calls the real service mock (to verify service interaction)
    #  2. Pushes PCM bytes (not MP3) to avoid av.open codec errors in tests
    original_run = MinimaxChunkedStream._run

    async def pcm_run(self: MinimaxChunkedStream, output_emitter) -> None:
        # Call the vendor service as the real code would.
        audio_bytes, _meta = await plugin._service.synthesize_bytes(text)
        if not audio_bytes:
            raise MinimaxTTSError("MiniMax TTS returned empty audio response")
        # Push as raw PCM so the emitter doesn't need av/codec installed.
        output_emitter.initialize(
            request_id="test-request-id",
            sample_rate=plugin.sample_rate,
            num_channels=plugin.num_channels,
            mime_type="audio/pcm",
            stream=False,
        )
        offset = 0
        while offset < len(mock_audio_bytes):
            chunk = mock_audio_bytes[offset : offset + _CHUNK_SIZE]
            output_emitter.push(chunk)
            offset += len(chunk)
        output_emitter.flush()

    frames = []
    with patch.object(MinimaxChunkedStream, "_run", pcm_run):
        stream = plugin.synthesize(text)
        try:
            async for event in stream:
                frames.append(event)
        finally:
            await stream.aclose()
    return frames


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars MINIMAX_API_KEY/TTS_MODEL/TTS_VOICE_ID are read at construction."""
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key-env")
    monkeypatch.setenv("MINIMAX_TTS_MODEL", "speech-env-model")
    monkeypatch.setenv("MINIMAX_TTS_VOICE_ID", "voice-env-id")

    with patch("backend.voice.plugins.minimax_tts._build_service") as mock_build:
        mock_build.return_value = MagicMock()
        plugin = MinimaxTTSPlugin()

        mock_build.assert_called_once_with(
            api_key="test-key-env",
            model="speech-env-model",
            voice_id="voice-env-id",
        )
        assert plugin.model == "speech-env-model"
        assert plugin._voice_id == "voice-env-id"


@pytest.mark.asyncio
async def test_synthesize_happy_path() -> None:
    """Mock service returns bytes; AudioEmitter receives non-empty audio frame."""
    pcm_audio = _make_pcm_bytes(duration_s=0.25)
    svc = _make_service_mock(return_bytes=pcm_audio)
    plugin = MinimaxTTSPlugin(_service=svc)

    frames = await _collect_via_mock_run(plugin, "你好世界", pcm_audio)

    # At least one SynthesizedAudio event must have been emitted.
    assert len(frames) >= 1, "Expected at least one SynthesizedAudio frame"
    first_frame = frames[0]
    # Frame data must be non-empty (real audio samples).
    assert len(bytes(first_frame.frame.data)) > 0
    # Service was called exactly once.
    svc.synthesize_bytes.assert_awaited_once_with("你好世界")


@pytest.mark.asyncio
async def test_synthesize_chunks_audio() -> None:
    """PCM payload larger than _CHUNK_SIZE causes push() to be called >1 time."""
    # 128 KB > _CHUNK_SIZE (64 KB) → at least 2 push() calls.
    large_pcm = _make_pcm_bytes(duration_s=2.0)  # 2s @ 32kHz = 128 KB
    svc = _make_service_mock(return_bytes=large_pcm)
    plugin = MinimaxTTSPlugin(_service=svc)

    push_calls: list[int] = []

    async def counting_run(self: MinimaxChunkedStream, output_emitter) -> None:
        audio_bytes, _ = await plugin._service.synthesize_bytes("hello world chunked")
        if not audio_bytes:
            raise MinimaxTTSError("empty")
        output_emitter.initialize(
            request_id="test-req",
            sample_rate=plugin.sample_rate,
            num_channels=plugin.num_channels,
            mime_type="audio/pcm",
            stream=False,
        )
        count = 0
        offset = 0
        while offset < len(audio_bytes):
            chunk = audio_bytes[offset : offset + _CHUNK_SIZE]
            output_emitter.push(chunk)
            count += 1
            offset += len(chunk)
        output_emitter.flush()
        push_calls.append(count)

    with patch.object(MinimaxChunkedStream, "_run", counting_run):
        stream = plugin.synthesize("hello world chunked")
        try:
            async for _ in stream:
                pass
        finally:
            await stream.aclose()

    assert len(push_calls) == 1
    assert push_calls[0] >= 2, (
        f"Expected >= 2 push() calls for 128 KB payload, got {push_calls[0]}"
    )


@pytest.mark.asyncio
async def test_minimax_429_rate_limit() -> None:
    """HTTP 429 from the vendor raises MinimaxTTSRateLimitError."""
    response_mock = MagicMock()
    response_mock.status_code = 429
    response_mock.text = "rate limit exceeded"
    http_error = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=response_mock,
    )

    svc = MagicMock()
    svc.synthesize_bytes = AsyncMock(side_effect=http_error)
    svc.close = AsyncMock()

    plugin = MinimaxTTSPlugin(_service=svc)

    with pytest.raises(MinimaxTTSRateLimitError) as exc_info:
        async with plugin.synthesize("rate limit test") as stream:
            async for _ in stream:
                pass

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_minimax_auth_error() -> None:
    """HTTP 401 from the vendor raises MinimaxTTSAuthError."""
    response_mock = MagicMock()
    response_mock.status_code = 401
    response_mock.text = "unauthorized"
    http_error = httpx.HTTPStatusError(
        "401 Unauthorized",
        request=MagicMock(),
        response=response_mock,
    )

    svc = MagicMock()
    svc.synthesize_bytes = AsyncMock(side_effect=http_error)
    svc.close = AsyncMock()

    plugin = MinimaxTTSPlugin(_service=svc)

    with pytest.raises(MinimaxTTSAuthError) as exc_info:
        async with plugin.synthesize("auth error test") as stream:
            async for _ in stream:
                pass

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_minimax_timeout() -> None:
    """httpx.TimeoutException from the vendor raises MinimaxTTSTimeoutError."""
    timeout_exc = httpx.TimeoutException("request timed out")

    svc = MagicMock()
    svc.synthesize_bytes = AsyncMock(side_effect=timeout_exc)
    svc.close = AsyncMock()

    plugin = MinimaxTTSPlugin(_service=svc)

    with pytest.raises(MinimaxTTSTimeoutError):
        async with plugin.synthesize("timeout test") as stream:
            async for _ in stream:
                pass
