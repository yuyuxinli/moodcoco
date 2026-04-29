from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from livekit.agents import StopResponse

from tests.voice.test_fast_slow_basic import (
    _BridgeRunResult,
    _make_agent,
    _make_chat_context,
    _make_user_message,
)


@pytest.mark.asyncio
async def test_bridge_reseeds_fast_deps_with_slow_carryover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.fast as fast_mod
    import backend.slow as slow_mod

    calls: dict[str, list] = {"fast": [], "slow": []}

    async def _fake_fast_run(user_msg, *, deps, message_history=None):
        calls["fast"].append({"user_msg": user_msg, "deps": deps})
        deps.collected_tool_calls.append(
            {
                "name": "ai_message",
                "args": {"messages": ["嗯，我在。"], "needs_deep_analysis": True},
            }
        )
        deps.voice_session.say("嗯，我在。", add_to_chat_ctx=True)
        return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

    async def _fake_slow_run(user_msg, *, deps, message_history=None):
        calls["slow"].append({"user_msg": user_msg, "deps": deps})
        if user_msg == "第一轮":
            deps.fast_deps.dynamic_inject.extend(["a", "b", "c", "d"])
            deps.fast_deps.skill_bundle.append("listen skill text")
            deps.fast_deps.retrieval_block = "上一轮他说被翻聊天记录，很生气。"
            deps.mutation_count_this_iter += 3
        return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

    monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast_run)
    monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow_run)

    agent = _make_agent(min_silence=0.02)

    with pytest.raises(StopResponse):
        await asyncio.wait_for(
            agent.on_user_turn_completed(_make_chat_context(), _make_user_message("第一轮")),
            timeout=3.0,
        )
    await asyncio.sleep(0)

    with pytest.raises(StopResponse):
        await asyncio.wait_for(
            agent.on_user_turn_completed(_make_chat_context(), _make_user_message("第二轮")),
            timeout=3.0,
        )

    second_fast_deps = calls["fast"][1]["deps"]
    assert second_fast_deps.dynamic_inject == ["b", "c", "d"]
    assert second_fast_deps.skill_bundle == ["listen skill text"]
    assert second_fast_deps.retrieval_block == "上一轮他说被翻聊天记录，很生气。"


@pytest.mark.asyncio
async def test_bridge_skips_fallback_when_slow_called_any_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.fast as fast_mod
    import backend.slow as slow_mod

    calls: dict[str, list] = {"fast": [], "slow": []}

    async def _fake_fast_run(user_msg, *, deps, message_history=None):
        calls["fast"].append({"user_msg": user_msg, "deps": deps})
        deps.collected_tool_calls.append(
            {
                "name": "ai_message",
                "args": {"messages": ["嗯，我听着。"], "needs_deep_analysis": False},
            }
        )
        deps.voice_session.say("嗯，我听着。", add_to_chat_ctx=True)
        return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

    async def _fake_slow_run(user_msg, *, deps, message_history=None):
        calls["slow"].append({"user_msg": user_msg, "deps": deps})
        deps.tool_call_history.append("list_skills")
        return _BridgeRunResult([*(message_history or []), {"role": "assistant"}])

    monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast_run)
    monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow_run)

    agent = _make_agent(min_silence=0.02)

    with pytest.raises(StopResponse):
        await asyncio.wait_for(
            agent.on_user_turn_completed(_make_chat_context(), _make_user_message("普通问候")),
            timeout=3.0,
        )
    await asyncio.sleep(0)

    fast_deps = calls["fast"][0]["deps"]
    slow_deps = calls["slow"][0]["deps"]
    assert fast_deps.dynamic_inject == []
    assert slow_deps.mutation_count_this_iter == 0
    assert agent._slow_state["carryover_inject"] == []


@pytest.mark.asyncio
async def test_slow_inject_auto_completes_voice_context_for_emotional_turn() -> None:
    from backend.fast import FastThinkDeps
    from backend.slow import SlowThinkDeps, slow_inject_to_fast

    fast_deps = FastThinkDeps(
        session_id="test-session",
        memory_text="",
        voice_session=object(),
    )
    slow_deps = SlowThinkDeps(
        session_id="test-session",
        user_message="我和我妈昨天大吵了一架，我感觉特别委屈。",
        fast_deps=fast_deps,
    )
    ctx = SimpleNamespace(deps=slow_deps)

    await slow_inject_to_fast(ctx, "下一轮先承接委屈，不急着给建议。")

    assert "slow_inject_to_fast" in slow_deps.tool_call_history
    assert "slow_set_fast_retrieval" in slow_deps.tool_call_history
    assert any(
        item.startswith("slow_attach_skill_to_fast(")
        for item in slow_deps.tool_call_history
    )
    assert fast_deps.dynamic_inject == ["下一轮先承接委屈，不急着给建议。"]
    assert fast_deps.skill_bundle
    assert fast_deps.retrieval_block.startswith("本轮用户线索：")
    assert slow_deps.mutation_count_this_iter == 3
