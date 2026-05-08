"""Typed events for browser-visible voice streaming state."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

VoiceStreamEventType = Literal[
    "user_partial",
    "user_final",
    "coco_delta",
    "coco_sentence",
    "tts_started",
    "tts_done",
    "turn_interrupted",
    "stream_error",
]

_VALID_EVENT_TYPES: set[str] = {
    "user_partial",
    "user_final",
    "coco_delta",
    "coco_sentence",
    "tts_started",
    "tts_done",
    "turn_interrupted",
    "stream_error",
}


@dataclass(slots=True)
class VoiceStreamEvent:
    type: VoiceStreamEventType
    session_id: str
    turn_id: str
    text: str = ""
    is_final: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in _VALID_EVENT_TYPES:
            raise ValueError(f"unknown voice stream event type: {self.type}")

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "type": self.type,
                "session_id": self.session_id,
                "turn_id": self.turn_id,
                "text": self.text,
                "is_final": self.is_final,
                "meta": self.meta,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
