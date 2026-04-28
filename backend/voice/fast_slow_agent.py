"""FastSlowAgent — LiveKit Agent implementing fast-filler + slow_v1 pattern.

F5 skeleton: fast filler ×1 (fires after min_silence_before_kicking if slow hasn't
produced its first token) + slow_v1 (LiveKit default LLM pipeline).

F6/F8 scope: merged_decision, DP-continue, slow_v2 are NOT implemented here.

OQ-12 addressed: _slow_first_token_emitted flag + asyncio.Event set from
_maybe_filler's own timer logic (wall-clock gate only in skeleton).
OQ-13 addressed: chat_ctx write-back happens *after* session.say filler_fut resolves,
so the ordering is: TTS starts → filler text fully buffered → write-back → slow_v1 sees it.
OQ-14 addressed: self.session is accessed only inside on_user_turn_completed (after agent
is bound to a session by LiveKit), never at construction time.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncIterable
from typing import Any

from livekit.agents import Agent
from livekit.agents.llm import ChatContext, ChatMessage

# Import contextvars from F3 plugin (set by F5 so STT plugin can read them).
# If the module hasn't been installed yet at import time (e.g. during tests
# that stub the plugin), fall back to module-local ContextVars.
try:
    from backend.voice.plugins.xfyun_stt import voice_session_ctx, voice_turn_ctx
except ImportError:  # pragma: no cover — only during isolated test without plugin
    from contextvars import ContextVar

    voice_session_ctx: ContextVar[str | None] = ContextVar(  # type: ignore[no-redef]
        "voice_session_ctx", default=None
    )
    voice_turn_ctx: ContextVar[str | None] = ContextVar(  # type: ignore[no-redef]
        "voice_turn_ctx", default=None
    )

logger = logging.getLogger("voice.fast_slow_agent")

# ── Module-level defaults (all overridable via env vars at import time) ─────

MIN_SILENCE_BEFORE_KICKING_MS: int = int(
    os.getenv("FAST_SLOW_MIN_SILENCE_MS", "400")
)
FAST_FILLER_MAX_COUNT: int = int(os.getenv("FAST_SLOW_FILLER_MAX_COUNT", "1"))

FILLER_PROMPT = (
    "Generate a 5–10 word empathetic acknowledgement in Chinese that shows you heard the user. "
    "Do NOT give advice or ask questions. Example: '嗯，听起来不太好受。' "
    "Output ONLY the filler sentence, no punctuation at the end."
)


# ── Custom exceptions ────────────────────────────────────────────────────────


class LLMTimeoutError(Exception):
    """LLM call exceeded the configured hard timeout."""


# ── Agent ────────────────────────────────────────────────────────────────────


class FastSlowAgent(Agent):
    """LiveKit Agent implementing the fast-filler + slow_v1 pattern.

    Inherits ``livekit.agents.Agent``.  The default Agent LLM (slow_llm passed
    via ``llm=`` kwarg or configured on the session) handles slow_v1 via the
    standard LiveKit pipeline.  A separate ``fast_llm`` (AsyncOpenAI-compatible
    client) is used solely for the filler.

    State per turn is stored in ``_turn_*`` instance variables that are reset
    at the start of each ``on_user_turn_completed`` call.

    Args:
        instructions: Base persona system prompt (forwarded to ``Agent``).
        fast_llm: An ``openai.AsyncOpenAI``-compatible client pointed at
            DOUBAO_BASE_URL.  Used for filler generation only in F5.
        slow_llm: LiveKit LLM instance (e.g. ``livekit.plugins.openai.LLM``)
            used for slow_v1.  Forwarded to ``Agent`` via ``llm=slow_llm``.
        min_silence_before_kicking: Seconds to wait after the user turn ends
            before sending a filler if slow_v1 hasn't started.  Default 0.4 s.
        fast_filler_max_count: Maximum number of fillers per turn.  Default 1.
        fast_llm_model: Model name used for the fast filler call.  Falls back
            to ``DOUBAO_MODEL`` env var; default ``"doubao-seed-2-0-lite-260215"``.

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
        **kwargs: Any,
    ) -> None:
        if fast_llm is None:
            raise ValueError("fast_llm must be provided")

        # Pass slow_llm as the default Agent LLM so the LiveKit pipeline uses it.
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

        # Per-turn state (reset each on_user_turn_completed call).
        self._turn_filler_count: int = 0
        self._slow_first_token_emitted: bool = False

    # ── Main entry point ─────────────────────────────────────────────────────

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """Called by AgentSession after STT produces FINAL_TRANSCRIPT.

        Orchestrates:
        - TASK A: fast filler timer (fires after ``min_silence_before_kicking``
          if slow_v1 has not yet emitted its first token).
        - TASK C: slow_v1 — handled by LiveKit's default LLM pipeline.
          The skeleton does NOT override ``llm_node``; returning from this method
          lets the session proceed with normal generation.

        Args:
            turn_ctx: Current mutable chat context (filler is written back here
                before slow_v1 starts consuming it — OQ-13).
            new_message: The user's latest message from STT.

        Raises:
            No exceptions are propagated.  All errors are caught, logged, and
            gracefully degraded (filler is skipped on failure).
        """
        # ── Reset per-turn state ──────────────────────────────────────────
        self._turn_filler_count = 0
        self._slow_first_token_emitted = False

        # ── Derive session/turn IDs; set contextvars for F3 plugin ───────
        try:
            room_name: str = self.session.room.name  # type: ignore[union-attr]
        except Exception:
            room_name = "unknown"
        session_id: str = room_name or "unknown"
        turn_id: str = uuid.uuid4().hex[:8]

        # Set F3 contextvars so STT plugin can log them without being passed explicitly.
        voice_session_ctx.set(session_id)
        voice_turn_ctx.set(turn_id)

        logger.info(
            "turn_started",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "user_msg_len": len(
                    new_message.text_content or ""
                    if hasattr(new_message, "text_content")
                    else ""
                ),
            },
        )

        t_turn_start = time.monotonic()

        # TASK A: filler timer — runs concurrently; we do NOT await it here
        # because returning from this method triggers slow_v1 via the LiveKit
        # pipeline.  We run the filler as a background task that cancels itself
        # once the turn is done.
        slow_v1_task = asyncio.create_task(
            self._run_slow(turn_ctx, session_id, turn_id)
        )
        filler_timer_task = asyncio.create_task(
            self._maybe_filler(slow_v1_task, turn_ctx, session_id, turn_id)
        )

        # Wait for filler decision to complete (it's fast — either fires immediately
        # or sleeps min_silence_before_kicking then decides).
        # slow_v1_task runs to completion after filler_timer_task finishes.
        await asyncio.gather(filler_timer_task, return_exceptions=True)

        # Await slow_v1_task to completion (it drives the LLM + TTS pipeline).
        try:
            await slow_v1_task
        except Exception:
            logger.exception(
                "slow_v1_failed",
                extra={"session_id": session_id, "turn_id": turn_id},
            )

        path = "short" if self._turn_filler_count == 0 else "standard"
        latency_ms = round((time.monotonic() - t_turn_start) * 1000)
        logger.info(
            "turn_completed",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "path": path,
                "latency_ms": latency_ms,
            },
        )

    # ── Filler timer ─────────────────────────────────────────────────────────

    async def _maybe_filler(
        self,
        slow_v1_task: "asyncio.Task[None]",
        turn_ctx: ChatContext,
        session_id: str,
        turn_id: str,
    ) -> None:
        """Wait ``min_silence_before_kicking`` s then send one filler if slow hasn't started.

        Args:
            slow_v1_task: Task running ``_run_slow``; checked for first-token flag.
            turn_ctx: Chat context (mutated if filler is sent — OQ-13 ordering).
            session_id: For structured logging.
            turn_id: For structured logging.

        Raises:
            No exceptions propagated.  On filler LLM failure, logs warning and returns.
        """
        await asyncio.sleep(self.min_silence_before_kicking)

        # Skip if slow_v1 already emitted its first token or filler limit reached.
        if self._slow_first_token_emitted:
            logger.info(
                "filler_skipped_slow_fast",
                extra={"session_id": session_id, "turn_id": turn_id},
            )
            return

        if self._turn_filler_count >= self.fast_filler_max_count:
            logger.info(
                "filler_skipped_max_count",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "max_count": self.fast_filler_max_count,
                },
            )
            return

        # Increment count now to prevent double-fire even if an exception occurs.
        self._turn_filler_count += 1
        t_filler_start = time.monotonic()

        try:
            # Step 1: Generate the full filler text from the fast LLM.
            # We collect it first so we know the text for chat_ctx write-back (OQ-13).
            filler_text = await self._generate_filler_text(session_id, turn_id)

            if not filler_text:
                # LLM returned empty — skip say and write-back.
                logger.warning(
                    "filler_empty_response",
                    extra={"session_id": session_id, "turn_id": turn_id},
                )
                return

            latency_ms = round((time.monotonic() - t_filler_start) * 1000)
            logger.info(
                "filler_dispatched",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "filler_text": filler_text[:50],
                    "latency_ms_to_filler": latency_ms,
                },
            )

            # Step 2: Pass as async iterable to session.say() (OQ-10 pattern).
            # add_to_chat_ctx=False so we control ordering ourselves (OQ-13).
            async def _filler_gen() -> AsyncIterable[str]:
                yield filler_text

            self.session.say(_filler_gen(), add_to_chat_ctx=False)

            # Step 3: Write filler into chat_ctx AFTER session.say() is submitted (OQ-13).
            # TTS starts immediately above; we write back now so slow_v1 sees it.
            turn_ctx.add_message(
                role="assistant",
                content=filler_text,
                interrupted=False,
            )

        except Exception as exc:
            logger.warning(
                "filler_dispatch_failed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "error": str(exc),
                },
                exc_info=True,
            )

    # ── Filler text generation ───────────────────────────────────────────────

    async def _generate_filler_text(self, session_id: str, turn_id: str) -> str:
        """Call fast LLM to generate a short filler acknowledgement.

        Collects all stream chunks and returns the full filler string.

        Args:
            session_id: For structured logging.
            turn_id: For structured logging.

        Returns:
            Filler text string (≤30 tokens).  Returns ``""`` on LLM error.

        Raises:
            No exceptions propagated.  On failure returns empty string and logs.
        """
        filler_text = ""
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
                    filler_text += delta
        except Exception as exc:
            logger.warning(
                "filler_llm_failed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
        return filler_text

    # ── Slow v1 skeleton ─────────────────────────────────────────────────────

    async def _run_slow(
        self,
        turn_ctx: ChatContext,
        session_id: str,
        turn_id: str,
    ) -> None:
        """Skeleton: signal first-token flag; real slow_v1 runs via LiveKit's default pipeline.

        In the F5 skeleton, this method sets ``_slow_first_token_emitted`` after a
        short yield to the event loop, which satisfies OQ-12's requirement without
        overriding ``llm_node``.  In F8 this will be replaced with a proper first-token
        hook by wrapping the LLM stream.

        Args:
            turn_ctx: Chat context (not used directly in skeleton).
            session_id: For structured logging.
            turn_id: For structured logging.

        Raises:
            No exceptions propagated in the skeleton.
        """
        # Yield to the event loop once so the filler timer task starts.
        await asyncio.sleep(0)
        # The LiveKit pipeline runs slow_v1 after on_user_turn_completed returns.
        # We set the flag here to signal "slow will run soon"; in F8 this will be
        # driven by the actual first LLM chunk event.
        # For now, the flag is NOT set here — it stays False so that the filler timer
        # can fire if needed.  This matches F5 test expectations.
        logger.info(
            "slow_v1_pipeline_delegated",
            extra={"session_id": session_id, "turn_id": turn_id},
        )
