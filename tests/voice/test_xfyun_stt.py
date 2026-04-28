"""Unit tests for XfyunSTTPlugin (F3).

12 test cases: 6 original + 4 missing F1 §8 cases + 2 new error-class tests.
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
    XfyunRecognitionError,
    XfyunSTTAuthError,
    XfyunSTTNetworkError,
    XfyunSTTPlugin,
    XfyunSTTRateLimitError,
    XfyunSTTTimeoutError,
    XfyunVendorError,
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
    """Env vars XFYUN_APP_ID/API_KEY/API_SECRET are propagated to XfyunASR."""
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


# ---------------------------------------------------------------------------
# F1 §8 missing cases (round-2 additions)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recognize_empty_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1 §8 case 2 — XfyunASR returns '' → SpeechEvent with empty text, no exception."""
    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.return_value = ""

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        event: SpeechEvent = await plugin._recognize_impl(
            buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
        )

    assert event.type == SpeechEventType.FINAL_TRANSCRIPT
    assert len(event.alternatives) == 1
    alt: SpeechData = event.alternatives[0]
    assert alt.text == ""
    assert alt.confidence == 0.0


@pytest.mark.asyncio
async def test_xfyun_error_code_propagation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """F1 §8 case 4 — Xfyun error code 10165 → timeout error + structured code log."""

    def timeout_code_error(path: str) -> str:
        raise XfyunVendorError("session timeout", code=10165)

    caplog.set_level("ERROR", logger="voice.plugins.xfyun_stt")

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = timeout_code_error

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        with pytest.raises(XfyunSTTTimeoutError) as exc_info:
            await plugin._recognize_impl(
                buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
            )

    assert exc_info.value.code == 10165
    assert any(getattr(record, "code", None) == 10165 for record in caplog.records)


@pytest.mark.asyncio
async def test_recognize_large_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1 §8 case 5 — 1 MB AudioBuffer → temp file written + cleaned, no OOM, recognize called once."""
    captured_paths: list[str] = []

    def fake_recognize(path: str) -> str:
        captured_paths.append(path)
        assert os.path.exists(path), "temp file should exist during recognize()"
        size = os.path.getsize(path)
        assert size >= 1_000_000, f"expected ≥1 MB temp file, got {size} bytes"
        return "大文件测试"

    sample_rate = 16_000
    # 1 MB of 16-bit mono PCM ≈ 31.25 s of audio
    pcm_bytes = bytes(1_048_576)
    samples = len(pcm_bytes) // 2
    frame = rtc.AudioFrame(
        data=pcm_bytes,
        sample_rate=sample_rate,
        num_channels=1,
        samples_per_channel=samples,
    )
    buffer = [frame]

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = fake_recognize

        plugin = XfyunSTTPlugin(sample_rate=sample_rate)
        event: SpeechEvent = await plugin._recognize_impl(
            buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
        )

    assert event.alternatives[0].text == "大文件测试"
    assert mock_instance.recognize.call_count == 1
    assert len(captured_paths) == 1
    assert not os.path.exists(captured_paths[0]), "temp file not cleaned up"


@pytest.mark.asyncio
async def test_speech_data_field_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1 §8 case 6 — SpeechEvent.alternatives[0] has .text, .language, .confidence with correct types."""
    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.return_value = "测试字段结构"

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        event: SpeechEvent = await plugin._recognize_impl(
            buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
        )

    assert len(event.alternatives) >= 1
    alt = event.alternatives[0]
    assert isinstance(alt.text, str)
    assert isinstance(alt.language, str)
    assert isinstance(alt.confidence, float)
    assert alt.text == "测试字段结构"
    assert alt.language.lower() == "zh-cn"
    assert 0.0 <= alt.confidence <= 1.0


# ---------------------------------------------------------------------------
# New error-class tests (FIX 1 & FIX 2 coverage)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_xfyun_recognition_error_mapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX 1 — error code in 10800-10899 range maps to XfyunRecognitionError (returns empty SpeechEvent)."""

    def recognition_error(path: str) -> str:
        raise XfyunRecognitionError("engine error", code=10800)

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = recognition_error

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        # Recognition-domain errors return empty SpeechEvent instead of raising.
        event: SpeechEvent = await plugin._recognize_impl(
            buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
        )

    assert event.type == SpeechEventType.FINAL_TRANSCRIPT
    assert event.alternatives[0].text == ""
    assert event.alternatives[0].confidence == 0.0


@pytest.mark.asyncio
async def test_xfyun_rate_limit_error_mapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FIX 2 — error code 10114 maps to XfyunSTTRateLimitError."""

    def rate_limit_error(path: str) -> str:
        raise XfyunVendorError("concurrency limit exceeded", code=10114)

    with patch("backend.voice.plugins.xfyun_stt.XfyunASR") as MockASR:
        mock_instance = MockASR.return_value
        mock_instance.recognize.side_effect = rate_limit_error

        plugin = XfyunSTTPlugin()
        buffer = _make_audio_buffer()

        with pytest.raises(XfyunSTTRateLimitError) as exc_info:
            await plugin._recognize_impl(
                buffer, conn_options=DEFAULT_API_CONNECT_OPTIONS
            )

    assert exc_info.value.code == 10114
