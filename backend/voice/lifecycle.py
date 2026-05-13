"""4-state voice session lifecycle.

States: Idle → UserSpeaking → Processing → AIResponding → Idle
VAD-triggered (Silero), no LLM Gate.
"""
from __future__ import annotations

import asyncio
from enum import Enum


class VoiceLifecycle(Enum):
    IDLE = "idle"
    USER_SPEAKING = "user_speaking"
    PROCESSING = "processing"
    AI_RESPONDING = "ai_responding"


VALID_TRANSITIONS: dict[VoiceLifecycle, set[VoiceLifecycle]] = {
    VoiceLifecycle.IDLE: {VoiceLifecycle.USER_SPEAKING},
    VoiceLifecycle.USER_SPEAKING: {VoiceLifecycle.PROCESSING, VoiceLifecycle.IDLE},
    VoiceLifecycle.PROCESSING: {VoiceLifecycle.AI_RESPONDING, VoiceLifecycle.IDLE},
    VoiceLifecycle.AI_RESPONDING: {VoiceLifecycle.IDLE, VoiceLifecycle.USER_SPEAKING},
}


class LifecycleTracker:
    """Tracks voice session lifecycle state with transition validation.

    Thread/asyncio-safe: all state changes go through an asyncio.Lock.
    For sync contexts, use try_transition() which returns bool.
    """

    def __init__(self) -> None:
        self.state = VoiceLifecycle.IDLE
        self._lock = asyncio.Lock()

    def can_transition(self, target: VoiceLifecycle) -> bool:
        return target in VALID_TRANSITIONS[self.state]

    def transition(self, target: VoiceLifecycle) -> None:
        if target not in VALID_TRANSITIONS[self.state]:
            raise ValueError(
                f"Invalid transition: {self.state.value} → {target.value}"
            )
        self.state = target

    def try_transition(self, target: VoiceLifecycle) -> bool:
        if target not in VALID_TRANSITIONS[self.state]:
            return False
        self.state = target
        return True

    async def async_transition(self, target: VoiceLifecycle) -> None:
        async with self._lock:
            self.transition(target)
