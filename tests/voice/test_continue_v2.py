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


# ── Test 1: dp_continue=yes triggers slow_v2 with skill content ─────────────


@pytest.mark.asyncio
async def test_dp_continue_yes_triggers_slow_v2():
    """F1 §8 F8 case 1: continue=yes → slow_v2 invoked with skill content."""
    skill_content = "## Listen Skill\n承接情绪，不急着分析。"
    skill_router = _make_skill_router_mock(skill_content=skill_content)

    merged_decision_fn = AsyncMock(
        return_value=MergedDecisionResult(skill="listen", latency_ms=12.0)
    )
    continue_decider_fn = AsyncMock(
        return_value=ContinueDecision(yes=True, reason="too_shallow", latency_ms=20.0)
    )

    slow_outputs = ["slow_v1 reply", "slow_v2 deeper reply"]
    captured_messages: list[list[dict]] = []

    async def _slow_chat(messages: list[dict]) -> str:
        captured_messages.append(messages)
        return slow_outputs[len(captured_messages) - 1]

    agent = _make_agent(
        merged_decision_fn=merged_decision_fn,
        continue_decider_fn=continue_decider_fn,
        slow_llm_chat_fn=_slow_chat,
        skill_router=skill_router,
        min_silence=0.02,
    )

    ctx = _make_chat_context()
    user_msg = _make_user_message("我和我妈又吵了")

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg), timeout=3.0
    )

    # slow LLM called twice (v1 + v2).
    assert len(captured_messages) == 2, (
        f"Expected slow_llm called twice, got {len(captured_messages)}"
    )
    # slow_v2 system prompt must contain the skill content text.
    slow_v2_system = captured_messages[1][0]
    assert slow_v2_system["role"] == "system"
    assert skill_content in slow_v2_system["content"], (
        f"slow_v2 system prompt missing skill content. Got:\n{slow_v2_system['content']!r}"
    )
    # The skill router was asked for the listen skill.
    skill_router.load_skill_content.assert_called_once_with("listen")
    # Continue decider was called with slow_v1 text.
    continue_decider_fn.assert_awaited_once()
    args, _ = continue_decider_fn.call_args
    assert args[0] == "slow_v1 reply"


# ── Test 2: dp_continue=no skips slow_v2; path = standard ───────────────────


@pytest.mark.asyncio
async def test_dp_continue_no_skips_slow_v2(caplog: pytest.LogCaptureFixture):
    """F1 §8 F8 case 2: continue=no → slow_llm called once (v1 only),
    turn marked ``standard`` (filler fired)."""
    caplog.set_level("INFO", logger="voice.fast_slow_agent")

    merged_decision_fn = AsyncMock(return_value=MergedDecisionResult())
    continue_decider_fn = AsyncMock(
        return_value=ContinueDecision(yes=False, reason="ok", latency_ms=15.0)
    )

    slow_calls = 0

    async def _slow_chat(messages: list[dict]) -> str:
        nonlocal slow_calls
        slow_calls += 1
        return "slow_v1 only"

    agent = _make_agent(
        merged_decision_fn=merged_decision_fn,
        continue_decider_fn=continue_decider_fn,
        slow_llm_chat_fn=_slow_chat,
        min_silence=0.02,  # filler fires → "standard" path
    )

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg), timeout=3.0
    )

    # slow LLM called only once (v1, no v2).
    assert slow_calls == 1, f"Expected slow_llm called once (v1 only), got {slow_calls}"

    # turn_complete log must be emitted with path == "standard".
    turn_complete_records = [
        r for r in caplog.records if r.getMessage() == "turn_complete"
    ]
    assert turn_complete_records, "turn_complete log missing"
    assert getattr(turn_complete_records[-1], "path", None) == "standard", (
        f"Expected path='standard', got "
        f"{getattr(turn_complete_records[-1], 'path', None)!r}"
    )

    # dp_continue_no log was emitted.
    dp_no_records = [r for r in caplog.records if r.getMessage() == "dp_continue_no"]
    assert dp_no_records, "dp_continue_no log missing"


# ── Test 3: dp_continue timeout → treated as no ─────────────────────────────


@pytest.mark.asyncio
async def test_dp_continue_timeout_treated_as_no(monkeypatch, caplog):
    """F1 §8 F8 case 3: continue_decider blocks > 200 ms hard timeout.

    We use the REAL ``should_continue`` so the asyncio.wait_for timeout path
    fires, with ``_call_doubao`` patched to a 500 ms sleep.  The fallback must
    be ``yes=False, reason='timeout'`` — slow_v2 must NOT run.
    """
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    caplog.set_level("ERROR", logger="voice.decisions.continue_decider")

    from backend.voice.decisions import continue_decider as cd_mod

    async def _slow_call(**kwargs):
        await asyncio.sleep(0.5)  # 500 ms — well past the 200 ms hard timeout
        return '{"yes": true, "reason": "should not arrive"}'

    monkeypatch.setattr(cd_mod, "_call_doubao", _slow_call)
    monkeypatch.setattr(cd_mod, "DP_CONTINUE_TIMEOUT_MS", 100)
    # Note: ``should_continue`` reads DP_CONTINUE_TIMEOUT_MS at call time, so
    # the patched 100 ms takes effect immediately.

    merged_decision_fn = AsyncMock(return_value=MergedDecisionResult())

    slow_calls = 0

    async def _slow_chat(messages: list[dict]) -> str:
        nonlocal slow_calls
        slow_calls += 1
        return "slow_v1"

    agent = _make_agent(
        merged_decision_fn=merged_decision_fn,
        continue_decider_fn=cd_mod.should_continue,
        slow_llm_chat_fn=_slow_chat,
        min_silence=0.02,
    )

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg), timeout=3.0
    )

    # slow LLM called only once — slow_v2 must NOT have run.
    assert slow_calls == 1, (
        f"slow_v2 must NOT run on DP-continue timeout; got slow_calls={slow_calls}"
    )

    # ContinueDecider logged the timeout fallback at ERROR level.
    timeout_records = [
        r for r in caplog.records if r.getMessage() == "continue_decider_timeout"
    ]
    assert timeout_records, "continue_decider_timeout log missing"


# ── Test 4: slow_v2 system prompt embeds skill text from merged_decision ────


@pytest.mark.asyncio
async def test_slow_v2_uses_skill_from_merged_decision():
    """F1 §8 F8 case 4: skill_router.load_skill_content is invoked with the
    merged-decision skill name and its return value is embedded in the slow_v2
    system prompt."""
    skill_content = "FAKE_LISTEN_SKILL_BODY_TOKEN_42"
    skill_router = _make_skill_router_mock(skill_content=skill_content)

    merged_decision_fn = AsyncMock(
        return_value=MergedDecisionResult(skill="listen", latency_ms=10.0)
    )
    continue_decider_fn = AsyncMock(
        return_value=ContinueDecision(yes=True, reason="needs_deeper", latency_ms=18.0)
    )

    captured_v2_system: dict[str, str] = {}
    call_idx = 0

    async def _slow_chat(messages: list[dict]) -> str:
        nonlocal call_idx
        call_idx += 1
        if call_idx == 2:  # second call is slow_v2
            captured_v2_system["content"] = messages[0]["content"]
        return f"slow_response_{call_idx}"

    agent = _make_agent(
        merged_decision_fn=merged_decision_fn,
        continue_decider_fn=continue_decider_fn,
        slow_llm_chat_fn=_slow_chat,
        skill_router=skill_router,
        min_silence=0.02,
    )

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg), timeout=3.0
    )

    skill_router.load_skill_content.assert_called_once_with("listen")
    assert "content" in captured_v2_system, "slow_v2 was not invoked"
    assert skill_content in captured_v2_system["content"], (
        f"Skill content not injected into slow_v2 system prompt. "
        f"Got:\n{captured_v2_system['content']!r}"
    )
    # Base instructions still present (skill is appended, not replacing).
    assert "You are a helpful assistant." in captured_v2_system["content"]


# ── Test 5: short path — filler skipped, decisions still run ────────────────


@pytest.mark.asyncio
async def test_short_path_skips_filler_but_runs_decisions(caplog):
    """F1 §8 F8 case 5: slow_v1 fast → filler skipped, but merged_decision still
    runs in parallel (logged) AND continue_decider STILL called after slow_v1.
    """
    caplog.set_level("INFO", logger="voice.fast_slow_agent")

    merged_decision_fn = AsyncMock(return_value=MergedDecisionResult())
    continue_decider_fn = AsyncMock(
        return_value=ContinueDecision(yes=False, reason="ok", latency_ms=18.0)
    )

    async def _fast_slow_chat(messages: list[dict]) -> str:
        # No await — slow_v1 returns immediately, simulating a < 0.4 s TTFT.
        return "slow_v1 fast"

    fast_llm = _make_fast_llm("不应触发的填充语")

    agent = _make_agent(
        fast_llm=fast_llm,
        merged_decision_fn=merged_decision_fn,
        continue_decider_fn=continue_decider_fn,
        slow_llm_chat_fn=_fast_slow_chat,
        min_silence=0.5,  # 500 ms window so slow finishing immediately wins
    )

    # Custom _run_slow that flips the first-token flag fast (simulating LiveKit
    # streaming contract): so _maybe_filler will skip when the timer fires.
    real_run_slow = agent._run_slow

    async def _flagging_run_slow(turn_ctx, session_id, turn_id):
        agent._slow_first_token_emitted = True
        await real_run_slow(turn_ctx, session_id, turn_id)

    agent._run_slow = _flagging_run_slow  # type: ignore[method-assign]

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg), timeout=3.0
    )

    # Filler must NOT have fired — fast LLM (filler) call_count == 0 and
    # session.say not invoked.
    assert fast_llm.chat.completions.create.call_count == 0, (
        "Filler LLM must not be called on the short path"
    )
    assert agent.session.say.call_count == 0, (
        "session.say must not be called on the short path"
    )
    assert agent._turn_filler_count == 0

    # merged_decision STILL ran in parallel.
    merged_decision_fn.assert_awaited_once()
    merged_dispatched = [
        r for r in caplog.records if r.getMessage() == "merged_decision_dispatched"
    ]
    assert merged_dispatched, "merged_decision_dispatched log missing"
    merged_done = [
        r for r in caplog.records if r.getMessage() == "merged_decision_done"
    ]
    assert merged_done, "merged_decision_done log missing"

    # continue_decider STILL called after slow_v1 (regardless of fast path).
    continue_decider_fn.assert_awaited_once()

    # Path is "short" since no filler fired AND continue=no.
    turn_complete_records = [
        r for r in caplog.records if r.getMessage() == "turn_complete"
    ]
    assert turn_complete_records, "turn_complete log missing"
    assert getattr(turn_complete_records[-1], "path", None) == "short", (
        f"Expected path='short', got "
        f"{getattr(turn_complete_records[-1], 'path', None)!r}"
    )
