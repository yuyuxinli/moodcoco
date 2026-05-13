"""Multi-turn voice integration tests — VoiceBridgeAgent E2E state flow.

Verifies end-to-end state flow through VoiceBridgeAgent.on_user_turn_completed():
  1. Cross-turn carryover: Slow writes inject/skill/retrieval → next-turn Fast reads
  2. speaker_output propagation: Fast speaks → Slow receives for L3 review
  3. _slow_state persistence, LRU limits (inject≤3, skills≤2), skill_names extraction
  4. keyword_filter in voice ai_message path
  5. ai_safety_brake voice delivery (with already_spoke fix)
  6. Lifecycle state machine transitions
  7. L3 safety correction loop (cross-turn)
  8. Slow timeout/error recovery
  9. StreamingVoiceBridgeAgent multi-turn (keyword_filter per sentence, turn interruption)
 10. _build_prewarmed_contexts real file I/O
 11. Fast failure + already_spoke recovery across turns
"""
from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from livekit.agents import StopResponse


# ── Shared helpers ──────────────────────────────────────────────────────────


def _make_chat_context() -> MagicMock:
    ctx = MagicMock()
    ctx.messages = []

    def _add_message(*, role: str, content: str, interrupted: bool = False) -> MagicMock:
        msg = MagicMock()
        msg.role = role
        msg.content = [content]
        msg.text_content = content
        ctx.messages.append({"role": role, "content": content})
        return msg

    ctx.add_message = _add_message
    return ctx


def _make_user_message(text: str = "我最近压力很大") -> MagicMock:
    msg = MagicMock()
    msg.text_content = text
    msg.content = [text]
    return msg


def _make_agent():
    from backend.voice.bridge_agent import VoiceBridgeAgent

    agent = VoiceBridgeAgent(instructions="test")
    session_mock = MagicMock()

    def _say(source, *args, **kwargs):
        if hasattr(source, "__aiter__"):

            async def _drain():
                async for _ in source:
                    pass

            asyncio.create_task(_drain())
        return MagicMock()

    session_mock.say = MagicMock(side_effect=_say)
    room_mock = MagicMock()
    room_mock.name = "integration-test-room"
    session_mock.room = room_mock
    activity_mock = MagicMock()
    activity_mock.session = session_mock
    agent._get_activity_or_raise = MagicMock(return_value=activity_mock)
    return agent


class _BridgeRunResult:
    def __init__(self, messages=None):
        self._messages = messages or []
        self.output = "ok"

    def all_messages(self):
        return self._messages


async def _run_turn(agent, text="我最近压力很大"):
    ctx = _make_chat_context()
    msg = _make_user_message(text)
    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, msg), timeout=5.0)
    await asyncio.sleep(0.05)


def _prewarm_stub(ctx_list):
    if not ctx_list:
        return {}
    return {name.split("(")[0]: f"prewarmed-{name.split('(')[0]}" for name in ctx_list}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Cross-turn carryover — 3-turn flow
# ═══════════════════════════════════════════════════════════════════════════════


class TestCrossTurnCarryover:
    """Slow writes carryover on Turn N → Fast reads it on Turn N+1."""

    @pytest.mark.asyncio
    async def test_three_turn_state_flow(self, monkeypatch):
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        fast_deps_log: list = []
        turn = {"n": 0}

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            reply = f"reply-{turn['n']}"
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": [reply], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say(reply, add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            n = turn["n"]
            deps.carryover_inject.append(f"inject-{n}")
            del deps.carryover_inject[:-3]
            deps.reasoning_trail.append(f"inject:hint-{n}")

            if n == 0:
                deps.carryover_skills.append("skill-content-listen")
                deps.reasoning_trail.append("skill:listen")
                deps.carryover_retrieval = "retrieval-0"
                deps.next_likely_contexts = ["untangle(困惑)"]
            elif n == 1:
                deps.carryover_skills.append("skill-content-calm-body")
                deps.reasoning_trail.append("skill:calm-body")
                deps.carryover_retrieval = "retrieval-1"
                deps.next_likely_contexts = ["face-decision(选择)"]

            deps.mutation_count_this_iter += 1
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()

        with patch(
            "backend.voice.bridge_agent._build_prewarmed_contexts",
            side_effect=_prewarm_stub,
        ):
            turn["n"] = 0
            await _run_turn(agent, "我很烦")
            turn["n"] = 1
            await _run_turn(agent, "怎么办")
            turn["n"] = 2
            await _run_turn(agent, "还是不行")

        # Turn 0: first turn — empty carryover
        t0 = fast_deps_log[0]
        assert t0.dynamic_inject == []
        assert t0.skill_bundle == []
        assert t0.retrieval_block == ""
        assert t0.prewarmed_contexts == {}
        assert t0.skill_names == []

        # Turn 1: receives Turn 0's carryover
        t1 = fast_deps_log[1]
        assert "inject-0" in t1.dynamic_inject
        assert "skill-content-listen" in t1.skill_bundle
        assert t1.retrieval_block == "retrieval-0"
        assert "untangle" in t1.prewarmed_contexts
        assert "listen" in t1.skill_names

        # Turn 2: receives Turn 1's carryover
        t2 = fast_deps_log[2]
        assert "inject-1" in t2.dynamic_inject
        assert "skill-content-calm-body" in t2.skill_bundle
        assert t2.retrieval_block == "retrieval-1"
        assert "face-decision" in t2.prewarmed_contexts
        assert "calm-body" in t2.skill_names

    @pytest.mark.asyncio
    async def test_inject_lru_limit_three(self, monkeypatch):
        """carryover_inject truncated to most recent 3 entries."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        fast_deps_log: list = []
        turn = {"n": 0}

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": ["ok"], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say("ok", add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.carryover_inject.append(f"a-{turn['n']}")
            deps.carryover_inject.append(f"b-{turn['n']}")
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            for i in range(4):
                turn["n"] = i
                await _run_turn(agent, f"msg-{i}")

        # After 4 turns, _persist_slow_state_sync applies [-3:]
        t3 = fast_deps_log[3]
        assert len(t3.dynamic_inject) <= 3

    @pytest.mark.asyncio
    async def test_skills_lru_limit_two(self, monkeypatch):
        """carryover_skills truncated to most recent 2 entries."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        fast_deps_log: list = []
        turn = {"n": 0}

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": ["ok"], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say("ok", add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.carryover_skills.append(f"skill-{turn['n']}")
            deps.reasoning_trail.append(f"skill:s{turn['n']}")
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            for i in range(4):
                turn["n"] = i
                await _run_turn(agent, f"msg-{i}")

        t3 = fast_deps_log[3]
        assert len(t3.skill_bundle) <= 2

    @pytest.mark.asyncio
    async def test_skill_names_extracted_from_reasoning_trail(self, monkeypatch):
        """skill_names populated from reasoning_trail 'skill:' entries via _extract_skill_names."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        fast_deps_log: list = []

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": ["ok"], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say("ok", add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.reasoning_trail.extend(
                ["skill:listen", "inject:hint", "skill:untangle", "predict:calm-body"]
            )
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "Turn 0")
            await _run_turn(agent, "Turn 1")

        t1 = fast_deps_log[1]
        assert "listen" in t1.skill_names
        assert "untangle" in t1.skill_names
        assert "calm-body" not in t1.skill_names  # predict: prefix, not skill:


# ═══════════════════════════════════════════════════════════════════════════════
# 2. speaker_output propagation — Fast speaks → Slow receives for L3 review
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpeakerOutputPropagation:
    """Fast speaks on Turn N → Slow receives speaker_output on Turn N+1."""

    @pytest.mark.asyncio
    async def test_speaker_output_flows_across_turns(self, monkeypatch):
        """agent._last_speaker_text carries Turn N fast output to Turn N+1 slow deps."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        slow_speaker_at_creation: list[str] = []
        turn = {"n": 0}

        async def _fake_fast(user_msg, *, deps, message_history=None):
            reply = f"speaker-text-{turn['n']}"
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": [reply], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say(reply, add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        assert agent._last_speaker_text == ""

        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            turn["n"] = 0
            await _run_turn(agent, "Turn 0")

        assert agent._last_speaker_text == "speaker-text-0"

        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            turn["n"] = 1
            await _run_turn(agent, "Turn 1")

        assert agent._last_speaker_text == "speaker-text-1"

    @pytest.mark.asyncio
    async def test_last_speaker_text_persisted_on_agent(self, monkeypatch):
        """agent._last_speaker_text is updated after each turn for next-turn L3 review."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        async def _fake_fast(user_msg, *, deps, message_history=None):
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": ["我听到你了"], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say("我听到你了", add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        assert agent._last_speaker_text == ""

        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "你好")

        assert agent._last_speaker_text == "我听到你了"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. keyword_filter in voice ai_message path
# ═══════════════════════════════════════════════════════════════════════════════


class TestKeywordFilterVoicePath:
    """keyword_filter applied before session.say in the voice ai_message tool."""

    @pytest.mark.asyncio
    async def test_dangerous_text_filtered_before_say(self, monkeypatch):
        import backend.fast as fast_mod
        import backend.slow as slow_mod
        from backend.safety import keyword_filter

        dangerous_text = "根据分析，你可能患有抑郁症"
        filter_result = keyword_filter(dangerous_text)
        assert filter_result.blocked

        async def _fake_fast(user_msg, *, deps, message_history=None):
            from backend.safety import keyword_filter as kf

            result = kf(dangerous_text)
            spoken = result.safe_replacement if result.blocked else dangerous_text
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": [dangerous_text], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say(spoken, add_to_chat_ctx=True)
            from backend.fast import VoiceAiMessageDelivered

            raise VoiceAiMessageDelivered("delivered")

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "我很焦虑")

        say_calls = agent.session.say.call_args_list
        spoken_texts = [call.args[0] for call in say_calls if call.args]
        assert filter_result.safe_replacement in spoken_texts
        assert dangerous_text not in spoken_texts

    @pytest.mark.asyncio
    async def test_normal_text_passes_through(self, monkeypatch):
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        normal_text = "我听到你的感受了，能多说说吗？"

        async def _fake_fast(user_msg, *, deps, message_history=None):
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": [normal_text], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say(normal_text, add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "我最近不太好")

        agent.session.say.assert_called_once_with(normal_text, add_to_chat_ctx=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ai_safety_brake voice delivery
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafetyBrakeVoiceDelivery:
    """ai_safety_brake triggers session.say and bridge handles VoiceAiMessageDelivered."""

    @pytest.mark.asyncio
    async def test_safety_brake_speaks_once_no_fallback(self, monkeypatch):
        """After already_spoke fix, safety brake should NOT trigger fallback say."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        safety_text = "你现在安全的。如果你有自伤想法，请拨打生命热线 400-161-9995。"

        async def _fake_fast(user_msg, *, deps, message_history=None):
            deps.collected_tool_calls.append(
                {
                    "name": "ai_safety_brake",
                    "args": {"risk_level": "high", "response": safety_text},
                }
            )
            deps.voice_session.say(safety_text, add_to_chat_ctx=True)
            from backend.fast import VoiceAiMessageDelivered

            raise VoiceAiMessageDelivered("voice safety_brake delivered")

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "我想死")

        # With the already_spoke fix, session.say should be called exactly once
        assert agent.session.say.call_count == 1
        agent.session.say.assert_called_once_with(safety_text, add_to_chat_ctx=True)

    @pytest.mark.asyncio
    async def test_safety_brake_with_ai_message_also_works(self, monkeypatch):
        """If both ai_message and ai_safety_brake are called, no fallback fires."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        msg_text = "我听到你说的了。"
        safety_text = "你值得被帮助。"

        async def _fake_fast(user_msg, *, deps, message_history=None):
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": [msg_text], "needs_deep_analysis": True},
                }
            )
            deps.voice_session.say(msg_text, add_to_chat_ctx=True)
            deps.collected_tool_calls.append(
                {
                    "name": "ai_safety_brake",
                    "args": {"risk_level": "medium", "response": safety_text},
                }
            )
            deps.voice_session.say(safety_text, add_to_chat_ctx=True)
            from backend.fast import VoiceAiMessageDelivered

            raise VoiceAiMessageDelivered("delivered")

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "我不想活了")

        # Two say calls (ai_message + safety_brake), but no fallback (total=2 not 3)
        assert agent.session.say.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Lifecycle state machine
# ═══════════════════════════════════════════════════════════════════════════════


class TestLifecycleTransitions:
    """VoiceLifecycle 4-state machine transitions."""

    def test_valid_idle_to_user_speaking(self):
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        assert tracker.state == VoiceLifecycle.IDLE
        tracker.transition(VoiceLifecycle.USER_SPEAKING)
        assert tracker.state == VoiceLifecycle.USER_SPEAKING

    def test_invalid_idle_to_ai_responding(self):
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        with pytest.raises(ValueError, match="Invalid transition"):
            tracker.transition(VoiceLifecycle.AI_RESPONDING)

    def test_full_cycle(self):
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        tracker.transition(VoiceLifecycle.USER_SPEAKING)
        tracker.transition(VoiceLifecycle.PROCESSING)
        tracker.transition(VoiceLifecycle.AI_RESPONDING)
        tracker.transition(VoiceLifecycle.IDLE)
        assert tracker.state == VoiceLifecycle.IDLE

    def test_try_transition_returns_false_on_invalid(self):
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        assert tracker.try_transition(VoiceLifecycle.PROCESSING) is False
        assert tracker.state == VoiceLifecycle.IDLE

    def test_barge_in_ai_responding_to_user_speaking(self):
        from backend.voice.lifecycle import LifecycleTracker, VoiceLifecycle

        tracker = LifecycleTracker()
        tracker.transition(VoiceLifecycle.USER_SPEAKING)
        tracker.transition(VoiceLifecycle.PROCESSING)
        tracker.transition(VoiceLifecycle.AI_RESPONDING)
        tracker.transition(VoiceLifecycle.USER_SPEAKING)
        assert tracker.state == VoiceLifecycle.USER_SPEAKING


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Slow fallback inject when no mutations made
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlowFallbackInject:
    """When Slow makes no mutations, bridge injects fallback hint."""

    @pytest.mark.asyncio
    async def test_no_mutation_gets_fallback_inject(self, monkeypatch):
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        fast_deps_log: list = []

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": ["ok"], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say("ok", add_to_chat_ctx=True)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            # Deliberately make NO mutations
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "Turn 0")
            await _run_turn(agent, "Turn 1")

        # Turn 1 should have the fallback inject from Turn 0's unmutated slow
        t1 = fast_deps_log[1]
        assert len(t1.dynamic_inject) >= 1
        assert any("Thinker" in inj or "Speaker" in inj for inj in t1.dynamic_inject)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. L3 Safety Correction Loop (cross-turn)
# ═══════════════════════════════════════════════════════════════════════════════


class TestL3SafetyCorrectionLoop:
    """Turn N Fast says something unsafe → Turn N+1 Slow reviews → injects correction → Turn N+2 Fast receives it."""

    @pytest.mark.asyncio
    async def test_unsafe_speaker_triggers_correction_next_turn(self, monkeypatch):
        import backend.fast as fast_mod
        import backend.slow as slow_mod
        from backend.slow import SAFETY_REVIEW_PATTERNS

        fast_deps_log: list = []
        turn = {"n": 0}

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            n = turn["n"]
            if n == 0:
                text = "你可能患有抑郁症，建议去看医生。"
            else:
                text = f"正常回复-{n}"
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": [text], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say(text, add_to_chat_ctx=True)
            await asyncio.sleep(0)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            output = deps.speaker_output
            if output.strip():
                issues = []
                for category, patterns in SAFETY_REVIEW_PATTERNS:
                    for pattern in patterns:
                        if re.search(re.escape(pattern), output, re.DOTALL):
                            issues.append(f"{category}: '{pattern}'")
                if issues:
                    correction = (
                        f"上轮 Speaker 输出有安全问题({'; '.join(issues)})。"
                        "下轮避免诊断、替用户做决定、对不在场的人做动机判断。"
                    )
                    deps.carryover_inject.append(correction)
                    del deps.carryover_inject[:-3]
                    deps.reasoning_trail.append("safety_correction")
                    deps.mutation_count_this_iter += 1
            if deps.mutation_count_this_iter == 0:
                deps.carryover_inject.append("继续承接")
                deps.mutation_count_this_iter += 1
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            # Turn 0: Fast says unsafe text
            turn["n"] = 0
            await _run_turn(agent, "我很焦虑")

            # Turn 1: Slow reviews Turn 0's unsafe output, injects correction
            turn["n"] = 1
            await _run_turn(agent, "然后呢")

            # Turn 2: Fast should receive the correction
            turn["n"] = 2
            await _run_turn(agent, "继续聊")

        t2 = fast_deps_log[2]
        assert any("安全问题" in inj for inj in t2.dynamic_inject)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Slow Timeout/Error Recovery
# ═══════════════════════════════════════════════════════════════════════════════


class TestSlowTimeoutRecovery:
    """When Slow fails on Turn N, Turn N+1 should still work with stale state."""

    @pytest.mark.asyncio
    async def test_slow_exception_preserves_prior_state(self, monkeypatch):
        """Turn 0 Slow succeeds → Turn 1 Slow raises → Turn 2 Fast still gets Turn 0 state."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        fast_deps_log: list = []
        turn = {"n": 0}

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": ["ok"], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say("ok", add_to_chat_ctx=True)
            await asyncio.sleep(0)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            n = turn["n"]
            if n == 0:
                deps.carryover_inject.append("turn-0-inject")
                deps.carryover_retrieval = "turn-0-retrieval"
                deps.mutation_count_this_iter += 1
                return _BridgeRunResult()
            elif n == 1:
                raise RuntimeError("simulated slow failure")
            else:
                deps.mutation_count_this_iter += 1
                return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            turn["n"] = 0
            await _run_turn(agent, "Turn 0")
            turn["n"] = 1
            await _run_turn(agent, "Turn 1")
            turn["n"] = 2
            await _run_turn(agent, "Turn 2")

        # Turn 1 Fast should receive Turn 0's state
        t1 = fast_deps_log[1]
        assert "turn-0-inject" in t1.dynamic_inject
        assert t1.retrieval_block == "turn-0-retrieval"

        # Turn 2 Fast: Slow failed on Turn 1, state NOT updated.
        # Should still have Turn 0's state (stale but not lost).
        t2 = fast_deps_log[2]
        assert "turn-0-inject" in t2.dynamic_inject
        assert t2.retrieval_block == "turn-0-retrieval"

    @pytest.mark.asyncio
    async def test_slow_usage_limit_still_persists_state(self, monkeypatch):
        """UsageLimitExceeded should still persist whatever state was written before the limit."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod
        from pydantic_ai.exceptions import UsageLimitExceeded

        fast_deps_log: list = []

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": ["ok"], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say("ok", add_to_chat_ctx=True)
            await asyncio.sleep(0)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.carryover_inject.append("partial-inject")
            deps.mutation_count_this_iter += 1
            raise UsageLimitExceeded("test limit")

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "Turn 0")
            await _run_turn(agent, "Turn 1")

        # UsageLimitExceeded calls _persist_slow_state(None), so partial state is saved
        t1 = fast_deps_log[1]
        assert "partial-inject" in t1.dynamic_inject


# ═══════════════════════════════════════════════════════════════════════════════
# 9. StreamingVoiceBridgeAgent multi-turn
# ═══════════════════════════════════════════════════════════════════════════════


class TestStreamingBridgeMultiTurn:
    """StreamingVoiceBridgeAgent with keyword_filter per sentence and turn interruption."""

    @pytest.mark.asyncio
    async def test_keyword_filter_blocks_per_sentence(self, monkeypatch):
        """Each streamed sentence passes through keyword_filter independently."""
        from backend.voice.streaming_bridge_agent import StreamingVoiceBridgeAgent

        class _FilterTestResponder:
            async def stream_reply(self, **_kw):
                yield "我理解你的感受。"
                yield "你可能患有抑郁症。"
                yield "我在这里陪你。"

        published: list = []

        async def _publisher(event):
            published.append(event)

        agent = StreamingVoiceBridgeAgent(
            instructions="test",
            responder=_FilterTestResponder(),
            event_publisher=_publisher,
        )
        session = MagicMock()
        session.say = AsyncMock()
        activity = MagicMock()
        activity.session = session
        monkeypatch.setattr(
            agent, "_get_activity_or_raise", MagicMock(return_value=activity)
        )

        user_msg = MagicMock()
        user_msg.text_content = "我最近不好"

        with pytest.raises(StopResponse):
            await agent.on_user_turn_completed(MagicMock(), user_msg)

        spoken = [call.args[0] for call in session.say.await_args_list]
        assert spoken[0] == "我理解你的感受。"
        assert "抑郁症" not in spoken[1]
        assert spoken[2] == "我在这里陪你。"

    @pytest.mark.asyncio
    async def test_multi_turn_carryover_passed_to_responder(self, monkeypatch):
        """Carryover state is forwarded to responder.stream_reply on each turn."""
        from backend.voice.streaming_bridge_agent import StreamingVoiceBridgeAgent

        responder_kwargs_log: list[dict] = []

        class _LoggingResponder:
            async def stream_reply(self, **kw):
                responder_kwargs_log.append(kw)
                yield "ok"

        agent = StreamingVoiceBridgeAgent(
            instructions="test",
            responder=_LoggingResponder(),
        )
        agent._slow_state["carryover_inject"] = ["test-inject"]
        agent._slow_state["carryover_skills"] = ["test-skill"]
        agent._slow_state["carryover_retrieval"] = "test-retrieval"

        session = MagicMock()
        session.say = AsyncMock()
        activity = MagicMock()
        activity.session = session
        monkeypatch.setattr(
            agent, "_get_activity_or_raise", MagicMock(return_value=activity)
        )

        user_msg = MagicMock()
        user_msg.text_content = "hello"

        with pytest.raises(StopResponse):
            await agent.on_user_turn_completed(MagicMock(), user_msg)

        assert len(responder_kwargs_log) == 1
        kw = responder_kwargs_log[0]
        assert kw["dynamic_inject"] == ["test-inject"]
        assert kw["skill_bundle"] == ["test-skill"]
        assert kw["retrieval_block"] == "test-retrieval"

    @pytest.mark.asyncio
    async def test_turn_interruption_cancels_previous(self):
        """replace_turn_task cancels the old task and publishes turn_interrupted event."""
        from backend.voice.streaming_bridge_agent import StreamingVoiceBridgeAgent
        from backend.voice.streaming_events import VoiceStreamEvent

        events: list[VoiceStreamEvent] = []

        async def _pub(event):
            events.append(event)

        agent = StreamingVoiceBridgeAgent(
            instructions="test",
            responder=MagicMock(),
            event_publisher=_pub,
        )

        old_task = asyncio.create_task(asyncio.sleep(10))
        new_task = asyncio.create_task(asyncio.sleep(10))

        agent.replace_turn_task("turn-old", old_task)
        agent.replace_turn_task("turn-new", new_task)

        await asyncio.sleep(0.05)
        assert old_task.cancelled()
        assert agent.current_turn_id == "turn-new"

        interrupted = [e for e in events if e.type == "turn_interrupted"]
        assert len(interrupted) == 1
        assert interrupted[0].turn_id == "turn-old"

        new_task.cancel()
        await asyncio.sleep(0.01)
        await agent.aclose()


# ═══════════════════════════════════════════════════════════════════════════════
# 10. _build_prewarmed_contexts real file I/O
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildPrewarmedContextsReal:
    """_build_prewarmed_contexts loads real skill files from SKILLS_DIR."""

    def test_loads_existing_skill(self, tmp_path, monkeypatch):
        import backend.slow as slow_mod
        from backend.voice.bridge_agent import _build_prewarmed_contexts

        skill_dir = tmp_path / "untangle"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Untangle\nHelp user untangle confusion.")

        monkeypatch.setattr(slow_mod, "SKILLS_DIR", tmp_path)

        result = _build_prewarmed_contexts(["untangle(困惑)"])
        assert "untangle" in result
        assert "Untangle" in result["untangle"]

    def test_skips_missing_skill(self, tmp_path, monkeypatch):
        import backend.slow as slow_mod
        from backend.voice.bridge_agent import _build_prewarmed_contexts

        monkeypatch.setattr(slow_mod, "SKILLS_DIR", tmp_path)

        result = _build_prewarmed_contexts(["nonexistent(missing)"])
        assert result == {}

    def test_multiple_skills_loaded(self, tmp_path, monkeypatch):
        import backend.slow as slow_mod
        from backend.voice.bridge_agent import _build_prewarmed_contexts

        for name in ("listen", "calm-body"):
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(f"# {name}\ncontent")

        monkeypatch.setattr(slow_mod, "SKILLS_DIR", tmp_path)

        result = _build_prewarmed_contexts(["listen(倾听)", "calm-body(焦虑)"])
        assert "listen" in result
        assert "calm-body" in result

    def test_empty_input_returns_empty(self):
        from backend.voice.bridge_agent import _build_prewarmed_contexts

        assert _build_prewarmed_contexts([]) == {}


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Fast failure + already_spoke recovery across turns
# ═══════════════════════════════════════════════════════════════════════════════


class TestFastFailureRecovery:
    """Fast fails after ai_message spoke → no fallback, next turn recovers normally."""

    @pytest.mark.asyncio
    async def test_fast_fails_after_speaking_then_next_turn_works(self, monkeypatch):
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        fast_deps_log: list = []
        turn = {"n": 0}

        async def _fake_fast(user_msg, *, deps, message_history=None):
            fast_deps_log.append(deps)
            n = turn["n"]
            text = f"reply-{n}"
            deps.collected_tool_calls.append(
                {
                    "name": "ai_message",
                    "args": {"messages": [text], "needs_deep_analysis": False},
                }
            )
            deps.voice_session.say(text, add_to_chat_ctx=True)
            if n == 0:
                raise RuntimeError("Exceeded maximum retries for output validation")
            await asyncio.sleep(0)
            return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.carryover_inject.append(f"slow-inject-{turn['n']}")
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            # Turn 0: Fast fails after speaking
            turn["n"] = 0
            await _run_turn(agent, "Turn 0")

            # Turn 1: Should recover and work normally
            turn["n"] = 1
            await _run_turn(agent, "Turn 1")

        # Turn 0: session.say called once with "reply-0", no fallback
        # (already_spoke=True because ai_message was recorded)
        # Turn 1 should still receive slow state from Turn 0
        t1 = fast_deps_log[1]
        assert "slow-inject-0" in t1.dynamic_inject

    @pytest.mark.asyncio
    async def test_fast_fails_without_speaking_triggers_fallback(self, monkeypatch):
        """When Fast fails before any ai_message, bridge should say fallback."""
        import backend.fast as fast_mod
        import backend.slow as slow_mod

        async def _fake_fast(user_msg, *, deps, message_history=None):
            raise RuntimeError("total failure, no tool calls")

        async def _fake_slow(user_msg, *, deps, message_history=None, usage_limits=None):
            deps.mutation_count_this_iter += 1
            return _BridgeRunResult()

        monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast)
        monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow)

        agent = _make_agent()
        with patch("backend.voice.bridge_agent._build_prewarmed_contexts", return_value={}):
            await _run_turn(agent, "hello")

        say_calls = agent.session.say.call_args_list
        assert len(say_calls) == 1
        assert "慢慢说" in say_calls[0].args[0]
