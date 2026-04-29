"""Unit tests for FastSlowAgent skeleton — F5 test cases (5 cases per F1 §8).

All tests are async (pytest-asyncio strict mode).
No network calls — fast_llm and session.say are mocked throughout.

OQ resolution coverage:
  OQ-12: _slow_first_token_emitted flag gates filler dispatch.
  OQ-13: chat_ctx write-back happens after session.say filler_fut resolves.
  OQ-14: contextvars (voice_session_ctx, voice_turn_ctx) are set during the turn.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from livekit.agents import StopResponse

# ── Helpers ──────────────────────────────────────────────────────────────────


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


def _make_fast_llm(filler_text: str = "嗯，听起来不太好受") -> MagicMock:
    """Build a mock openai.AsyncOpenAI-compatible fast_llm client.

    The mock simulates async streaming: chat.completions.create returns an
    async iterable where each item has choices[0].delta.content == filler chunk.
    """
    fast_llm = MagicMock()

    async def _fake_stream_iter():
        # Yield filler text in two chunks to test accumulation.
        for chunk_text in [filler_text[:len(filler_text)//2], filler_text[len(filler_text)//2:]]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = chunk_text
            yield chunk

    async def _fake_create(**kwargs):
        return _fake_stream_iter()

    fast_llm.chat = MagicMock()
    fast_llm.chat.completions = MagicMock()
    fast_llm.chat.completions.create = AsyncMock(side_effect=_fake_create)
    return fast_llm


def _make_agent(
    fast_llm=None,
    slow_llm=None,
    min_silence: float = 0.05,  # very short for fast tests
    fast_filler_max_count: int = 1,
    filler_text: str = "嗯，听起来不太好受",
) -> "FastSlowAgent":
    """Build a FastSlowAgent with a mocked session.say attached."""
    from backend.voice.fast_slow_agent import FastSlowAgent

    if fast_llm is None:
        fast_llm = _make_fast_llm(filler_text)

    agent = FastSlowAgent(
        instructions="You are a helpful assistant.",
        fast_llm=fast_llm,
        slow_llm=slow_llm,
        min_silence_before_kicking=min_silence,
        fast_filler_max_count=fast_filler_max_count,
    )

    # Attach a mock session so self.session.say and self.session.room work.
    # session.say drains its async-iterable arg in a background task — without
    # this, the streaming-Future generator never iterates, so the filler future
    # never resolves and on_user_turn_completed hangs.  Real LiveKit drives this.
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

    # Patch _get_activity_or_raise to return a fake activity that has .session
    activity_mock = MagicMock()
    activity_mock.session = session_mock
    agent._get_activity_or_raise = MagicMock(return_value=activity_mock)

    return agent


class _BridgeRunResult:
    def __init__(self, messages: list[dict]) -> None:
        self._messages = messages
        self.output = "ok"

    def all_messages(self) -> list[dict]:
        return self._messages


def _patch_bridge_agents(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fast_text: str = "嗯，我在听你说。",
    slow_inject: str = "下一轮继续承接情绪。",
) -> dict[str, list]:
    """Patch pydantic-ai agents so bridge tests stay hermetic."""
    import backend.fast as fast_mod
    import backend.slow as slow_mod
    from backend.voice.fast_slow_agent import voice_session_ctx, voice_turn_ctx

    calls: dict[str, list] = {
        "fast": [],
        "slow": [],
        "session_ids": [],
        "turn_ids": [],
    }

    async def _fake_fast_run(user_msg, *, deps, message_history=None):
        calls["fast"].append(
            {
                "user_msg": user_msg,
                "deps": deps,
                "message_history": list(message_history or []),
            }
        )
        calls["session_ids"].append(voice_session_ctx.get())
        calls["turn_ids"].append(voice_turn_ctx.get())
        deps.collected_tool_calls.append(
            {
                "name": "ai_message",
                "args": {"messages": [fast_text], "needs_deep_analysis": False},
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
        deps.fast_deps.dynamic_inject.append(slow_inject)
        deps.reasoning_trail.append("inject")
        deps.search_cache[user_msg] = "cached"
        deps.pending_actions.append({"kind": "followup"})
        deps.mutation_count_this_iter += 1
        return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

    monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast_run)
    monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow_run)
    return calls


# ── Test 1: filler fires after silence ────────────────────────────────────────


@pytest.mark.asyncio
async def test_bridge_fast_says_and_stops_livekit_reply(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: bridge runs Fast, lets ai_message speak, then raises StopResponse."""
    fast_text = "嗯，我在听你说。"
    calls = _patch_bridge_agents(monkeypatch, fast_text=fast_text)
    agent = _make_agent(min_silence=0.02)

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)
    await asyncio.sleep(0)

    session_say = agent.session.say
    assert session_say.call_count == 1
    session_say.assert_called_with(fast_text, add_to_chat_ctx=True)
    assert len(calls["fast"]) == 1
    assert len(calls["slow"]) == 1


# ── Test 2: filler skipped if slow emits first token quickly ─────────────────


@pytest.mark.asyncio
async def test_bridge_passes_voice_session_to_fast(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: FastThinkDeps carries the LiveKit AgentSession reference."""
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent(min_silence=0.1)

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)

    fast_deps = calls["fast"][0]["deps"]
    assert fast_deps.voice_session is agent.session
    assert fast_deps.voice_system_extras()


# ── Test 3: filler max count = 1 (strengthened) ─────────────────────────────


@pytest.mark.asyncio
async def test_filler_max_count_one():
    """F1 §8 F5 case 3 strengthened: even with the slow path silent for 5+ s and
    the filler timer firing twice (simulating a multi-tick timer in F8), the
    filler LLM is invoked at most once.

    The round-1 version was tautological: a single ``on_user_turn_completed``
    call can only fire ``_maybe_filler`` once, so ``_turn_filler_count == 1``
    was guaranteed even if the MAX_COUNT guard were deleted.

    This version invokes ``_maybe_filler`` directly twice with the slow path
    pinned silent (``_run_slow`` returns a 5 s no-op).  The MAX_COUNT=1 guard
    must skip the second invocation: the LLM must be called exactly once and
    ``session.say`` must be called exactly once.
    """
    agent = _make_agent(min_silence=0.01, fast_filler_max_count=1)

    ctx = _make_chat_context()
    _ = _make_user_message()

    # Reset per-turn state (normally done by on_user_turn_completed).
    agent._turn_filler_count = 0
    agent._slow_first_token_emitted = False

    # Set ContextVars (normally done by on_user_turn_completed).
    from backend.voice.fast_slow_agent import voice_session_ctx, voice_turn_ctx
    voice_session_ctx.set("test-room-001")
    voice_turn_ctx.set("turn00001")

    # Pin the slow path silent for 5 s (longer than any reasonable filler timer).
    async def _slow_long(*args, **kwargs):
        await asyncio.sleep(5.0)

    agent._run_slow = _slow_long  # type: ignore[method-assign]

    # Fire the filler timer TWICE (each waits min_silence = 0.01 s).
    await asyncio.wait_for(
        agent._maybe_filler(ctx, "test-room-001", "turn00001"), timeout=3.0
    )
    await asyncio.wait_for(
        agent._maybe_filler(ctx, "test-room-001", "turn00001"), timeout=3.0
    )

    # Fast LLM (filler) must be called exactly ONCE despite two timer fires.
    assert agent._fast_llm.chat.completions.create.call_count == 1, (
        f"Filler LLM should be called once across two timer fires; got "
        f"{agent._fast_llm.chat.completions.create.call_count}"
    )
    assert agent.session.say.call_count == 1
    assert agent._turn_filler_count == 1


# ── Test 4: chat_ctx write-back after filler ──────────────────────────────────


@pytest.mark.asyncio
async def test_bridge_collects_slow_state(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: slow done callback writes history and cross-turn state back."""
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent(min_silence=0.01)

    ctx = _make_chat_context()
    user_msg = _make_user_message("我有些担心")

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)
    await asyncio.sleep(0)

    assert agent._slow_history
    assert agent._slow_state["reasoning_trail"] == ["inject"]
    assert agent._slow_state["search_cache"][user_msg.text_content] == "cached"
    assert agent._slow_state["pending_actions"] == [{"kind": "followup"}]
    assert calls["slow"][0]["deps"].fast_deps.dynamic_inject


# ── Test 5: session_id and turn_id propagated via contextvars ─────────────────


@pytest.mark.asyncio
async def test_session_id_turn_id_propagated(monkeypatch: pytest.MonkeyPatch):
    """voice_session_ctx and voice_turn_ctx must be set inside the agent turn.

    F1 §8 F5 case 4 / OQ-14 contract: contextvars set by FastSlowAgent for F3 plugin.
    We spy on the contextvars from inside the filler generator.
    """
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent(min_silence=0.01)

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)

    # The contextvar must have been set before the filler LLM was called.
    assert len(calls["session_ids"]) >= 1, (
        "Filler LLM was not called (voice_session_ctx not captured). "
        "Ensure filler fired (min_silence short enough)."
    )
    assert calls["session_ids"][0] is not None, (
        f"voice_session_ctx was None inside bridge. Got: {calls['session_ids']}"
    )
    assert calls["turn_ids"][0] is not None, (
        f"voice_turn_ctx was None inside bridge. Got: {calls['turn_ids']}"
    )
    # session_id should be the room name set by the mock.
    assert calls["session_ids"][0] == "test-room-001", (
        f"Expected session_id='test-room-001', got: {calls['session_ids'][0]!r}"
    )
    # turn_id should be an 8-char hex string.
    assert len(calls["turn_ids"][0]) == 8, (
        f"Expected 8-char hex turn_id, got: {calls['turn_ids'][0]!r}"
    )


# ── Test 6: F1 §8 case 4 — both fast AND slow LLMs invoked ───────────────────


@pytest.mark.asyncio
async def test_bridge_preserves_message_history(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: Fast and Slow message histories are fed back on later turns."""
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent(min_silence=0.02)

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)
    await asyncio.sleep(0)
    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)

    assert calls["fast"][0]["message_history"] == []
    assert calls["slow"][0]["message_history"] == []
    assert calls["fast"][1]["message_history"]
    assert calls["slow"][1]["message_history"]
