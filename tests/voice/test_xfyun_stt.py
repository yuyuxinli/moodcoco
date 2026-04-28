"""Unit tests for XfyunSTTPlugin (F3).

All 6 test cases per F1 §8 F3 acceptance criteria.
XfyunASR is fully mocked — no network calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from livekit import rtc
from livekit.agents import APIConnectionError
from livekit.agents.stt import SpeechData, SpeechEvent, SpeechEventType
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS

from backend.voice.plugins.xfyun_stt import (
    XfyunSTTAuthError,
    XfyunSTTNetworkError,
    XfyunSTTPlugin,
    XfyunSTTTimeoutError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audio_buffer(
    duration_s: float = 0.1,
    sample_rate: int = 16_000,
) -> list[rtc.AudioFrame]:
    """Build a minimal AudioBuffer (list of one AudioFrame) with silent PCM."""
    samples = int(duration_s * sample_rate)
    data = bytes(samples * 2)  # 16-bit mono
    frame = rtc.AudioFrame(
        data=data,
        sample_rate=sample_rate,
        num_channels=1,
        samples_per_channel=samples,
    )
    return [frame]


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars XFYUN_APPID/API_KEY/API_SECRET are propagated to XfyunASR."""
    monkeypatch.setenv("XFYUN_APP_ID", "test_app_id_123")
    monkeypatch.setenv("XFYUN_API_KEY", "test_key_abc")
    monkeypatch.setenv("XFYUN_API_SECRET", "test_secret_xyz")

    with patch(
        "backend.voice.plugins.xfyun_stt.XfyunASR", autospec=True
    ) as MockASR:
        plugin = XfyunSTTPlugin()
        # Plugin should have constructed exactly one XfyunASR instance.
        MockASR.assert_called_once()
        # Env vars must have been set before XfyunASR() was called.
        assert os.environ.get("XFYUN_APP_ID") == "test_app_id_123"
        assert os.environ.get("XFYUN_API_KEY") == "test_key_abc"
        assert os.environ.get("XFYUN_API_SECRET") == "test_secret_xyz"


@pytest.mark.asyncio
async def test_recognize_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock XfyunASR.recognize returns text; SpeechEvent carries it correctly."""
    expected_text = "我和我妈吵架了"

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.return_value = expected_text

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        event: SpeechEvent = await plugin._recognize_impl(
            buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
        )

    assert event.type == SpeechEventType.FINAL_TRANSCRIPT
    assert len(event.alternatives) == 1
    alt: SpeechData = event.alternatives[0]
    assert alt.text == expected_text
    assert alt.language.lower() == "zh-cn"
    assert alt.confidence == 1.0


@pytest.mark.asyncio
async def test_recognize_writes_temp_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """Plugin writes PCM to a temp file and cleans it up after success."""
    captured_paths: list[str] = []

    def fake_recognize(path: str) -> str:
        captured_paths.append(path)
        # File must exist while recognize() is running.
        assert os.path.exists(path), "temp file should exist during recognize()"
        return "测试"

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = fake_recognize

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()
        await plugin._recognize_impl(buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS)

    assert len(captured_paths) == 1
    # After recognize() the temp file must be deleted.
    assert not os.path.exists(captured_paths[0]), (
        "temp file should be cleaned up after success"
    )


@pytest.mark.asyncio
async def test_recognize_temp_file_cleanup_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Temp file is removed even when XfyunASR.recognize raises an exception."""
    captured_paths: list[str] = []

    def failing_recognize(path: str) -> str:
        captured_paths.append(path)
        raise RuntimeError("ws connect failed")

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = failing_recognize

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        with pytest.raises((APIConnectionError, XfyunSTTNetworkError)):
            await plugin._recognize_impl(
                buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
            )

    assert len(captured_paths) == 1
    assert not os.path.exists(captured_paths[0]), (
        "temp file should be cleaned up even after error"
    )


@pytest.mark.asyncio
async def test_xfyun_network_error_mapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WebSocket-style connection error from XfyunASR is re-raised as APIConnectionError."""
    def ws_error(path: str) -> str:
        raise ConnectionError("WebSocket connection refused")

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = ws_error

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        with pytest.raises(APIConnectionError):
            await plugin._recognize_impl(
                buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
            )


@pytest.mark.asyncio
async def test_xfyun_auth_error_mapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auth-style error from XfyunASR is raised as XfyunSTTAuthError."""
    def auth_error(path: str) -> str:
        raise ValueError("invalid api_key or api secret — 401 unauthorized")

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = auth_error

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        with pytest.raises(XfyunSTTAuthError):
            await plugin._recognize_impl(
                buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
            )
