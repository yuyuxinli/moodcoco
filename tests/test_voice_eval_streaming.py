from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_voice_eval():
    path = Path(__file__).resolve().parents[1] / ".evolve" / "voice_eval.py"
    spec = importlib.util.spec_from_file_location("voice_eval", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_voice_eval_summarizes_streaming_metrics() -> None:
    voice_eval = _load_voice_eval()
    events = [
        {
            "timestamp": "2026-05-08T10:00:00+00:00",
            "message": "registered worker",
        },
        {
            "timestamp": "2026-05-08T10:00:00+00:00",
            "message": "received job request",
        },
        {
            "timestamp": "2026-05-08T10:00:00+00:00",
            "message": "voice_session_started",
        },
        {
            "timestamp": "2026-05-08T10:00:00+00:00",
            "message": "voice_session_starting",
            "streaming_mode_enabled": True,
            "tts_mode": "minimax_ws",
            "voice_tts_sink": "pcm_audio_source",
        },
        {
            "timestamp": "2026-05-08T10:00:01+00:00",
            "message": "voice_streaming_stt_started",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:01.200000+00:00",
            "message": "voice_stream_event_published",
            "event_type": "user_partial",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:02+00:00",
            "message": "voice_stream_event_published",
            "event_type": "user_final",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:03+00:00",
            "message": "voice_stream_event_published",
            "event_type": "coco_sentence",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:03.100000+00:00",
            "message": "voice_streaming_tts_first_audio",
            "turn_id": "turn-a",
            "tts_mode": "minimax_ws",
            "voice_tts_sink": "pcm_audio_source",
        },
        {
            "timestamp": "2026-05-08T10:00:03.500000+00:00",
            "message": "voice_stream_event_published",
            "event_type": "turn_interrupted",
            "turn_id": "turn-a",
        },
    ]

    summary = voice_eval.summarize_agent(events)

    assert summary["streaming"]["streaming_mode_enabled"] is True
    assert summary["streaming"]["tts_mode"] == "minimax_ws"
    assert summary["streaming"]["voice_tts_sink"] == "pcm_audio_source"
    assert summary["streaming"]["barge_in_success"] is True
    assert summary["latency_ms"]["time_to_user_partial_ms"]["p50"] == 200
    assert summary["latency_ms"]["time_to_user_final_ms"]["p50"] == 1000
    assert summary["latency_ms"]["time_to_first_coco_sentence_ms"]["p50"] == 1000
    assert summary["latency_ms"]["time_to_first_audio_ms"]["p50"] == 1100
