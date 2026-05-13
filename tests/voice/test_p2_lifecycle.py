"""P2 TDD tests — 4-state voice lifecycle and naming aliases.

Voice session lifecycle: Idle → UserSpeaking → Processing → AIResponding
Naming: Speaker (fast) + Thinker (slow) aliases for public API.
"""
from __future__ import annotations

import pytest


class TestVoiceLifecycleEnum:
    """4-state lifecycle enum for voice sessions."""

    def test_lifecycle_enum_exists(self):
        """VoiceLifecycle enum should be importable from voice module."""
        from backend.voice.lifecycle import VoiceLifecycle

        assert hasattr(VoiceLifecycle, "IDLE")
        assert hasattr(VoiceLifecycle, "USER_SPEAKING")
        assert hasattr(VoiceLifecycle, "PROCESSING")
        assert hasattr(VoiceLifecycle, "AI_RESPONDING")

    def test_lifecycle_has_four_states(self):
        """Exactly 4 states, no more."""
        from backend.voice.lifecycle import VoiceLifecycle

        assert len(VoiceLifecycle) == 4

    def test_lifecycle_default_is_idle(self):
        """Default state should be IDLE."""
        from backend.voice.lifecycle import VoiceLifecycle

        assert VoiceLifecycle.IDLE.value == "idle"

    def test_lifecycle_valid_transitions(self):
        """Each state should know its valid next states."""
        from backend.voice.lifecycle import VALID_TRANSITIONS, VoiceLifecycle

        assert VoiceLifecycle.USER_SPEAKING in VALID_TRANSITIONS[VoiceLifecycle.IDLE]
        assert VoiceLifecycle.PROCESSING in VALID_TRANSITIONS[VoiceLifecycle.USER_SPEAKING]
        assert VoiceLifecycle.AI_RESPONDING in VALID_TRANSITIONS[VoiceLifecycle.PROCESSING]
        assert VoiceLifecycle.IDLE in VALID_TRANSITIONS[VoiceLifecycle.AI_RESPONDING]

    def test_lifecycle_no_skip_transition(self):
        """Cannot skip states (e.g., IDLE → PROCESSING is invalid)."""
        from backend.voice.lifecycle import VALID_TRANSITIONS, VoiceLifecycle

        assert VoiceLifecycle.PROCESSING not in VALID_TRANSITIONS[VoiceLifecycle.IDLE]
        assert VoiceLifecycle.AI_RESPONDING not in VALID_TRANSITIONS[VoiceLifecycle.IDLE]

    def test_lifecycle_tracker_transition(self):
        """LifecycleTracker should enforce valid transitions."""
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        assert tracker.state == VoiceLifecycle.IDLE

        tracker.transition(VoiceLifecycle.USER_SPEAKING)
        assert tracker.state == VoiceLifecycle.USER_SPEAKING

    def test_lifecycle_tracker_rejects_invalid(self):
        """LifecycleTracker should raise on invalid transition."""
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        with pytest.raises(ValueError, match="Invalid transition"):
            tracker.transition(VoiceLifecycle.PROCESSING)

    def test_lifecycle_tracker_try_transition_returns_bool(self):
        """try_transition should return True on success, False on invalid."""
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        assert tracker.try_transition(VoiceLifecycle.USER_SPEAKING) is True
        assert tracker.state == VoiceLifecycle.USER_SPEAKING
        assert tracker.try_transition(VoiceLifecycle.IDLE) is True
        assert tracker.try_transition(VoiceLifecycle.AI_RESPONDING) is False

    def test_lifecycle_tracker_can_transition(self):
        """can_transition should check without changing state."""
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        assert tracker.can_transition(VoiceLifecycle.USER_SPEAKING) is True
        assert tracker.can_transition(VoiceLifecycle.PROCESSING) is False
        assert tracker.state == VoiceLifecycle.IDLE

    @pytest.mark.asyncio
    async def test_lifecycle_tracker_async_transition(self):
        """async_transition should be safe under asyncio.Lock."""
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        await tracker.async_transition(VoiceLifecycle.USER_SPEAKING)
        assert tracker.state == VoiceLifecycle.USER_SPEAKING


class TestNamingAliases:
    """Speaker/Thinker aliases for public API."""

    def test_speaker_agent_alias(self):
        """speaker_agent should be an alias for fast_agent."""
        from backend.fast import fast_agent, speaker_agent

        assert speaker_agent is fast_agent

    def test_thinker_agent_alias(self):
        """thinker_agent should be an alias for slow_agent."""
        from backend.slow import slow_agent, thinker_agent

        assert thinker_agent is slow_agent

    def test_speaker_deps_alias(self):
        """SpeakerDeps should be an alias for FastThinkDeps."""
        from backend.fast import FastThinkDeps, SpeakerDeps

        assert SpeakerDeps is FastThinkDeps

    def test_thinker_deps_alias(self):
        """ThinkerDeps should be an alias for SlowThinkDeps."""
        from backend.slow import SlowThinkDeps, ThinkerDeps

        assert ThinkerDeps is SlowThinkDeps
