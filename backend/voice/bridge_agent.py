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
from pydantic_ai.usage import UsageLimitExceeded, UsageLimits

from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx

logger = logging.getLogger("voice.bridge_agent")

VOICE_SLOW_USAGE_LIMITS = UsageLimits(request_limit=4, tool_calls_limit=4)


def _extract_speaker_text(collected_tool_calls: list[dict[str, Any]]) -> str:
    """Extract spoken text from the last ai_message tool call."""
    for call in reversed(collected_tool_calls):
        if call.get("name") == "ai_message":
            messages = (call.get("args") or {}).get("messages", [])
            return "\n".join(str(m).strip() for m in messages if str(m).strip())
    return ""


def _build_prewarmed_contexts(next_likely: list[str]) -> dict[str, str]:
    """Load skill content for predicted next-turn contexts."""
    if not next_likely:
        return {}
    from backend.slow import SKILLS_DIR

    result: dict[str, str] = {}
    for name in next_likely:
        skill_path = SKILLS_DIR / name / "SKILL.md"
        if skill_path.exists():
            result[name] = skill_path.read_text(encoding="utf-8")
    return result


def _extract_skill_names(reasoning_trail: list[str]) -> list[str]:
    """Extract skill names from reasoning_trail entries like 'skill:untangle'."""
    names = []
    for entry in reasoning_trail:
        if entry.startswith("skill:"):
            names.append(entry[6:])
    return names


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
            "next_likely_contexts": [],
            "carryover_skill_names": [],
        }
        self._last_speaker_text: str = ""

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
            prewarmed_contexts=_build_prewarmed_contexts(
                self._slow_state["next_likely_contexts"]
            ),
            skill_names=list(self._slow_state["carryover_skill_names"]),
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
            speaker_output=self._last_speaker_text,
            reasoning_trail=self._slow_state["reasoning_trail"],
            search_cache=self._slow_state["search_cache"],
            pending_actions=self._slow_state["pending_actions"],
            carryover_inject=list(self._slow_state["carryover_inject"]),
            carryover_skills=list(self._slow_state["carryover_skills"]),
            carryover_retrieval=str(self._slow_state["carryover_retrieval"]),
        )

        fast_task = asyncio.create_task(
            fast_agent.run(user_text, deps=fast_deps, message_history=self._fast_history)
        )
        slow_task = asyncio.create_task(
            slow_agent.run(
                user_text,
                deps=slow_deps,
                message_history=self._slow_history,
                usage_limits=VOICE_SLOW_USAGE_LIMITS,
            )
        )

        def _persist_slow_state(result: Any | None) -> None:
            slow_called_tool = bool(slow_deps.tool_call_history)
            if slow_deps.mutation_count_this_iter == 0 and not slow_called_tool:
                from backend.slow import _append_lru
                fallback_hint = "Thinker 本轮未发现需要额外展开的策略；Speaker 继续轻量承接用户情绪。"
                _append_lru(slow_deps.carryover_inject, fallback_hint, limit=3)
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
                        "latency_ms": round((time.monotonic() - started_at) * 1000),
                        "mutations_made": slow_deps.mutation_count_this_iter,
                        "fallback": "bridge_no_mutation",
                    },
                )
            self._persist_slow_state_sync(slow_deps, result)

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
            except UsageLimitExceeded:
                _persist_slow_state(None)
                logger.warning(
                    "slow_agent_run_limited",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": "slow",
                        "latency_ms": latency_ms,
                        "request_limit": VOICE_SLOW_USAGE_LIMITS.request_limit,
                        "tool_calls_limit": VOICE_SLOW_USAGE_LIMITS.tool_calls_limit,
                        "mutations_made": slow_deps.mutation_count_this_iter,
                    },
                    exc_info=True,
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

            _persist_slow_state(result)
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
            already_spoke = any(
                call.get("name") == "ai_message"
                and (call.get("args") or {}).get("messages")
                for call in fast_deps.collected_tool_calls
            )
            if already_spoke:
                logger.info(
                    "fast_agent_run_completed",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "phase": "fast",
                        "iter_used": len(self._fast_history),
                        "latency_ms": latency_ms,
                        "completed_after_voice_ai_message": True,
                    },
                )
            else:
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

        self._last_speaker_text = _extract_speaker_text(
            fast_deps.collected_tool_calls
        )
        raise StopResponse()

    def _persist_slow_state_sync(
        self, slow_deps: Any, result: Any | None
    ) -> None:
        """Persist slow agent state for cross-turn carryover."""
        if result is not None:
            self._slow_history = result.all_messages()
        self._slow_state["reasoning_trail"] = slow_deps.reasoning_trail
        self._slow_state["search_cache"] = slow_deps.search_cache
        self._slow_state["pending_actions"] = slow_deps.pending_actions
        self._slow_state["carryover_inject"] = slow_deps.carryover_inject[-3:]
        self._slow_state["carryover_skills"] = slow_deps.carryover_skills[-2:]
        self._slow_state["carryover_retrieval"] = slow_deps.carryover_retrieval
        self._slow_state["next_likely_contexts"] = slow_deps.next_likely_contexts
        self._slow_state["carryover_skill_names"] = _extract_skill_names(
            slow_deps.reasoning_trail
        )

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
    "_build_prewarmed_contexts",
    "_extract_skill_names",
    "_extract_speaker_text",
    "voice_session_ctx",
    "voice_turn_ctx",
]
