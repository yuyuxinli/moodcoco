from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_voice_entrypoint_uses_longer_vad_silence(monkeypatch: pytest.MonkeyPatch):
    import backend.voice.entrypoint as entrypoint

    calls: dict[str, object] = {}

    class _FakeRoom:
        name = "test-room"
        remote_participants: dict[str, object] = {}

        def on(self, event: str, callback: object) -> None:
            calls.setdefault("room_events", []).append(event)

    class _FakeCtx:
        room = _FakeRoom()

        async def connect(self) -> None:
            calls["connected"] = True

    class _FakeAgentSession:
        def __init__(self, **kwargs: object) -> None:
            calls["session_kwargs"] = kwargs
            self.input = None
            self._room_io = None

        async def start(self, **kwargs: object) -> None:
            calls["start_kwargs"] = kwargs

    def _fake_vad_load(**kwargs: object) -> object:
        calls["vad_kwargs"] = kwargs
        return object()

    monkeypatch.setattr(entrypoint._silero.VAD, "load", _fake_vad_load)
    monkeypatch.setattr(entrypoint._agent_stt, "StreamAdapter", lambda **kwargs: kwargs)
    monkeypatch.setattr(entrypoint, "XfyunSTTPlugin", lambda: object())
    monkeypatch.setattr(entrypoint, "MinimaxTTSPlugin", lambda: object())
    monkeypatch.setattr(entrypoint, "_build_slow_llm", lambda: object())
    monkeypatch.setattr(entrypoint, "VoiceBridgeAgent", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(entrypoint, "AgentSession", _FakeAgentSession)

    await entrypoint.voice_entrypoint(_FakeCtx())

    assert calls["connected"] is True
    assert calls["vad_kwargs"] == {"min_silence_duration": 1.2}


@pytest.mark.asyncio
async def test_voice_streaming_mode_keeps_vad_stt_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.voice.entrypoint as entrypoint

    calls: dict[str, object] = {}

    class _FakeRoom:
        name = "test-room"
        remote_participants: dict[str, object] = {}

        def on(self, event: str, callback: object) -> None:
            calls.setdefault("room_events", []).append(event)

    class _FakeCtx:
        room = _FakeRoom()

        async def connect(self) -> None:
            calls["connected"] = True

    class _FakeAgentSession:
        def __init__(self, **kwargs: object) -> None:
            calls["session_kwargs"] = kwargs
            self.input = None
            self._room_io = None

        async def start(self, **kwargs: object) -> None:
            calls["start_kwargs"] = kwargs

    def _fake_vad_load(**kwargs: object) -> object:
        calls["vad_kwargs"] = kwargs
        return "vad"

    def _fake_stream_adapter(**kwargs: object) -> dict[str, object]:
        calls["stream_adapter_kwargs"] = kwargs
        return kwargs

    def _unexpected_streaming_stt(**_kwargs: object) -> object:
        raise AssertionError("streaming STT must be opt-in")

    monkeypatch.setenv("VOICE_STREAMING_MODE", "true")
    monkeypatch.delenv("VOICE_STREAMING_STT_MODE", raising=False)
    monkeypatch.delenv("VOICE_STREAMING_TTS_MODE", raising=False)
    monkeypatch.setattr(entrypoint._silero.VAD, "load", _fake_vad_load)
    monkeypatch.setattr(entrypoint._agent_stt, "StreamAdapter", _fake_stream_adapter)
    monkeypatch.setattr(entrypoint, "XfyunSTTPlugin", lambda: "xfyun-stt")
    monkeypatch.setattr(entrypoint, "XfyunStreamingSTTPlugin", _unexpected_streaming_stt)
    monkeypatch.setattr(entrypoint, "MinimaxTTSPlugin", lambda: "minimax-tts")
    monkeypatch.setattr(entrypoint, "_build_slow_llm", lambda: "slow-llm")
    monkeypatch.setattr(entrypoint, "create_voice_streaming_client", lambda: "client")
    monkeypatch.setattr(entrypoint, "get_voice_streaming_model_name", lambda: "model")
    monkeypatch.setattr(
        entrypoint,
        "VoiceStreamingResponder",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(
        entrypoint,
        "StreamingVoiceBridgeAgent",
        lambda **kwargs: SimpleNamespace(kind="streaming-agent", **kwargs),
    )
    monkeypatch.setattr(entrypoint, "AgentSession", _FakeAgentSession)

    await entrypoint.voice_entrypoint(_FakeCtx())

    assert calls["vad_kwargs"] == {"min_silence_duration": 1.2}
    assert calls["stream_adapter_kwargs"] == {"stt": "xfyun-stt", "vad": "vad"}
    assert calls["session_kwargs"]["stt"] == {"stt": "xfyun-stt", "vad": "vad"}
    assert calls["start_kwargs"]["agent"].kind == "streaming-agent"
