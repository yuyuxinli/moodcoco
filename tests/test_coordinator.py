from __future__ import annotations

from dataclasses import dataclass
import asyncio

import pytest


@dataclass
class _SlowResult:
    output: str = "下一轮继续承接转专业和关系焦虑。"


@pytest.mark.asyncio
async def test_run_turn_keeps_ai_message_when_fast_output_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import backend.coordinator as coordinator
    import backend.fast as fast_mod
    import backend.slow as slow_mod

    memory_file = tmp_path / "MEMORY.md"
    guidance_file = tmp_path / "SLOW_GUIDANCE.md"
    memory_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(coordinator, "MEMORY_FILE", memory_file)
    monkeypatch.setattr(coordinator, "GUIDANCE_FILE", guidance_file)

    async def _fake_fast_run(user_msg, *, deps):
        deps.collected_tool_calls.append(
            {
                "name": "ai_message",
                "args": {
                    "messages": ["绩点掉了确实会慌。"],
                    "needs_deep_analysis": True,
                },
            }
        )
        raise RuntimeError("Exceeded maximum retries (0) for output validation")

    slow_calls: list[dict] = []

    async def _fake_slow_run(user_msg, *, deps, usage_limits=None):
        slow_calls.append({"user_msg": user_msg, "deps": deps, "usage_limits": usage_limits})
        return _SlowResult()

    monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast_run)
    monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow_run)

    result = await coordinator.run_turn("我绩点又掉了", session_id="test-session")

    assert result["fast_reply_text"] == "绩点掉了确实会慌。"
    assert result["needs_deep"] is True
    assert result["fast_tool_calls"][0]["name"] == "ai_message"
    assert slow_calls
    assert slow_calls[0]["usage_limits"].request_limit == 4
    assert slow_calls[0]["usage_limits"].tool_calls_limit == 4
    assert guidance_file.read_text(encoding="utf-8").strip() == _SlowResult.output


@pytest.mark.asyncio
async def test_run_turn_returns_fast_reply_when_slow_times_out(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import backend.coordinator as coordinator
    import backend.fast as fast_mod
    import backend.slow as slow_mod

    memory_file = tmp_path / "MEMORY.md"
    guidance_file = tmp_path / "SLOW_GUIDANCE.md"
    memory_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(coordinator, "MEMORY_FILE", memory_file)
    monkeypatch.setattr(coordinator, "GUIDANCE_FILE", guidance_file)
    monkeypatch.setattr(coordinator, "TEXT_SLOW_TIMEOUT_SECONDS", 0.01)

    async def _fake_fast_run(user_msg, *, deps):
        deps.collected_tool_calls.append(
            {
                "name": "ai_message",
                "args": {
                    "messages": ["我先接住你这句。"],
                    "needs_deep_analysis": True,
                },
            }
        )

    async def _fake_slow_run(user_msg, *, deps, usage_limits=None):
        await asyncio.sleep(10)
        return _SlowResult()

    monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast_run)
    monkeypatch.setattr(slow_mod.slow_agent, "run", _fake_slow_run)

    result = await coordinator.run_turn("我很烦", session_id="test-session")

    assert result["fast_reply_text"] == "我先接住你这句。"
    assert result["slow_guidance_for_next_turn"] == ""
    assert not guidance_file.exists()


@pytest.mark.asyncio
async def test_run_turn_times_out_when_fast_never_returns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import backend.coordinator as coordinator
    import backend.fast as fast_mod

    memory_file = tmp_path / "MEMORY.md"
    guidance_file = tmp_path / "SLOW_GUIDANCE.md"
    memory_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(coordinator, "MEMORY_FILE", memory_file)
    monkeypatch.setattr(coordinator, "GUIDANCE_FILE", guidance_file)
    monkeypatch.setattr(coordinator, "TEXT_FAST_TIMEOUT_SECONDS", 0.01)

    async def _fake_fast_run(user_msg, *, deps):
        await asyncio.sleep(10)

    monkeypatch.setattr(fast_mod.fast_agent, "run", _fake_fast_run)

    with pytest.raises(TimeoutError):
        await coordinator.run_turn("我很烦", session_id="test-session")
