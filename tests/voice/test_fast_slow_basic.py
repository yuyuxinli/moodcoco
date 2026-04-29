"""Unit tests for the pydantic-ai voice bridge.

All tests are async (pytest-asyncio strict mode).
No network calls — Fast/Slow agents and session.say are mocked throughout.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

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


def _make_agent(**_ignored: object) -> "FastSlowAgent":
    """Build a voice bridge agent with a mocked session.say attached."""
    from backend.voice.bridge_agent import FastSlowAgent

    agent = FastSlowAgent(instructions="You are a helpful assistant.")

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
    from backend.voice.bridge_agent import voice_session_ctx, voice_turn_ctx

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


# ── Test 1: Fast speaks and stops LiveKit reply ───────────────────────────────


@pytest.mark.asyncio
async def test_bridge_fast_says_and_stops_livekit_reply(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: bridge runs Fast, lets ai_message speak, then raises StopResponse."""
    fast_text = "嗯，我在听你说。"
    calls = _patch_bridge_agents(monkeypatch, fast_text=fast_text)
    agent = _make_agent()

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


# ── Test 2: voice session is passed to Fast ───────────────────────────────────


@pytest.mark.asyncio
async def test_bridge_passes_voice_session_to_fast(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: FastThinkDeps carries the LiveKit AgentSession reference."""
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent()

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)

    fast_deps = calls["fast"][0]["deps"]
    assert fast_deps.voice_session is agent.session
    assert fast_deps.voice_system_extras()


# ── Test 3: slow state is collected ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_bridge_collects_slow_state(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: slow done callback writes history and cross-turn state back."""
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent()

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

    We spy on the contextvars from inside the patched Fast run.
    """
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent()

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)

    # The contextvar must have been set before the patched Fast run was called.
    assert len(calls["session_ids"]) >= 1, (
        "Fast run was not called (voice_session_ctx not captured)."
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


# ── Test 5: message history is preserved ─────────────────────────────────────


@pytest.mark.asyncio
async def test_bridge_preserves_message_history(monkeypatch: pytest.MonkeyPatch):
    """F-2.0a: Fast and Slow message histories are fed back on later turns."""
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent()

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
