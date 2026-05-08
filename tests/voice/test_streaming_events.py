from __future__ import annotations

import json

from backend.voice.streaming_events import VoiceStreamEvent


def test_voice_stream_event_serializes_minimal_payload() -> None:
    event = VoiceStreamEvent(
        type="user_partial",
        session_id="room-1",
        turn_id="turn-1",
        text="我今天",
        is_final=False,
    )

    payload = event.to_json_bytes()
    decoded = json.loads(payload.decode("utf-8"))

    assert decoded == {
        "type": "user_partial",
        "session_id": "room-1",
        "turn_id": "turn-1",
        "text": "我今天",
        "is_final": False,
        "meta": {},
    }


def test_voice_stream_event_rejects_unknown_type() -> None:
    try:
        VoiceStreamEvent(
            type="unknown",
            session_id="room-1",
            turn_id="turn-1",
            text="x",
        )
    except ValueError as exc:
        assert "unknown voice stream event type" in str(exc)
    else:
        raise AssertionError("expected ValueError")
