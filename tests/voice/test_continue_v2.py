"""Bridge-focused voice tests for the pydantic-ai Fast and Slow handoff."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from livekit.agents import StopResponse

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


def _make_agent():
    """Build a voice bridge agent with a mocked session.say attached."""
    from backend.voice.bridge_agent import FastSlowAgent

    agent = FastSlowAgent(instructions="You are a helpful assistant.")

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
    agent = _make_agent()

    ctx = _make_chat_context()
    user_msg = _make_user_message("我和我妈又吵了")

    with pytest.raises(StopResponse):
        await asyncio.wait_for(agent.on_user_turn_completed(ctx, user_msg), timeout=3.0)
    await asyncio.sleep(0)

    assert [c["user_msg"] for c in calls["fast"]] == ["我和我妈又吵了"]
    assert [c["user_msg"] for c in calls["slow"]] == ["我和我妈又吵了"]
    assert agent.session.say.call_count == 1


@pytest.mark.asyncio
async def test_bridge_runs_without_legacy_hooks(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_bridge_agents(monkeypatch)
    agent = _make_agent()

    with pytest.raises(StopResponse):
        await asyncio.wait_for(
            agent.on_user_turn_completed(_make_chat_context(), _make_user_message()),
            timeout=3.0,
        )

    assert len(calls["fast"]) == 1
    assert len(calls["slow"]) == 1


@pytest.mark.asyncio
async def test_bridge_logs_fast_and_slow_completion(monkeypatch, caplog):
    _patch_bridge_agents(monkeypatch)
    caplog.set_level("INFO", logger="voice.bridge_agent")
    agent = _make_agent()

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
    agent = _make_agent()

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
    agent = _make_agent()

    await asyncio.wait_for(
        agent.on_user_turn_completed(_make_chat_context(), _make_user_message("   ")),
        timeout=3.0,
    )

    assert calls["fast"] == []
    assert calls["slow"] == []
