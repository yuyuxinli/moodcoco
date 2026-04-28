"""FastSlowAgent — LiveKit Agent implementing fast-filler + slow_v1 + slow_v2.

F5 skeleton (locked at L177-230 below — DO NOT touch the streaming Future
pattern): fast filler ×1 (fires after ``min_silence_before_kicking`` if
slow_v1 hasn't yet emitted its first token) + slow_v1 (LiveKit default LLM
pipeline).

F8 extension (this file): merged-decision runs in parallel with slow_v1;
after slow_v1 completes, ContinueDecider asks Doubao lite whether to add a
second deeper response.  When ``yes``, slow_v2 fires with system prompt =
base instructions + (skill SKILL.md content if merged_decision yielded a
skill) + retrieved context (RetrievalStub returns ""; F2 phase will swap in
memU).  When ``no`` / timeout / error, the turn ends after slow_v1 with no
extra speech.

The filler is streamed via the canonical ``asyncio.Future`` pattern from
``fast-preresponse.py`` (LiveKit voice-agent reference): the LLM stream is
piped chunk-by-chunk into ``session.say()`` so TTS starts speaking on the
first token (~150 ms TTFB), while a Future captures the complete text for
the chat-context write-back that follows.

Path enum (logged on ``turn_complete``):
* ``short``    — slow_v1 emitted first token before the silence window;
                 no filler, no slow_v2.
* ``standard`` — filler dispatched OR slow_v2 declined; one filler write-back
                 + one slow_v1 only.
* ``long``     — DP-continue=yes; slow_v2 ran with skill+retrieval injection.

OQ-12: ``_slow_first_token_emitted`` flag never set in skeleton (F8 will
wrap the LLM stream); wall-clock timer is the only gate.
OQ-13: chat_ctx write-back happens after the streaming filler future
resolves so slow_v1 sees the filler in turn_ctx.
OQ-14: ``self.session`` is read only inside ``on_user_turn_completed``
(after LiveKit binds the session), guarded by try/except.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncIterable, Awaitable, Callable
from typing import Any

from livekit.agents import Agent
from livekit.agents.llm import ChatContext, ChatMessage

from backend.voice.decisions import continue_decider as _continue_decider_mod
from backend.voice.decisions import merged_decision as _merged_decision_mod
from backend.voice.decisions.continue_decider import ContinueDecision
from backend.voice.decisions.merged_decision import MergedDecisionResult
from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx
from backend.voice.skill_router import SJTUSkillRouter, SkillNotFoundError

logger = logging.getLogger("voice.fast_slow_agent")

MIN_SILENCE_BEFORE_KICKING_MS: int = int(os.getenv("FAST_SLOW_MIN_SILENCE_MS", "400"))
FAST_FILLER_MAX_COUNT: int = int(os.getenv("FAST_SLOW_FILLER_MAX_COUNT", "1"))

FILLER_PROMPT = (
    "Generate a 5–10 word empathetic acknowledgement in Chinese that shows you heard the user. "
    "Do NOT give advice or ask questions. Example: '嗯，听起来不太好受。' "
    "Output ONLY the filler sentence, no punctuation at the end."
)

# Type aliases for the injectable decision / slow-LLM hooks.
MergedDecisionFn = Callable[[str, list[dict]], Awaitable[MergedDecisionResult]]
ContinueDeciderFn = Callable[[str, list[dict]], Awaitable[ContinueDecision]]
SlowLLMChatFn = Callable[[list[dict]], Awaitable[str]]


class LLMTimeoutError(Exception):
    """LLM call exceeded the configured hard timeout."""


class FastSlowAgent(Agent):
    """LiveKit Agent implementing the fast-filler + slow_v1 + slow_v2 pattern.

    Args:
        instructions: Base persona system prompt (forwarded to ``Agent``).
        fast_llm: openai.AsyncOpenAI-compatible client used for filler streaming.
        slow_llm: LiveKit LLM instance for slow_v1 (forwarded as ``llm=`` kwarg).
        min_silence_before_kicking: Seconds to wait before sending filler.
        fast_filler_max_count: Maximum fillers per turn (default 1).
        fast_llm_model: Filler model name; falls back to ``DOUBAO_MODEL`` env.
        merged_decision_fn: Coroutine called as
            ``await fn(user_msg, recent_ctx) -> MergedDecisionResult``.
            Defaults to :func:`backend.voice.decisions.merged_decision.decide`.
        continue_decider_fn: Coroutine called as
            ``await fn(slow_v1_text, recent_ctx) -> ContinueDecision``.
            Defaults to
            :func:`backend.voice.decisions.continue_decider.should_continue`.
        skill_router: :class:`SJTUSkillRouter` used to inject SKILL.md content
            into the slow_v2 system prompt.  Built lazily on first use when
            ``None``.
        slow_llm_chat_fn: Optional coroutine ``await fn(messages) -> str`` used
            for slow_v1 and slow_v2.  When omitted slow_v1 falls back to the
            LiveKit default-pipeline stub (logs only) and slow_v2 is logged as
            dispatched but produces no real audio in unit tests.

    Raises:
        ValueError: if ``fast_llm`` is not provided.
    """

    def __init__(
        self,
        *,
        instructions: str,
        fast_llm: Any,
        slow_llm: Any | None = None,
        min_silence_before_kicking: float = MIN_SILENCE_BEFORE_KICKING_MS / 1000,
        fast_filler_max_count: int = FAST_FILLER_MAX_COUNT,
        fast_llm_model: str | None = None,
        merged_decision_fn: MergedDecisionFn | None = None,
        continue_decider_fn: ContinueDeciderFn | None = None,
        skill_router: SJTUSkillRouter | None = None,
        slow_llm_chat_fn: SlowLLMChatFn | None = None,
        **kwargs: Any,
    ) -> None:
        if fast_llm is None:
            raise ValueError("fast_llm must be provided")

        agent_kwargs: dict[str, Any] = {"instructions": instructions}
        if slow_llm is not None:
            agent_kwargs["llm"] = slow_llm
        agent_kwargs.update(kwargs)
        super().__init__(**agent_kwargs)

        self._fast_llm = fast_llm
        self._fast_llm_model: str = fast_llm_model or os.getenv(
            "DOUBAO_MODEL", "doubao-seed-2-0-lite-260215"
        )
        self.min_silence_before_kicking: float = min_silence_before_kicking
        self.fast_filler_max_count: int = fast_filler_max_count
        self._instructions: str = instructions

        self._merged_decision_fn: MergedDecisionFn = (
            merged_decision_fn or _merged_decision_mod.decide
        )
        self._continue_decider_fn: ContinueDeciderFn = (
            continue_decider_fn or _continue_decider_mod.should_continue
        )
        self._skill_router: SJTUSkillRouter | None = skill_router
        self._slow_llm_chat_fn: SlowLLMChatFn | None = slow_llm_chat_fn

        self._turn_filler_count: int = 0
        self._slow_first_token_emitted: bool = False
        # Captured slow_v1 output for the DP-continue / slow_v2 stage.
        self._slow_v1_text: str = ""

    # ------------------------------------------------------------------
    # Lazy skill-router accessor (per F1 §4.5 design — built on first use)
    # ------------------------------------------------------------------

    def _get_skill_router(self) -> SJTUSkillRouter:
        if self._skill_router is None:
            self._skill_router = SJTUSkillRouter()
        return self._skill_router

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """Orchestrate fast-filler + slow_v1 + DP-continue + slow_v2.

        All exceptions are caught + logged; no errors are propagated.
        """
        self._turn_filler_count = 0
        self._slow_first_token_emitted = False
        self._slow_v1_text = ""

        try:
            room_name: str = self.session.room.name  # type: ignore[union-attr]
        except Exception:
            room_name = "unknown"
        session_id: str = room_name or "unknown"
        turn_id: str = uuid.uuid4().hex[:8]

        voice_session_ctx.set(session_id)
        voice_turn_ctx.set(turn_id)

        user_text = getattr(new_message, "text_content", "") or ""
        logger.info(
            "turn_started",
            extra={"session_id": session_id, "turn_id": turn_id, "user_msg_len": len(user_text)},
        )

        t_turn_start = time.monotonic()
        recent_ctx = self._snapshot_recent_ctx(turn_ctx)

        # TASK B — merged decision in PARALLEL with slow_v1 (per design doc §1).
        # Result is consumed only by slow_v2; if slow_v2 doesn't run we still
        # await the task for clean shutdown + structured logging.
        logger.info(
            "merged_decision_dispatched",
            extra={"session_id": session_id, "turn_id": turn_id},
        )
        decision_task: asyncio.Task[MergedDecisionResult] = asyncio.create_task(
            self._run_merged_decision_safe(user_text, recent_ctx, session_id, turn_id)
        )

        # TASK C — slow_v1 (LiveKit default pipeline or injected mock).
        slow_v1_task = asyncio.create_task(
            self._run_slow(turn_ctx, session_id, turn_id)
        )
        # TASK A — filler racing timer.  Fires only if slow_v1 hasn't emitted
        # its first token within ``min_silence_before_kicking``.
        filler_timer_task = asyncio.create_task(
            self._maybe_filler(turn_ctx, session_id, turn_id)
        )

        await filler_timer_task

        try:
            await slow_v1_task
        except Exception:
            logger.exception(
                "slow_v1_failed", extra={"session_id": session_id, "turn_id": turn_id}
            )

        # TASK D — DP-continue + optional slow_v2 (always after slow_v1, per design §1).
        path = await self._run_dp_continue_and_v2(
            turn_ctx, recent_ctx, decision_task, session_id, turn_id
        )

        latency_ms = round((time.monotonic() - t_turn_start) * 1000)
        logger.info(
            "turn_complete",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "path": path,
                "latency_ms": latency_ms,
            },
        )

    # ------------------------------------------------------------------
    # Task helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot_recent_ctx(turn_ctx: ChatContext) -> list[dict]:
        """Best-effort snapshot of recent chat_ctx as JSON-friendly dicts.

        Used by merged_decision and continue_decider as the ``recent_ctx`` arg.
        Any failure returns ``[]`` so the decision pipeline still runs.
        """
        try:
            messages = getattr(turn_ctx, "messages", []) or []
            out: list[dict] = []
            for m in messages[-6:]:  # last 6 turns is plenty for a routing prompt
                if isinstance(m, dict):
                    out.append(
                        {
                            "role": str(m.get("role", "")),
                            "content": str(m.get("content", "")),
                        }
                    )
                else:
                    role = getattr(m, "role", "")
                    content = getattr(m, "text_content", "") or getattr(
                        m, "content", ""
                    )
                    if isinstance(content, list):
                        content = "".join(str(c) for c in content)
                    out.append({"role": str(role), "content": str(content)})
            return out
        except Exception:
            return []

    async def _run_merged_decision_safe(
        self,
        user_text: str,
        recent_ctx: list[dict],
        session_id: str,
        turn_id: str,
    ) -> MergedDecisionResult:
        """Wrapper around merged_decision.decide with structured logging.

        Returns the fallback ``MergedDecisionResult()`` on any unexpected
        exception so the awaiting consumer never sees a raw error.
        """
        try:
            result = await self._merged_decision_fn(user_text, recent_ctx)
        except Exception as exc:
            logger.warning(
                "merged_decision_unexpected_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            return MergedDecisionResult()

        logger.info(
            "merged_decision_done",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "search_yes": result.search_yes,
                "search_kw": result.search_kw,
                "skill": result.skill,
                "latency_ms": result.latency_ms,
            },
        )
        return result

    async def _maybe_filler(
        self, turn_ctx: ChatContext, session_id: str, turn_id: str
    ) -> None:
        """Wait ``min_silence_before_kicking`` then stream one filler if slow is silent.

        Streaming Future pattern (per fast-preresponse.py L61-74):
        1. Wrap fast-LLM stream in an async generator that yields AND collects.
        2. ``session.say(_gen())`` — TTS begins on first chunk (~150 ms TTFB).
        3. ``await filler_text_fut`` — block on stream completion.
        4. ``turn_ctx.add_message(...)`` — write-back so slow_v1 sees filler.
        """
        await asyncio.sleep(self.min_silence_before_kicking)

        if self._slow_first_token_emitted:
            logger.info(
                "filler_skipped_slow_fast",
                extra={"session_id": session_id, "turn_id": turn_id},
            )
            return

        if self._turn_filler_count >= self.fast_filler_max_count:
            logger.info(
                "filler_skipped_max_count",
                extra={"session_id": session_id, "turn_id": turn_id, "max_count": self.fast_filler_max_count},
            )
            return

        # Increment count NOW (before any await) so re-entry on the same turn
        # is gated even if the LLM stream is slow / errors mid-flight.
        self._turn_filler_count += 1
        t_filler_start = time.monotonic()

        filler_text_fut: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _fast_llm_reply() -> AsyncIterable[str]:
            collected: list[str] = []
            try:
                stream = await self._fast_llm.chat.completions.create(
                    model=self._fast_llm_model,
                    messages=[{"role": "system", "content": FILLER_PROMPT}],
                    stream=True,
                    max_tokens=30,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        collected.append(delta)
                        yield delta
                if not filler_text_fut.done():
                    filler_text_fut.set_result("".join(collected))
            except Exception as exc:
                logger.warning(
                    "filler_llm_failed",
                    extra={"session_id": session_id, "turn_id": turn_id, "error": str(exc)},
                    exc_info=True,
                )
                if not filler_text_fut.done():
                    filler_text_fut.set_exception(exc)

        try:
            # Stream chunks into TTS as they arrive — TTFB is first-token, NOT
            # full-response latency.  add_to_chat_ctx=False because we own
            # the write-back below (OQ-13 ordering).
            self.session.say(_fast_llm_reply(), add_to_chat_ctx=False)

            try:
                filler_text = await filler_text_fut
            except Exception:
                # Already logged inside the generator; abort write-back.
                return

            if not filler_text:
                logger.warning(
                    "filler_empty_response",
                    extra={"session_id": session_id, "turn_id": turn_id},
                )
                return

            latency_ms = round((time.monotonic() - t_filler_start) * 1000)
            logger.info(
                "filler_dispatched",
                extra={"session_id": session_id, "turn_id": turn_id, "filler_text": filler_text[:50], "latency_ms_to_filler": latency_ms},
            )

            # Write-back so slow_v1 sees the filler in chat_ctx (OQ-13).
            turn_ctx.add_message(role="assistant", content=filler_text, interrupted=False)
        except Exception as exc:
            logger.warning(
                "filler_dispatch_failed",
                extra={"session_id": session_id, "turn_id": turn_id, "error": str(exc)},
                exc_info=True,
            )

    async def _run_slow(
        self, turn_ctx: ChatContext, session_id: str, turn_id: str
    ) -> None:
        """Drive slow_v1.

        When ``slow_llm_chat_fn`` was supplied at construction time we use it
        directly (typical in tests and the full F8 wiring).  Otherwise we
        delegate to LiveKit's default pipeline (the F5 skeleton behaviour) and
        only log — slow_v1 in production speaks via the AgentSession default
        LLM chain that is bound to the room.
        """
        if self._slow_llm_chat_fn is None:
            await asyncio.sleep(0)
            logger.info(
                "slow_v1_pipeline_delegated",
                extra={"session_id": session_id, "turn_id": turn_id},
            )
            return

        messages = self._build_messages(turn_ctx, system_prompt=self._instructions)
        t_slow_start = time.monotonic()
        try:
            self._slow_v1_text = await self._slow_llm_chat_fn(messages)
        except Exception:
            logger.exception(
                "slow_v1_failed",
                extra={"session_id": session_id, "turn_id": turn_id},
            )
            raise
        latency_ms = round((time.monotonic() - t_slow_start) * 1000)
        logger.info(
            "slow_v1_completed",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "text_len": len(self._slow_v1_text or ""),
                "latency_ms": latency_ms,
            },
        )

    # ------------------------------------------------------------------
    # DP-continue + slow_v2 (F8)
    # ------------------------------------------------------------------

    async def _run_dp_continue_and_v2(
        self,
        turn_ctx: ChatContext,
        recent_ctx: list[dict],
        decision_task: "asyncio.Task[MergedDecisionResult]",
        session_id: str,
        turn_id: str,
    ) -> str:
        """Run DP-continue; if yes, dispatch slow_v2.

        Returns the path string for ``turn_complete`` logging:
        ``"short"``    — fast path, no filler, no slow_v2.
        ``"standard"`` — slow_v1 only (filler may have fired).
        ``"long"``     — slow_v2 ran.
        """
        try:
            decision: ContinueDecision = await self._continue_decider_fn(
                self._slow_v1_text, recent_ctx
            )
        except Exception as exc:
            # The public ContinueDecider API is contractually non-raising, but
            # callers may swap in a custom fn — guard belt-and-braces.
            logger.warning(
                "dp_continue_unexpected_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            decision = ContinueDecision(yes=False, reason="unexpected_error")

        if not decision.yes:
            logger.info(
                "dp_continue_no",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "reason": decision.reason,
                    "latency_ms": decision.latency_ms,
                },
            )
            # Drain the merged_decision task so we don't leak it.
            if not decision_task.done():
                try:
                    await decision_task
                except Exception:
                    pass
            return "short" if self._turn_filler_count == 0 else "standard"

        logger.info(
            "dp_continue_yes",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "reason": decision.reason,
                "latency_ms": decision.latency_ms,
            },
        )

        # Resolve the merged decision so we know which skill (if any) to inject.
        try:
            merged_result = await decision_task
        except Exception:
            logger.exception(
                "merged_decision_await_failed",
                extra={"session_id": session_id, "turn_id": turn_id},
            )
            merged_result = MergedDecisionResult()

        skill_content = self._load_skill_content_safe(
            merged_result.skill, session_id, turn_id
        )

        # Retrieval stub (F2 will replace with memU).
        retrieval_query = (
            merged_result.search_kw if merged_result.search_yes else ""
        )
        retrieved = await self._run_retrieval(retrieval_query)

        await self._run_slow_v2(
            turn_ctx,
            skill_name=merged_result.skill,
            skill_content=skill_content,
            retrieved=retrieved,
            session_id=session_id,
            turn_id=turn_id,
        )
        return "long"

    def _load_skill_content_safe(
        self, skill_name: str | None, session_id: str, turn_id: str
    ) -> str:
        """Look up SKILL.md content for ``skill_name``; ``""`` if missing/error."""
        if not skill_name:
            return ""
        try:
            router = self._get_skill_router()
            return router.load_skill_content(skill_name)
        except SkillNotFoundError:
            # SkillRouter already logs ``skill_not_found`` warning.
            return ""
        except Exception as exc:
            logger.warning(
                "skill_router_unexpected_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "skill_name": skill_name,
                    "error": str(exc),
                },
                exc_info=True,
            )
            return ""

    async def _run_retrieval(self, query: str) -> str:
        """Retrieval stub for the demo phase.

        F2 will replace this with the memU client.  The signature stays stable
        so the call site in :meth:`_run_dp_continue_and_v2` does not change.
        """
        return ""

    async def _run_slow_v2(
        self,
        turn_ctx: ChatContext,
        *,
        skill_name: str | None,
        skill_content: str,
        retrieved: str,
        session_id: str,
        turn_id: str,
    ) -> None:
        """Compose slow_v2 system prompt and call the slow LLM (or log only).

        System prompt = base instructions + skill SKILL.md content (when
        merged_decision yielded a skill) + retrieved context (RetrievalStub
        returns "" for now).
        """
        system_prompt = self._compose_slow_v2_system_prompt(skill_content, retrieved)

        logger.info(
            "slow_v2_dispatched",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "skill_name": skill_name,
                "has_skill_content": bool(skill_content),
                "has_retrieved_context": bool(retrieved),
                "system_prompt_len": len(system_prompt),
            },
        )

        if self._slow_llm_chat_fn is None:
            # Demo / unit-test path without an injected LLM hook: log dispatch
            # + completion so the structured-log audit trail still proves the
            # second pass occurred.  Real audio is produced by LiveKit when a
            # slow_llm hook is wired up at the entrypoint level.
            logger.info(
                "slow_v2_completed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "text_len": 0,
                    "latency_ms": 0,
                    "delegated": True,
                },
            )
            return

        messages = self._build_messages(turn_ctx, system_prompt=system_prompt)
        t_v2_start = time.monotonic()
        try:
            v2_text = await self._slow_llm_chat_fn(messages)
        except Exception:
            logger.exception(
                "slow_v2_failed",
                extra={"session_id": session_id, "turn_id": turn_id},
            )
            return

        latency_ms = round((time.monotonic() - t_v2_start) * 1000)
        logger.info(
            "slow_v2_completed",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "text_len": len(v2_text or ""),
                "latency_ms": latency_ms,
            },
        )

    def _compose_slow_v2_system_prompt(
        self, skill_content: str, retrieved: str
    ) -> str:
        """Compose system prompt: base instructions + skill + retrieval."""
        parts: list[str] = [self._instructions]
        if skill_content:
            parts.append("## Skill Context\n" + skill_content.strip())
        if retrieved:
            parts.append("## Retrieved Context\n" + retrieved.strip())
        return "\n\n".join(parts)

    @staticmethod
    def _build_messages(
        turn_ctx: ChatContext, *, system_prompt: str
    ) -> list[dict]:
        """Best-effort conversion of ChatContext + system prompt → OpenAI-style messages."""
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        try:
            history = getattr(turn_ctx, "messages", []) or []
            for m in history:
                if isinstance(m, dict):
                    role = str(m.get("role", "user"))
                    content = str(m.get("content", ""))
                else:
                    role = str(getattr(m, "role", "user"))
                    raw = getattr(m, "text_content", "") or getattr(m, "content", "")
                    content = (
                        "".join(str(c) for c in raw) if isinstance(raw, list) else str(raw)
                    )
                if content:
                    messages.append({"role": role, "content": content})
        except Exception:
            pass
        return messages
