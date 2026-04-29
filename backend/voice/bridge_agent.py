"""LiveKit voice bridge backed by pydantic-ai Fast and Slow agents."""
from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import AsyncIterable
from typing import Any

from livekit.agents import Agent, StopResponse
from livekit.agents.llm import ChatContext, ChatMessage

from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx

logger = logging.getLogger("voice.bridge_agent")


class VoiceBridgeAgent(Agent):
    """LiveKit Agent that bridges each user turn to pydantic-ai Fast and Slow."""

    def __init__(self, *, instructions: str, **kwargs: Any) -> None:
        super().__init__(instructions=instructions, **kwargs)
        self._instructions: str = instructions
        self._session_hooks_registered = False
        self._speech_meta: dict[str, dict[str, Any]] = {}
        self._fast_history: list[Any] = []
        self._slow_history: list[Any] = []
        self._slow_state: dict[str, Any] = {
            "reasoning_trail": [],
            "search_cache": {},
            "pending_actions": [],
            "carryover_inject": [],
            "carryover_skills": [],
            "carryover_retrieval": "",
        }

    async def stt_node(
        self,
        audio: AsyncIterable[Any],
        model_settings: Any,
    ):
        """Count audio frames entering the default STT pipeline."""
        session_id = voice_session_ctx.get() or "unknown"
        frame_count = 0
        sample_total = 0
        last_log_at = time.monotonic()

        async def _counting_audio():
            nonlocal frame_count, sample_total, last_log_at
            async for frame in audio:
                frame_count += 1
                samples_per_channel = getattr(frame, "samples_per_channel", 0) or 0
                sample_rate = getattr(frame, "sample_rate", 0) or 0
                sample_total += samples_per_channel
                now = time.monotonic()
                if frame_count == 1 or (now - last_log_at) >= 1.0:
                    logger.info(
                        "[STAGE_A] stt_node_audio_frames",
                        extra={
                            "session_id": session_id,
                            "turn_id": voice_turn_ctx.get() or "pre-turn",
                            "phase": "stt_node",
                            "frame_count": frame_count,
                            "sample_total": sample_total,
                            "approx_seconds": round(
                                sample_total / max(sample_rate, 1), 2
                            ),
                        },
                    )
                    last_log_at = now
                yield frame

        async for ev in Agent.default.stt_node(self, _counting_audio(), model_settings):
            yield ev

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        """Bridge LiveKit user turns into pydantic-ai Fast and Slow agents."""
        from backend.fast import FastThinkDeps, fast_agent
        from backend.llm_provider import PROJECT_ROOT
        from backend.slow import SlowThinkDeps, slow_agent

        started_at = time.monotonic()
        user_text = (getattr(new_message, "text_content", "") or "").strip()
        logger.info(
            "[STAGE_E] HOOK on_user_turn_completed entered",
            extra={
                "session_id": voice_session_ctx.get() or "unknown",
                "turn_id": voice_turn_ctx.get() or "pre-turn",
                "phase": "turn",
                "user_text_preview": user_text[:40],
            },
        )
        if not user_text:
            return

        self._ensure_session_hooks_registered()

        room_name = self._resolve_room_name()
        session_id = voice_session_ctx.get() or room_name or "unknown"
        turn_id = uuid.uuid4().hex[:8]
        voice_session_ctx.set(session_id)
        voice_turn_ctx.set(turn_id)

        logger.info(
            "fast_agent_run_started",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "fast",
            },
        )
        logger.info(
            "slow_agent_run_started",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "phase": "slow",
            },
        )

        memory_file = PROJECT_ROOT / "backend" / "state" / "MEMORY.md"
        guidance_file = PROJECT_ROOT / "backend" / "state" / "SLOW_GUIDANCE.md"
        memory_text = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
        slow_guidance = (
            guidance_file.read_text(encoding="utf-8").strip()
            if guidance_file.exists()
            else ""
        )

        fast_deps = FastThinkDeps(
            session_id=session_id,
            memory_text=memory_text,
            slow_guidance=slow_guidance,
            voice_session=self.session,
            skill_bundle=list(self._slow_state["carryover_skills"]),
            retrieval_block=str(self._slow_state["carryover_retrieval"]),
            dynamic_inject=list(self._slow_state["carryover_inject"]),
        )
        if (
            fast_deps.dynamic_inject
            or fast_deps.skill_bundle
            or fast_deps.retrieval_block.strip()
        ):
            logger.info(
                "[STAGE_E] cross_turn_carryover",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "fast",
                    "inject_count": len(fast_deps.dynamic_inject),
                    "skills_count": len(fast_deps.skill_bundle),
                    "retrieval_len": len(fast_deps.retrieval_block),
                },
            )
        slow_deps = SlowThinkDeps(
            session_id=session_id,
            user_message=user_text,
            fast_reply_text="",
            fast_deps=fast_deps,
            reasoning_trail=self._slow_state["reasoning_trail"],
            search_cache=self._slow_state["search_cache"],
            pending_actions=self._slow_state["pending_actions"],
            carryover_inject=self._slow_state["carryover_inject"],
            carryover_skills=self._slow_state["carryover_skills"],
            carryover_retrieval=str(self._slow_state["carryover_retrieval"]),
        )

        fast_task = asyncio.create_task(
            fast_agent.run(user_text, deps=fast_deps, message_history=self._fast_history)
        )
        slow_task = asyncio.create_task(
            slow_agent.run(user_text, deps=slow_deps, message_history=self._slow_history)
        )

        def _on_slow_done(task: asyncio.Task[Any]) -> None:
            latency_ms = round((time.monotonic() - started_at) * 1000)
            try:
                result = task.result()
            except asyncio.CancelledError:
                logger.info(
                    "slow_agent_run_cancelled",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": "slow",
                        "latency_ms": latency_ms,
                    },
                )
                return
            except Exception:
                logger.error(
                    "slow_agent_run_failed",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": "slow",
                        "latency_ms": latency_ms,
                    },
                    exc_info=True,
                )
                return

            self._slow_history = result.all_messages()
            slow_called_tool = bool(slow_deps.tool_call_history)
            if (
                slow_deps.mutation_count_this_iter == 0
                and not slow_called_tool
                and slow_deps.fast_deps is not None
            ):
                fallback_hint = "Slow 本轮未发现需要额外展开的策略；Fast 继续轻量承接用户情绪。"
                slow_deps.fast_deps.dynamic_inject.append(fallback_hint)
                slow_deps.carryover_inject.append(fallback_hint)
                del slow_deps.carryover_inject[:-3]
                slow_deps.reasoning_trail.append("bridge_default_inject")
                slow_deps.mutation_count_this_iter += 1
                logger.info(
                    "slow_tool_call",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": "slow",
                        "tool": "slow_inject_to_fast",
                        "text_len": len(fallback_hint),
                        "latency_ms": latency_ms,
                        "mutations_made": slow_deps.mutation_count_this_iter,
                        "fallback": "bridge_no_mutation",
                    },
                )
            self._slow_state["reasoning_trail"] = slow_deps.reasoning_trail
            self._slow_state["search_cache"] = slow_deps.search_cache
            self._slow_state["pending_actions"] = slow_deps.pending_actions
            if slow_deps.fast_deps is not None:
                for injected in slow_deps.fast_deps.dynamic_inject:
                    if injected not in slow_deps.carryover_inject:
                        slow_deps.carryover_inject.append(injected)
                for skill_text in slow_deps.fast_deps.skill_bundle:
                    if skill_text not in slow_deps.carryover_skills:
                        slow_deps.carryover_skills.append(skill_text)
                slow_deps.carryover_retrieval = slow_deps.fast_deps.retrieval_block
            self._slow_state["carryover_inject"] = slow_deps.carryover_inject[-3:]
            self._slow_state["carryover_skills"] = slow_deps.carryover_skills
            self._slow_state["carryover_retrieval"] = slow_deps.carryover_retrieval
            logger.info(
                "slow_agent_run_completed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "slow",
                    "iter_used": len(self._slow_history),
                    "mutations_made": slow_deps.mutation_count_this_iter,
                    "latency_ms": latency_ms,
                },
            )

        slow_task.add_done_callback(_on_slow_done)

        try:
            fast_result = await fast_task
        except Exception:
            latency_ms = round((time.monotonic() - started_at) * 1000)
            logger.error(
                "fast_agent_run_failed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "fast",
                    "latency_ms": latency_ms,
                },
                exc_info=True,
            )
            try:
                fallback = self.session.say("嗯，我在这儿听着，慢慢说。", add_to_chat_ctx=True)
                if inspect.isawaitable(fallback):
                    await fallback
            except Exception:
                logger.info(
                    "fast_agent_fallback_say_failed",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": "fast",
                    },
                    exc_info=True,
                )
        else:
            self._fast_history = fast_result.all_messages()
            latency_ms = round((time.monotonic() - started_at) * 1000)
            logger.info(
                "fast_agent_run_completed",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "phase": "fast",
                    "iter_used": len(self._fast_history),
                    "latency_ms": latency_ms,
                },
            )

        raise StopResponse()

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


FastSlowAgent = VoiceBridgeAgent

__all__ = [
    "FastSlowAgent",
    "VoiceBridgeAgent",
    "voice_session_ctx",
    "voice_turn_ctx",
]
