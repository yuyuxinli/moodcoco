"""LiveKit data-channel helpers for voice streaming events."""
from __future__ import annotations

import inspect
import logging
from typing import Any

from backend.voice.streaming_events import VoiceStreamEvent

logger = logging.getLogger("voice.livekit_data")


async def publish_voice_event(room: Any, event: VoiceStreamEvent) -> None:
    """Publish a voice event without breaking the audio path if unavailable."""
    local_participant = getattr(room, "local_participant", None)
    publish_data = getattr(local_participant, "publish_data", None)
    if not callable(publish_data):
        logger.warning(
            "voice_event_publish_unavailable",
            extra={"event_type": event.type, "session_id": event.session_id},
        )
        return

    try:
        result = publish_data(event.to_json_bytes(), reliable=True, topic="voice-stream")
    except TypeError:
        result = publish_data(event.to_json_bytes(), reliable=True)
    if inspect.isawaitable(result):
        await result
    logger.info(
        "voice_stream_event_published",
        extra={
            "event_type": event.type,
            "session_id": event.session_id,
            "turn_id": event.turn_id,
            "text_len": len(event.text),
            "is_final": event.is_final,
            "tts_mode": event.meta.get("tts_mode"),
            "voice_tts_sink": event.meta.get("voice_tts_sink"),
        },
    )
