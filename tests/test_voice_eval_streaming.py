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
            "timestamp": "2026-05-08T10:00:01.500000+00:00",
            "message": "voice_streaming_stt_speech_started",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:01.700000+00:00",
            "message": "voice_stream_event_published",
            "event_type": "user_partial",
            "turn_id": "turn-a",
            "text": "",
        },
        {
            "timestamp": "2026-05-08T10:00:01.900000+00:00",
            "message": "voice_stream_event_published",
            "event_type": "user_partial",
            "turn_id": "turn-a",
            "text": "我",
        },
        {
            "timestamp": "2026-05-08T10:00:02.100000+00:00",
            "message": "voice_streaming_stt_endpointed",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:02.300000+00:00",
            "message": "voice_stream_event_published",
            "event_type": "user_final",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:02.400000+00:00",
            "message": "voice_llm_request_started",
            "turn_id": "turn-a",
            "model": "gpt-4o-mini",
        },
        {
            "timestamp": "2026-05-08T10:00:02.900000+00:00",
            "message": "voice_llm_first_token",
            "turn_id": "turn-a",
            "model": "gpt-4o-mini",
        },
        {
            "timestamp": "2026-05-08T10:00:03.250000+00:00",
            "message": "voice_llm_first_sentence",
            "turn_id": "turn-a",
            "model": "gpt-4o-mini",
        },
        {
            "timestamp": "2026-05-08T10:00:03.300000+00:00",
            "message": "voice_stream_event_published",
            "event_type": "coco_sentence",
            "turn_id": "turn-a",
        },
        {
            "timestamp": "2026-05-08T10:00:03.400000+00:00",
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
    assert summary["latency_ms"]["time_to_user_partial_ms"]["p50"] == 400
    assert summary["latency_ms"]["time_to_user_final_ms"]["p50"] == 800
    assert summary["latency_ms"]["stt_stream_start_to_user_final_ms"]["p50"] == 1300
    assert summary["latency_ms"]["stt_first_partial_to_user_final_ms"]["p50"] == 400
    assert summary["latency_ms"]["stt_speech_to_endpoint_ms"]["p50"] == 600
    assert summary["latency_ms"]["stt_endpoint_to_user_final_ms"]["p50"] == 200
    assert summary["latency_ms"]["user_final_to_llm_request_ms"]["p50"] == 100
    assert summary["latency_ms"]["llm_request_to_first_token_ms"]["p50"] == 500
    assert summary["latency_ms"]["llm_first_token_to_first_sentence_ms"]["p50"] == 350
    assert summary["latency_ms"]["llm_first_sentence_to_first_audio_ms"]["p50"] == 150
    assert summary["latency_ms"]["time_to_first_coco_sentence_ms"]["p50"] == 1000
    assert summary["latency_ms"]["time_to_first_audio_ms"]["p50"] == 1100
