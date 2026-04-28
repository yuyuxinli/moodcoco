"""FastSlowAgent — LiveKit Agent implementing fast-filler + slow_v1 pattern.

F5 skeleton: fast filler ×1 (fires after ``min_silence_before_kicking`` if
slow_v1 hasn't yet emitted its first token) + slow_v1 (LiveKit default LLM
pipeline).  Merged-decision, DP-continue, slow_v2 are out of scope.

The filler is streamed via the canonical ``asyncio.Future`` pattern from
``fast-preresponse.py`` (LiveKit voice-agent reference): the LLM stream is
piped chunk-by-chunk into ``session.say()`` so TTS starts speaking on the
first token (~150 ms TTFB), while a Future captures the complete text for
the chat-context write-back that follows.

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
from collections.abc import AsyncIterable
from typing import Any

from livekit.agents import Agent
from livekit.agents.llm import ChatContext, ChatMessage

from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx

logger = logging.getLogger("voice.fast_slow_agent")

MIN_SILENCE_BEFORE_KICKING_MS: int = int(os.getenv("FAST_SLOW_MIN_SILENCE_MS", "400"))
FAST_FILLER_MAX_COUNT: int = int(os.getenv("FAST_SLOW_FILLER_MAX_COUNT", "1"))

FILLER_PROMPT = (
    "Generate a 5–10 word empathetic acknowledgement in Chinese that shows you heard the user. "
    "Do NOT give advice or ask questions. Example: '嗯，听起来不太好受。' "
    "Output ONLY the filler sentence, no punctuation at the end."
)


class LLMTimeoutError(Exception):
    """LLM call exceeded the configured hard timeout."""


class FastSlowAgent(Agent):
    """LiveKit Agent implementing the fast-filler + slow_v1 pattern.

    Args:
        instructions: Base persona system prompt (forwarded to ``Agent``).
        fast_llm: openai.AsyncOpenAI-compatible client used for filler streaming.
        slow_llm: LiveKit LLM instance for slow_v1 (forwarded as ``llm=`` kwarg).
        min_silence_before_kicking: Seconds to wait before sending filler.
        fast_filler_max_count: Maximum fillers per turn (default 1).
        fast_llm_model: Filler model name; falls back to ``DOUBAO_MODEL`` env.

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

        self._turn_filler_count: int = 0
        self._slow_first_token_emitted: bool = False

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """Orchestrate fast-filler timer + slow_v1 (LiveKit default pipeline).

        All exceptions are caught + logged; no errors are propagated.
        """
        self._turn_filler_count = 0
        self._slow_first_token_emitted = False

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

        slow_v1_task = asyncio.create_task(self._run_slow(turn_ctx, session_id, turn_id))
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

        path = "short" if self._turn_filler_count == 0 else "standard"
        latency_ms = round((time.monotonic() - t_turn_start) * 1000)
        logger.info(
            "turn_completed",
            extra={"session_id": session_id, "turn_id": turn_id, "path": path, "latency_ms": latency_ms},
        )

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
        """Skeleton: real slow_v1 runs via LiveKit's default LLM pipeline.

        F8 will wrap the LLM stream to flip ``_slow_first_token_emitted`` on
        the first chunk.  In F5 the flag stays False so the filler timer runs.
        """
        await asyncio.sleep(0)
        logger.info(
            "slow_v1_pipeline_delegated",
            extra={"session_id": session_id, "turn_id": turn_id},
        )
