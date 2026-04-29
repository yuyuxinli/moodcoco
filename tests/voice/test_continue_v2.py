"""Unit tests for FastSlowAgent F8 extension — DP-continue + slow_v2.

5 cases per F1 §8 F8.  All async via pytest-asyncio; LLM calls and
``session.say`` are mocked.  No network.

Coverage map (F1 §8 F8):
1. ``test_dp_continue_yes_triggers_slow_v2`` — yes → slow_v2 invoked, skill
   content present in slow_v2 system prompt.
2. ``test_dp_continue_no_skips_slow_v2`` — no → slow_v2 NOT invoked, path
   marked ``standard`` (filler fired).
3. ``test_dp_continue_timeout_treated_as_no`` — DP-continue blocked >200 ms
   real timeout → fallback yes=False, slow_v2 NOT invoked, log carries
   ``timeout`` reason.
4. ``test_slow_v2_uses_skill_from_merged_decision`` — merged_decision returns
   ``skill="listen"``; skill router stub returns deterministic text → slow_v2
   system prompt contains that text verbatim.
5. ``test_short_path_skips_filler_but_runs_decisions`` — slow_v1 emits first
   token < 0.4 s (mocked by setting the flag inside ``_run_slow``); filler
   skipped AND merged_decision still ran in parallel (logged) AND
   continue_decider STILL called after slow_v1 (per design §1).
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from livekit.agents import StopResponse

from backend.voice.decisions.continue_decider import ContinueDecision
from backend.voice.decisions.merged_decision import MergedDecisionResult


# ── Helpers (mirror test_fast_slow_basic.py for compatibility) ──────────────


def _make_chat_context() -> MagicMock:
    """Minimal ChatContext mock that supports add_message and tracks messages."""
    ctx = MagicMock()
    ctx.messages: list[dict] = []

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


def _make_fast_llm(filler_text: str = "嗯，我在听") -> MagicMock:
    """Mock openai.AsyncOpenAI-compatible fast_llm with streaming chunks."""
    fast_llm = MagicMock()

    async def _fake_stream_iter():
        for piece in [filler_text[: len(filler_text) // 2], filler_text[len(filler_text) // 2 :]]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = piece
            yield chunk

    async def _fake_create(**kwargs: Any):
        return _fake_stream_iter()

    fast_llm.chat = MagicMock()
    fast_llm.chat.completions = MagicMock()
    fast_llm.chat.completions.create = AsyncMock(side_effect=_fake_create)
    return fast_llm


def _make_skill_router_mock(skill_content: str = "FAKE_SKILL_CONTENT") -> MagicMock:
    router = MagicMock()
    router.load_skill_content = MagicMock(return_value=skill_content)
    return router


def _make_agent(
    *,
    merged_decision_fn,
    continue_decider_fn,
    slow_llm_chat_fn,
    skill_router=None,
    fast_llm=None,
    min_silence: float = 0.05,
    fast_filler_max_count: int = 1,
    filler_text: str = "嗯，我在听",
):
    """Build a FastSlowAgent wired for F8 tests with all hooks mocked."""
    from backend.voice.fast_slow_agent import FastSlowAgent

    if fast_llm is None:
        fast_llm = _make_fast_llm(filler_text)

    agent = FastSlowAgent(
        instructions="You are a helpful assistant.",
        fast_llm=fast_llm,
        merged_decision_fn=merged_decision_fn,
        continue_decider_fn=continue_decider_fn,
        skill_router=skill_router,
        slow_llm_chat_fn=slow_llm_chat_fn,
        min_silence_before_kicking=min_silence,
        fast_filler_max_count=fast_filler_max_count,
    )

    # Attach mock session (drains any async-iterable handed to session.say).
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
    room_mock.name = "test-room-001"
    session_mock.room = room_mock

    activity_mock = MagicMock()
    activity_mock.session = session_mock
    agent._get_activity_or_raise = MagicMock(return_value=activity_mock)

    return agent


class _BridgeRunResult:
    def __init__(self, messages: list[dict], output: str = "ok") -> None:
        self._messages = messages
        self.output = output

    def all_messages(self) -> list[dict]:
        return self._messages


def _patch_bridge_agents(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fast_text: str = "嗯，我在听你说。",
    slow_mutation: str = "inject",
) -> dict[str, list]:
    import backend.fast as fast_mod
    import backend.slow as slow_mod

    calls: dict[str, list] = {"fast": [], "slow": []}

    async def _fake_fast_run(user_msg, *, deps, message_history=None):
        calls["fast"].append(
            {
                "user_msg": user_msg,
                "deps": deps,
                "message_history": list(message_history or []),
            }
        )
        deps.collected_tool_calls.append(
            {
                "name": "ai_message",
                "args": {"messages": [fast_text], "needs_deep_analysis": True},
            }
        )
        deps.voice_session.say(fast_text, add_to_chat_ctx=True)
        return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

    async def _fake_slow_run(user_msg, *, deps, message_history=None):
        calls["slow"].append(
            {
                "user_msg": user_msg,
                "deps": deps,
                "message_history": list(message_history or []),
            }
        )
        deps.fast_deps.dynamic_inject.append(slow_mutation)
        deps.mutation_count_this_iter += 1
        return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

    monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast_run)
    monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow_run)
    return calls


# ── F-2.0a bridge tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bridge_starts_fast_and_slow_in_parallel(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent(
        merged_decision_fn=AsyncMock(),
        continue_decider_fn=AsyncMock(),
        slow_llm_chat_fn=AsyncMock(),
        min_silence=0.02,
    )

    ctx = _make_chat_context()
    user_msg = _make_user_message("我和我妈又吵了")

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)
    await asyncio.sleep(0)

    assert [c["user_msg"] for c in calls["fast"]] == ["我和我妈又吵了"]
    assert [c["user_msg"] for c in calls["slow"]] == ["我和我妈又吵了"]
    assert agent.session.say.call_count == 1


@pytest.mark.asyncio
async def test_bridge_does_not_call_deprecated_deciders(monkeypatch: pytest.MonkeyPatch):
    _patch_bridge_agents(monkeypatch)
    merged_decision_fn = AsyncMock()
    continue_decider_fn = AsyncMock()
    slow_llm_chat_fn = AsyncMock()
    agent = _make_agent(
        merged_decision_fn=merged_decision_fn,
        continue_decider_fn=continue_decider_fn,
        slow_llm_chat_fn=slow_llm_chat_fn,
        min_silence=0.02,
    )

    with pytest.raises(StopResponse):
        await asyncio.wait_for(
            agent.on_user_turn_completed(_make_chat_context(), _make_user_message()),
            timeout=3.0,
        )

    merged_decision_fn.assert_not_awaited()
    continue_decider_fn.assert_not_awaited()
    slow_llm_chat_fn.assert_not_awaited()


@pytest.mark.asyncio
async def test_bridge_logs_fast_and_slow_completion(monkeypatch, caplog):
    _patch_bridge_agents(monkeypatch)
    caplog.set_level("INFO", logger="voice.fast_slow_agent")
    agent = _make_agent(
        merged_decision_fn=AsyncMock(),
        continue_decider_fn=AsyncMock(),
        slow_llm_chat_fn=AsyncMock(),
        min_silence=0.02,
    )

    with pytest.raises(StopResponse):
        await asyncio.wait_for(
            agent.on_user_turn_completed(_make_chat_context(), _make_user_message()),
            timeout=3.0,
        )
    await asyncio.sleep(0)

    messages = [record.getMessage() for record in caplog.records]
    assert "fast_agent_run_started" in messages
    assert "fast_agent_run_completed" in messages
    assert "slow_agent_run_started" in messages
    assert "slow_agent_run_completed" in messages


@pytest.mark.asyncio
async def test_bridge_slow_mutates_fast_deps(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bridge_agents(monkeypatch, slow_mutation="read relationship-guide")
    agent = _make_agent(
        merged_decision_fn=AsyncMock(),
        continue_decider_fn=AsyncMock(),
        slow_llm_chat_fn=AsyncMock(),
        min_silence=0.02,
    )

    with pytest.raises(StopResponse):
        await asyncio.wait_for(
            agent.on_user_turn_completed(_make_chat_context(), _make_user_message()),
            timeout=3.0,
        )
    await asyncio.sleep(0)

    fast_deps = calls["fast"][0]["deps"]
    slow_deps = calls["slow"][0]["deps"]
    assert fast_deps.dynamic_inject == ["read relationship-guide"]
    assert slow_deps.mutation_count_this_iter == 1


@pytest.mark.asyncio
async def test_bridge_empty_user_message_returns_without_stop(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent(
        merged_decision_fn=AsyncMock(),
        continue_decider_fn=AsyncMock(),
        slow_llm_chat_fn=AsyncMock(),
        min_silence=0.02,
    )

    await asyncio.wait_for(
        agent.on_user_turn_completed(_make_chat_context(), _make_user_message("   ")),
        timeout=3.0,
    )

    assert calls["fast"] == []
    assert calls["slow"] == []
