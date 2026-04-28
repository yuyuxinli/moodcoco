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


# ── Test 1: filler fires after silence ────────────────────────────────────────


@pytest.mark.asyncio
async def test_filler_fires_after_silence():
    """Mock slow LLM never sets first-token flag; filler must fire after silence window.

    F1 §8 F5 case 2 (standard path): slow delays > min_silence → filler sent once,
    turn_ctx has assistant filler message.
    """
    filler_text = "嗯，听起来不太好受"
    agent = _make_agent(min_silence=0.02, filler_text=filler_text)  # 20 ms silence window

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    # _run_slow will be a no-op (default impl just yields and logs).
    # slow_first_token_emitted stays False so filler fires.

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg),
        timeout=3.0,
    )

    # session.say must have been called exactly once (for the filler).
    session_say = agent.session.say
    assert session_say.call_count == 1, (
        f"Expected session.say called once for filler, got {session_say.call_count}"
    )

    # filler count incremented to 1.
    assert agent._turn_filler_count == 1

    # chat_ctx must have one assistant message with filler text (OQ-13).
    assistant_msgs = [m for m in ctx.messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert filler_text in assistant_msgs[0]["content"] or assistant_msgs[0]["content"] in filler_text


# ── Test 2: filler skipped if slow emits first token quickly ─────────────────


@pytest.mark.asyncio
async def test_filler_skipped_if_slow_fast():
    """Slow LLM emits first token flag within the silence window → filler NOT called.

    F1 §8 F5 case 1 (short path): slow fast enough → session.say not invoked.
    """
    agent = _make_agent(min_silence=0.1)  # 100 ms window

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    # Simulate slow_v1 setting the flag within 30 ms (before the 100 ms timer).
    original_run_slow = agent._run_slow

    async def _fast_slow(*args, **kwargs):
        await asyncio.sleep(0.03)  # 30 ms — before 100 ms filler timer
        agent._slow_first_token_emitted = True
        await original_run_slow(*args, **kwargs)

    agent._run_slow = _fast_slow  # type: ignore[method-assign]

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg),
        timeout=3.0,
    )

    # session.say must NOT have been called (filler was skipped).
    session_say = agent.session.say
    assert session_say.call_count == 0, (
        f"Expected session.say NOT called (slow was fast), got {session_say.call_count}"
    )

    assert agent._turn_filler_count == 0


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
async def test_chat_ctx_writeback_after_filler():
    """After filler emitted, turn_ctx must have an assistant message with filler content.

    F1 §8 F5 case 5 / OQ-13 contract: write-back ordering is maintained.
    """
    filler_text = "稍等一下，让我想想"
    agent = _make_agent(min_silence=0.01, filler_text=filler_text)

    ctx = _make_chat_context()
    user_msg = _make_user_message("我有些担心")

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg),
        timeout=3.0,
    )

    # Verify the filler was written into the chat context.
    assistant_msgs = [m for m in ctx.messages if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1, "Expected at least one assistant message in turn_ctx"

    # The first assistant message should contain the filler text (or part of it).
    first_content = assistant_msgs[0]["content"]
    assert filler_text in first_content or first_content in filler_text, (
        f"Filler text not found in chat_ctx. Got: {first_content!r}, expected: {filler_text!r}"
    )


# ── Test 5: session_id and turn_id propagated via contextvars ─────────────────


@pytest.mark.asyncio
async def test_session_id_turn_id_propagated():
    """voice_session_ctx and voice_turn_ctx must be set inside the agent turn.

    F1 §8 F5 case 4 / OQ-14 contract: contextvars set by FastSlowAgent for F3 plugin.
    We spy on the contextvars from inside the filler generator.
    """
    from backend.voice.fast_slow_agent import voice_session_ctx, voice_turn_ctx

    captured_session_id: list[str | None] = []
    captured_turn_id: list[str | None] = []

    fast_llm = MagicMock()
    fast_llm.chat = MagicMock()
    fast_llm.chat.completions = MagicMock()

    async def _spy_create(**kwargs):
        # Capture contextvar values when the filler LLM is called.
        captured_session_id.append(voice_session_ctx.get())
        captured_turn_id.append(voice_turn_ctx.get())

        async def _gen():
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = "好的"
            yield chunk

        return _gen()

    fast_llm.chat.completions.create = AsyncMock(side_effect=_spy_create)

    agent = _make_agent(fast_llm=fast_llm, min_silence=0.01)

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg),
        timeout=3.0,
    )

    # The contextvar must have been set before the filler LLM was called.
    assert len(captured_session_id) >= 1, (
        "Filler LLM was not called (voice_session_ctx not captured). "
        "Ensure filler fired (min_silence short enough)."
    )
    assert captured_session_id[0] is not None, (
        f"voice_session_ctx was None inside filler; expected room name. Got: {captured_session_id}"
    )
    assert captured_turn_id[0] is not None, (
        f"voice_turn_ctx was None inside filler; expected turn_id hex. Got: {captured_turn_id}"
    )
    # session_id should be the room name set by the mock.
    assert captured_session_id[0] == "test-room-001", (
        f"Expected session_id='test-room-001', got: {captured_session_id[0]!r}"
    )
    # turn_id should be an 8-char hex string.
    assert len(captured_turn_id[0]) == 8, (
        f"Expected 8-char hex turn_id, got: {captured_turn_id[0]!r}"
    )


# ── Test 6: F1 §8 case 4 — both fast AND slow LLMs invoked ───────────────────


@pytest.mark.asyncio
async def test_both_fast_and_slow_invoked_in_standard_path():
    """F1 §8 case 4: standard path → fast LLM (filler) called once + slow LLM
    called once.  The round-1 file dropped this case (no test exercised a
    mocked ``slow_llm``), so this pins the contract.

    The F5 skeleton's ``_run_slow`` is a stub; we override it with a thin shim
    that calls ``slow_llm.chat`` to simulate F8 wiring.  The standard path
    must produce: fast filler dispatched once + slow LLM exercised once +
    write-back landed in chat_ctx.
    """
    filler_text = "嗯，我在听"
    fast_llm = _make_fast_llm(filler_text)
    slow_llm = MagicMock()
    slow_llm.chat = AsyncMock(return_value="slow_v1 response")

    agent = _make_agent(fast_llm=fast_llm, min_silence=0.02, filler_text=filler_text)

    async def _real_run_slow(turn_ctx, session_id, turn_id):
        await slow_llm.chat()

    agent._run_slow = _real_run_slow  # type: ignore[method-assign]

    ctx = _make_chat_context()
    user_msg = _make_user_message()

    await asyncio.wait_for(
        agent.on_user_turn_completed(ctx, user_msg), timeout=3.0
    )

    # Fast LLM (filler) invoked exactly once.
    assert fast_llm.chat.completions.create.call_count == 1, (
        f"Fast LLM expected 1 call, got {fast_llm.chat.completions.create.call_count}"
    )
    # Slow LLM invoked exactly once.
    assert slow_llm.chat.call_count == 1, (
        f"Slow LLM expected 1 call, got {slow_llm.chat.call_count}"
    )
    # Filler dispatched + write-back landed.
    assert agent.session.say.call_count == 1
    assert agent._turn_filler_count == 1
    assistant_msgs = [m for m in ctx.messages if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] == filler_text
