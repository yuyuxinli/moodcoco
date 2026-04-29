"""FastSlowAgent — real fast/slow voice orchestration on top of LiveKit.

The production path uses ``session.say()`` for every spoken segment so audio
always flows through the real LiveKit TTS pipeline and back into the room.
Unit tests can still inject ``slow_llm_chat_fn`` to keep the fast, hermetic
behaviour from earlier F5/F8 work.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
import uuid
from collections.abc import AsyncIterable, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from livekit.agents import Agent, StopResponse
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
    "你是一个中文情绪陪伴助手。"
    "请只输出一句 5-10 个字的短回应，表示你听到了用户，"
    "不要分析，不要建议，不要提问，不要解释。"
)

MergedDecisionFn = Callable[[str, list[dict]], Awaitable[MergedDecisionResult]]
ContinueDeciderFn = Callable[[str, list[dict]], Awaitable[ContinueDecision]]
SlowLLMChatFn = Callable[[list[dict]], Awaitable[str]]

_PATH_LABELS = {
    "short": "短",
    "standard": "标准",
    "long": "长",
}


@dataclass(frozen=True)
class StreamedReply:
    text: str
    first_token_ms: int | None
    latency_ms: int


class LLMTimeoutError(Exception):
    """LLM call exceeded the configured hard timeout."""


class FastSlowAgent(Agent):
    """LiveKit Agent implementing fast filler + slow_v1 + optional slow_v2."""

    def __init__(
        self,
        *,
        instructions: str,
        fast_llm: Any,
        slow_llm: Any | None = None,
        min_silence_before_kicking: float = MIN_SILENCE_BEFORE_KICKING_MS / 1000,
        fast_filler_max_count: int = FAST_FILLER_MAX_COUNT,
        fast_llm_model: str | None = None,
        slow_llm_model: str | None = None,
        merged_decision_fn: MergedDecisionFn | None = None,
        continue_decider_fn: ContinueDeciderFn | None = None,
        skill_router: SJTUSkillRouter | None = None,
        slow_llm_chat_fn: SlowLLMChatFn | None = None,
        slow_client: Any | None = None,
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
        self._slow_client = slow_client
        self._fast_llm_model: str = fast_llm_model or os.getenv(
            "DOUBAO_MODEL", "doubao-seed-2-0-lite-260215"
        )
        self._slow_llm_model: str = slow_llm_model or os.getenv(
            "OPENAI_MODEL", "minimax/minimax-m2.7"
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
        self._slow_v1_text: str = ""
        self._session_hooks_registered = False
        self._speech_meta: dict[str, dict[str, Any]] = {}

    def _get_skill_router(self) -> SJTUSkillRouter:
        if self._skill_router is None:
            self._skill_router = SJTUSkillRouter()
        return self._skill_router

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """Run the full fast/slow pipeline and suppress LiveKit default reply."""
        self._turn_filler_count = 0
        self._slow_first_token_emitted = False
        self._slow_v1_text = ""
        self._ensure_session_hooks_registered()

        room_name = self._resolve_room_name()
        session_id = (
            voice_session_ctx.get()
            or room_name
            or "unknown"
        )
        turn_id = voice_turn_ctx.get() or uuid.uuid4().hex[:8]
        voice_session_ctx.set(session_id)
        voice_turn_ctx.set(turn_id)

        user_text = getattr(new_message, "text_content", "") or ""
        logger.info(
            "turn_started",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "turn",
                "user_msg_len": len(user_text),
            },
        )

        turn_started_at = time.monotonic()
        recent_ctx = self._snapshot_recent_ctx(turn_ctx)

        logger.info(
            "merged_decision_dispatched",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "decision",
            },
        )
        decision_task: asyncio.Task[MergedDecisionResult] = asyncio.create_task(
            self._run_merged_decision_safe(user_text, recent_ctx, session_id, turn_id)
        )
        slow_v1_task = asyncio.create_task(
            self._run_slow(turn_ctx, session_id, turn_id)
        )
        filler_timer_task = asyncio.create_task(
            self._maybe_filler(turn_ctx, session_id, turn_id)
        )

        await filler_timer_task
        await slow_v1_task

        path = await self._run_dp_continue_and_v2(
            turn_ctx, recent_ctx, decision_task, session_id, turn_id
        )

        latency_ms = round((time.monotonic() - turn_started_at) * 1000)
        logger.info(
            "turn_complete",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "turn",
                "path": path,
                "path_label": _PATH_LABELS[path],
                "latency_ms": latency_ms,
            },
        )

        if self._slow_client is not None and self._slow_llm_chat_fn is None:
            raise StopResponse()

    @staticmethod
    def _snapshot_recent_ctx(turn_ctx: ChatContext) -> list[dict]:
        try:
            messages = FastSlowAgent._chat_messages(turn_ctx)
            out: list[dict] = []
            for message in messages[-6:]:
                if isinstance(message, dict):
                    out.append(
                        {
                            "role": str(message.get("role", "")),
                            "content": str(message.get("content", "")),
                        }
                    )
                    continue

                role = getattr(message, "role", "")
                content = getattr(message, "text_content", "") or getattr(
                    message, "content", ""
                )
                if isinstance(content, list):
                    content = "".join(str(item) for item in content)
                out.append({"role": str(role), "content": str(content)})
            return out
        except Exception:
            logger.warning("snapshot_recent_ctx_failed", exc_info=True)
            return []

    async def _run_merged_decision_safe(
        self,
        user_text: str,
        recent_ctx: list[dict],
        session_id: str,
        turn_id: str,
    ) -> MergedDecisionResult:
        try:
            result = await self._merged_decision_fn(user_text, recent_ctx)
        except Exception as exc:
            logger.warning(
                "merged_decision_unexpected_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "decision",
                    "error": str(exc),
                    "error_class": exc.__class__.__name__,
                },
                exc_info=True,
            )
            return MergedDecisionResult()

        decision_json = result.raw_json or (
            '{"search":{"yes":%s,"kw":"%s"},"skill":%s}'
            % (
                "true" if result.search_yes else "false",
                result.search_kw,
                f'"{result.skill}"' if result.skill else "null",
            )
        )
        logger.info(
            "merged_decision_result",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "decision",
                "decision_json": decision_json,
                "search_yes": result.search_yes,
                "search_kw": result.search_kw,
                "skill": result.skill,
                "latency_ms": round(result.latency_ms),
            },
        )
        logger.info(
            "merged_decision_done",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "decision",
                "search_yes": result.search_yes,
                "search_kw": result.search_kw,
                "skill": result.skill,
                "latency_ms": round(result.latency_ms),
            },
        )
        return result

    async def _maybe_filler(
        self, turn_ctx: ChatContext, session_id: str, turn_id: str
    ) -> None:
        await asyncio.sleep(self.min_silence_before_kicking)

        if self._slow_first_token_emitted:
            logger.info(
                "filler_skipped_slow_fast",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "filler",
                },
            )
            return

        if self._turn_filler_count >= self.fast_filler_max_count:
            logger.info(
                "filler_skipped_max_count",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "filler",
                    "max_count": self.fast_filler_max_count,
                },
            )
            return

        self._turn_filler_count += 1
        started_at = time.monotonic()
        filler_text_fut: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _fast_llm_reply() -> AsyncIterable[str]:
            collected: list[str] = []
            try:
                stream = await self._fast_llm.chat.completions.create(
                    model=self._fast_llm_model,
                    messages=[
                        {"role": "system", "content": FILLER_PROMPT},
                        {
                            "role": "user",
                            "content": self._latest_user_message(turn_ctx),
                        },
                    ],
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
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": "filler",
                        "error": str(exc),
                        "error_class": exc.__class__.__name__,
                    },
                    exc_info=True,
                )
                if not filler_text_fut.done():
                    filler_text_fut.set_exception(exc)

        try:
            self.session.say(_fast_llm_reply(), add_to_chat_ctx=False)
            filler_text = await filler_text_fut
        except Exception:
            return

        if not filler_text:
            logger.warning(
                "filler_empty_response",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "filler",
                },
            )
            return

        latency_ms = round((time.monotonic() - started_at) * 1000)
        logger.info(
            "fast_filler_sent",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "filler",
                "filler_text": filler_text,
                "latency_ms": latency_ms,
            },
        )
        self._write_back_assistant_message(turn_ctx, filler_text)

    async def _run_slow(
        self, turn_ctx: ChatContext, session_id: str, turn_id: str
    ) -> None:
        if self._slow_llm_chat_fn is not None:
            messages = self._build_messages(turn_ctx, system_prompt=self._instructions)
            started_at = time.monotonic()
            self._slow_v1_text = await self._slow_llm_chat_fn(messages)
            latency_ms = round((time.monotonic() - started_at) * 1000)
            logger.info(
                "slow_v1_completed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "slow_v1",
                    "text_len": len(self._slow_v1_text or ""),
                    "latency_ms": latency_ms,
                },
            )
            return

        if self._slow_client is None:
            logger.info(
                "slow_v1_pipeline_delegated",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "slow_v1",
                },
            )
            return

        messages = self._build_messages(turn_ctx, system_prompt=self._instructions)
        reply = await self._stream_model_reply(
            messages=messages,
            model=self._slow_llm_model,
            phase="slow_v1",
            turn_ctx=turn_ctx,
            session_id=session_id,
            turn_id=turn_id,
        )
        self._slow_v1_text = reply.text
        logger.info(
            "slow_v1_completed",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "slow_v1",
                "first_token_ms": reply.first_token_ms,
                "latency_ms": reply.latency_ms,
                "final_text": reply.text,
                "text_len": len(reply.text),
            },
        )

    async def _run_dp_continue_and_v2(
        self,
        turn_ctx: ChatContext,
        recent_ctx: list[dict],
        decision_task: "asyncio.Task[MergedDecisionResult]",
        session_id: str,
        turn_id: str,
    ) -> str:
        try:
            decision = await self._continue_decider_fn(self._slow_v1_text, recent_ctx)
        except Exception as exc:
            logger.warning(
                "dp_continue_unexpected_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "continue_decider",
                    "error": str(exc),
                    "error_class": exc.__class__.__name__,
                },
                exc_info=True,
            )
            decision = ContinueDecision(yes=False, reason="unexpected_error")

        logger.info(
            "continue_decider_result",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "continue_decider",
                "continue_": decision.yes,
                "reason": decision.reason,
                "latency_ms": round(decision.latency_ms),
            },
        )

        if not decision.yes:
            logger.info(
                "dp_continue_no",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "continue_decider",
                    "reason": decision.reason,
                    "latency_ms": round(decision.latency_ms),
                },
            )
            if not decision_task.done():
                try:
                    await decision_task
                except Exception as exc:
                    logger.warning(
                        "merged_decision_drain_failed",
                        extra={
                            "session_id": session_id,
                            "turn_id": turn_id,
                            "phase": "decision",
                            "error": str(exc),
                            "error_class": exc.__class__.__name__,
                        },
                        exc_info=True,
                    )
            return "short" if self._turn_filler_count == 0 else "standard"

        logger.info(
            "dp_continue_yes",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "continue_decider",
                "reason": decision.reason,
                "latency_ms": round(decision.latency_ms),
            },
        )

        try:
            merged_result = await decision_task
        except Exception as exc:
            logger.warning(
                "merged_decision_await_failed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "decision",
                    "error": str(exc),
                    "error_class": exc.__class__.__name__,
                },
                exc_info=True,
            )
            merged_result = MergedDecisionResult()

        skill_content = self._load_skill_content_safe(
            merged_result.skill, session_id, turn_id
        )
        retrieval_query = merged_result.search_kw if merged_result.search_yes else ""
        retrieved = await self._run_retrieval(retrieval_query, session_id, turn_id)
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
        if not skill_name:
            return ""
        try:
            router = self._get_skill_router()
            content = router.load_skill_content(skill_name)
            logger.info(
                "skill_router_content_loaded",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "skill_router",
                    "skill_name": skill_name,
                    "content_len": len(content),
                },
            )
            return content
        except SkillNotFoundError:
            return ""
        except Exception as exc:
            logger.warning(
                "skill_router_unexpected_error",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "skill_router",
                    "skill_name": skill_name,
                    "error": str(exc),
                    "error_class": exc.__class__.__name__,
                },
                exc_info=True,
            )
            return ""

    async def _run_retrieval(
        self, query: str, session_id: str, turn_id: str
    ) -> str:
        logger.info(
            "retrieval_stub_result",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "retrieval",
                "query": query,
                "hit_count": 0,
                "latency_ms": 0,
            },
        )
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
        system_prompt = self._compose_slow_v2_system_prompt(skill_content, retrieved)
        logger.info(
            "slow_v2_streaming_start",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "slow_v2",
                "skill_name": skill_name,
                "has_skill_content": bool(skill_content),
                "has_retrieved_context": bool(retrieved),
            },
        )

        if self._slow_llm_chat_fn is not None:
            messages = self._build_messages(turn_ctx, system_prompt=system_prompt)
            started_at = time.monotonic()
            text = await self._slow_llm_chat_fn(messages)
            self._write_back_assistant_message(turn_ctx, text)
            latency_ms = round((time.monotonic() - started_at) * 1000)
            logger.info(
                "slow_v2_completed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "slow_v2",
                    "final_text": text,
                    "text_len": len(text or ""),
                    "latency_ms": latency_ms,
                },
            )
            return

        if self._slow_client is None:
            logger.info(
                "slow_v2_completed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "slow_v2",
                    "final_text": "",
                    "text_len": 0,
                    "latency_ms": 0,
                    "delegated": True,
                },
            )
            return

        messages = self._build_messages(turn_ctx, system_prompt=system_prompt)
        reply = await self._stream_model_reply(
            messages=messages,
            model=self._slow_llm_model,
            phase="slow_v2",
            turn_ctx=turn_ctx,
            session_id=session_id,
            turn_id=turn_id,
        )
        logger.info(
            "slow_v2_completed",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "slow_v2",
                "first_token_ms": reply.first_token_ms,
                "latency_ms": reply.latency_ms,
                "final_text": reply.text,
                "text_len": len(reply.text),
            },
        )

    async def _stream_model_reply(
        self,
        *,
        messages: list[dict],
        model: str,
        phase: str,
        turn_ctx: ChatContext,
        session_id: str,
        turn_id: str,
    ) -> StreamedReply:
        logger.info(
            f"{phase}_streaming_start",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": phase,
                "model": model,
            },
        )
        started_at = time.monotonic()
        first_token_ms: int | None = None
        reply_text_fut: asyncio.Future[str] = asyncio.get_event_loop().create_future()

        async def _reply_stream() -> AsyncIterable[str]:
            nonlocal first_token_ms
            collected: list[str] = []
            try:
                stream = await self._slow_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                )
                async for chunk in stream:
                    d = chunk.choices[0].delta
                    # Reasoning models (e.g. minimax-m2.7) emit text in
                    # reasoning_content during the thinking phase, then
                    # often emit the final answer in content. Use whichever
                    # is non-empty so we never drop tokens.
                    delta = (getattr(d, "content", None) or
                             getattr(d, "reasoning_content", None) or "")
                    if not delta:
                        continue
                    collected.append(delta)
                    if first_token_ms is None:
                        first_token_ms = round((time.monotonic() - started_at) * 1000)
                        if phase == "slow_v1":
                            self._slow_first_token_emitted = True
                        logger.info(
                            f"{phase}_first_token",
                            extra={
                                "session_id": session_id,
                                "turn_id": turn_id,
                                "phase": phase,
                                "latency_ms": first_token_ms,
                            },
                        )
                    yield delta
                if not reply_text_fut.done():
                    reply_text_fut.set_result("".join(collected).strip())
            except Exception as exc:
                if not reply_text_fut.done():
                    reply_text_fut.set_exception(exc)
                logger.error(
                    f"{phase}_streaming_failed",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": phase,
                        "error": str(exc),
                        "error_class": exc.__class__.__name__,
                    },
                    exc_info=True,
                )
                raise

        handle = self.session.say(_reply_stream(), add_to_chat_ctx=False)
        speech_id = getattr(handle, "id", "")
        if speech_id:
            self._speech_meta[speech_id] = {
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": phase,
                "text_len": 0,
            }

        text = await reply_text_fut
        latency_ms = round((time.monotonic() - started_at) * 1000)
        self._write_back_assistant_message(turn_ctx, text)

        if speech_id:
            self._speech_meta[speech_id]["text_len"] = len(text)

        return StreamedReply(text=text, first_token_ms=first_token_ms, latency_ms=latency_ms)

    def _compose_slow_v2_system_prompt(
        self, skill_content: str, retrieved: str
    ) -> str:
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
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        try:
            history = FastSlowAgent._chat_messages(turn_ctx)
            for message in history:
                if isinstance(message, dict):
                    role = str(message.get("role", "user"))
                    content = str(message.get("content", ""))
                else:
                    role = str(getattr(message, "role", "user"))
                    raw = getattr(message, "text_content", "") or getattr(
                        message, "content", ""
                    )
                    content = (
                        "".join(str(item) for item in raw)
                        if isinstance(raw, list)
                        else str(raw)
                    )
                if content:
                    messages.append({"role": role, "content": content})
        except Exception:
            logger.warning("build_messages_failed", exc_info=True)
        return messages

    def _write_back_assistant_message(self, turn_ctx: ChatContext, text: str) -> None:
        if not text:
            return
        turn_ctx.add_message(role="assistant", content=text, interrupted=False)
        self._chat_ctx.add_message(role="assistant", content=text, interrupted=False)

    @staticmethod
    def _latest_user_message(turn_ctx: ChatContext) -> str:
        messages = FastSlowAgent._chat_messages(turn_ctx)
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                return str(message.get("content", ""))
            role = getattr(message, "role", "")
            if role == "user":
                return str(
                    getattr(message, "text_content", "") or getattr(message, "content", "")
                )
        return ""

    @staticmethod
    def _chat_messages(turn_ctx: ChatContext) -> list[Any]:
        messages_attr = getattr(turn_ctx, "messages", None)
        if callable(messages_attr):
            messages = messages_attr()
        else:
            messages = messages_attr if messages_attr is not None else []
        return list(messages) if messages else []

    def _resolve_room_name(self) -> str:
        candidates = [
            getattr(getattr(getattr(self.session, "room_io", None), "room", None), "name", None),
            getattr(getattr(self.session, "room", None), "name", None),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate:
                return candidate
        return "unknown"

    def _ensure_session_hooks_registered(self) -> None:
        if self._session_hooks_registered:
            return

        session = getattr(self, "session", None)
        on = getattr(session, "on", None)
        if not callable(on):
            return

        def _on_metrics(event: Any) -> None:
            metrics = getattr(event, "metrics", None)
            if getattr(metrics, "type", None) != "tts_metrics":
                return
            speech_id = getattr(metrics, "speech_id", None)
            if not speech_id:
                return
            meta = self._speech_meta.get(speech_id)
            if not meta:
                return
            logger.info(
                "minimax_tts_publish",
                extra={
                    "session_id": meta["session_id"],
                    "turn_id": meta["turn_id"],
                    "phase": meta["phase"],
                    "text_len": meta["text_len"],
                    "audio_duration_ms": round(getattr(metrics, "audio_duration", 0) * 1000),
                    "latency_ms": round(getattr(metrics, "duration", 0) * 1000),
                },
            )

        on("metrics_collected", _on_metrics)
        self._session_hooks_registered = True

    @staticmethod
    async def _wait_for_handle_playout(handle: Any) -> None:
        waiter = getattr(handle, "wait_for_playout", None)
        if waiter is None or not callable(waiter):
            return
        if inspect.iscoroutinefunction(waiter):
            await waiter()
            return
        maybe_coro = waiter()
        if inspect.isawaitable(maybe_coro):
            await maybe_coro
