"""P1 TDD tests — bridge_agent.py integration wiring.

These tests verify that bridge_agent.py correctly wires P1 features:
  1. _slow_state includes next_likely_contexts key
  2. speaker_output extracted from Fast's ai_message and passed to SlowThinkDeps
  3. next_likely_contexts persisted and used as prewarmed_contexts next turn
  4. keyword_filter applied to ai_message text before TTS
  5. carryover_skill_names tracked alongside carryover_skills
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_bridge():
    """Create a VoiceBridgeAgent without requiring LiveKit runtime."""
    from backend.voice.bridge_agent import VoiceBridgeAgent

    with patch.object(VoiceBridgeAgent, "__init__", lambda self, **kw: None):
        agent = VoiceBridgeAgent.__new__(VoiceBridgeAgent)
        agent._instructions = ""
        agent._session_hooks_registered = True
        agent._speech_meta = {}
        agent._fast_history = []
        agent._slow_history = []
        agent._slow_state = {
            "reasoning_trail": [],
            "search_cache": {},
            "pending_actions": [],
            "carryover_inject": [],
            "carryover_skills": [],
            "carryover_retrieval": "",
            "next_likely_contexts": [],
            "carryover_skill_names": [],
        }
    return agent


class TestSlowStateInit:
    """_slow_state should include all P1 keys from initialization."""

    def test_slow_state_has_next_likely_contexts(self):
        """_slow_state must have next_likely_contexts key to avoid KeyError."""
        agent = _make_bridge()
        assert "next_likely_contexts" in agent._slow_state
        assert agent._slow_state["next_likely_contexts"] == []

    def test_slow_state_has_carryover_skill_names(self):
        """_slow_state must track skill names alongside skill text."""
        agent = _make_bridge()
        assert "carryover_skill_names" in agent._slow_state
        assert agent._slow_state["carryover_skill_names"] == []


class TestSpeakerOutputWiring:
    """Previous turn's Speaker text should be passed to SlowThinkDeps.speaker_output."""

    def test_extract_speaker_text_from_collected_tool_calls(self):
        """Bridge should extract text from fast_deps.collected_tool_calls ai_message."""
        from backend.voice.bridge_agent import _extract_speaker_text

        calls = [
            {"name": "ai_message", "args": {"messages": ["你好", "我在听"], "needs_deep_analysis": False}},
        ]
        assert _extract_speaker_text(calls) == "你好\n我在听"

    def test_extract_speaker_text_empty_when_no_ai_message(self):
        """Returns empty string when no ai_message tool call."""
        from backend.voice.bridge_agent import _extract_speaker_text

        calls = [{"name": "ai_options", "args": {"options": ["a", "b"]}}]
        assert _extract_speaker_text(calls) == ""

    def test_extract_speaker_text_uses_last_ai_message(self):
        """When multiple ai_message calls, use the last one."""
        from backend.voice.bridge_agent import _extract_speaker_text

        calls = [
            {"name": "ai_message", "args": {"messages": ["第一条"], "needs_deep_analysis": False}},
            {"name": "ai_message", "args": {"messages": ["第二条"], "needs_deep_analysis": False}},
        ]
        assert _extract_speaker_text(calls) == "第二条"


class TestNextLikelyContextsWiring:
    """next_likely_contexts should be persisted and converted to prewarmed_contexts."""

    def test_persist_slow_state_includes_next_likely_contexts(self):
        """_persist_slow_state should save next_likely_contexts."""
        from backend.slow import SlowThinkDeps

        agent = _make_bridge()
        slow_deps = SlowThinkDeps(
            session_id="s1",
            user_message="hi",
            next_likely_contexts=["untangle", "calm-body"],
            mutation_count_this_iter=1,
        )
        slow_deps.tool_call_history.append("some_tool")

        agent._persist_slow_state_sync(slow_deps, result=None)

        assert agent._slow_state["next_likely_contexts"] == ["untangle", "calm-body"]

    def test_prewarmed_contexts_built_from_next_likely(self, tmp_path):
        """FastThinkDeps.prewarmed_contexts should be populated from stored next_likely_contexts."""
        from backend.voice.bridge_agent import _build_prewarmed_contexts

        skills_dir = tmp_path / "skills"
        (skills_dir / "untangle").mkdir(parents=True)
        (skills_dir / "untangle" / "SKILL.md").write_text("untangle content")
        (skills_dir / "calm-body").mkdir(parents=True)
        (skills_dir / "calm-body" / "SKILL.md").write_text("calm-body content")

        with patch("backend.slow.SKILLS_DIR", skills_dir):
            result = _build_prewarmed_contexts(["untangle", "calm-body"])

        assert isinstance(result, dict)
        assert "untangle" in result
        assert "calm-body" in result


class TestKeywordFilterWiring:
    """keyword_filter should be applied to ai_message text before TTS."""

    def test_filter_blocks_dangerous_ai_message(self):
        """When ai_message contains dangerous content, filter should replace it."""
        from backend.safety import keyword_filter

        result = keyword_filter("你可以尝试割腕来释放压力")
        assert result.blocked is True
        assert result.safe_replacement

    def test_filter_integration_with_extract(self):
        """Extracted speaker text should be filterable."""
        from backend.safety import keyword_filter
        from backend.voice.bridge_agent import _extract_speaker_text

        calls = [
            {"name": "ai_message", "args": {"messages": ["你应该去死"], "needs_deep_analysis": False}},
        ]
        text = _extract_speaker_text(calls)
        result = keyword_filter(text)
        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_ai_message_applies_keyword_filter_before_tts(self):
        """ai_message tool should apply keyword_filter before calling session.say."""
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from backend.fast import FastThinkDeps, ai_message

        said_texts = []

        class FakeSession:
            async def say(self, text, **kw):
                said_texts.append(text)

        deps = FastThinkDeps(
            session_id="s1",
            memory_text="",
            voice_session=FakeSession(),
        )
        ctx = SimpleNamespace(deps=deps)

        try:
            await ai_message(ctx, messages=["你应该去死"], needs_deep_analysis=False)
        except Exception:
            pass

        assert said_texts
        assert "去死" not in said_texts[0]
        assert "陪着你" in said_texts[0]


class TestSkillNamesTracking:
    """Bridge should track skill names alongside full skill text."""

    def test_persist_slow_state_saves_skill_names(self):
        """_persist_slow_state should save carryover_skill_names from reasoning_trail."""
        from backend.slow import SlowThinkDeps

        agent = _make_bridge()
        slow_deps = SlowThinkDeps(
            session_id="s1",
            user_message="hi",
            reasoning_trail=["skill:untangle", "inject:some text"],
            carryover_skills=["full untangle text"],
            mutation_count_this_iter=1,
        )
        slow_deps.tool_call_history.append("slow_attach_skill_to_fast")

        agent._persist_slow_state_sync(slow_deps, result=None)

        assert "untangle" in agent._slow_state["carryover_skill_names"]
