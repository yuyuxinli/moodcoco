"""Streaming voice bridge milestone."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from livekit.agents import Agent, StopResponse
from livekit.agents.llm import ChatContext, ChatMessage

from backend.llm_provider import PROJECT_ROOT
from backend.voice.plugins._context import (
    get_latest_voice_turn_id,
    set_latest_voice_turn_id,
    voice_session_ctx,
    voice_turn_ctx,
)
from backend.voice.streaming_events import VoiceStreamEvent

logger = logging.getLogger("voice.streaming_bridge_agent")

VoiceEventPublisher = Callable[[VoiceStreamEvent], Awaitable[None]]


class StreamingVoiceBridgeAgent(Agent):
    def __init__(
        self,
        *,
        instructions: str,
        responder: Any,
        streaming_tts_client: Any | None = None,
        audio_sink: Callable[[bytes], Awaitable[None]] | None = None,
        event_publisher: VoiceEventPublisher | None = None,
        tts_mode: str | None = None,
        voice_tts_sink: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(instructions=instructions, **kwargs)
        self._responder = responder
        self._streaming_tts_client = streaming_tts_client
        self._streaming_tts_started = False
        self._audio_sink = audio_sink
        self._event_publisher = event_publisher
        self._background_event_tasks: set[asyncio.Task[None]] = set()
        self._tts_mode = tts_mode or (
            "minimax_ws" if streaming_tts_client is not None else "session_say"
        )
        self._voice_tts_sink = voice_tts_sink or (
            "pcm_audio_source" if streaming_tts_client is not None else "session_say"
        )
        self.current_turn_id: str | None = None
        self.current_turn_task: asyncio.Task[Any] | None = None
        self._slow_state: dict[str, Any] = {
            "carryover_inject": [],
            "carryover_skills": [],
            "carryover_retrieval": "",
        }

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        user_text = (getattr(new_message, "text_content", "") or "").strip()
        if not user_text:
            raise StopResponse()

        session_id = voice_session_ctx.get() or "unknown"
        turn_id = (
            voice_turn_ctx.get()
            or get_latest_voice_turn_id(session_id)
            or uuid.uuid4().hex[:8]
        )
        voice_turn_ctx.set(turn_id)
        set_latest_voice_turn_id(session_id, turn_id)

        turn_task = asyncio.create_task(
            self._run_streaming_turn(
                session_id=session_id,
                turn_id=turn_id,
                user_text=user_text,
            )
        )
        self.replace_turn_task(turn_id, turn_task)
        try:
            await turn_task
        except asyncio.CancelledError:
            raise StopResponse() from None

        raise StopResponse()

    async def _run_streaming_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        user_text: str,
    ) -> None:
        memory_file = PROJECT_ROOT / "backend" / "state" / "MEMORY.md"
        guidance_file = PROJECT_ROOT / "backend" / "state" / "SLOW_GUIDANCE.md"
        memory_text = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
        slow_guidance = (
            guidance_file.read_text(encoding="utf-8").strip()
            if guidance_file.exists()
            else ""
        )

        async for sentence in self._responder.stream_reply(
            user_text=user_text,
            memory_text=memory_text,
            slow_guidance=slow_guidance,
            dynamic_inject=list(self._slow_state["carryover_inject"]),
            skill_bundle=list(self._slow_state["carryover_skills"]),
            retrieval_block=str(self._slow_state["carryover_retrieval"]),
            session_id=session_id,
            turn_id=turn_id,
        ):
            logger.info(
                "voice_streaming_sentence",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "text_len": len(sentence),
                },
            )
            await self._publish_event(
                VoiceStreamEvent(
                    type="coco_sentence",
                    session_id=session_id,
                    turn_id=turn_id,
                    text=sentence,
                    is_final=False,
                    meta=self._tts_meta(),
                )
            )
            await self._publish_event(
                VoiceStreamEvent(
                    type="tts_started",
                    session_id=session_id,
                    turn_id=turn_id,
                    text="",
                    is_final=False,
                    meta=self._tts_meta(),
                )
            )
            if self._streaming_tts_client is None:
                activity = self._get_activity_or_raise()
                await activity.session.say(sentence, add_to_chat_ctx=True)
            else:
                await self._synthesize_to_sink(
                    sentence, session_id=session_id, turn_id=turn_id
                )
            await self._publish_event(
                VoiceStreamEvent(
                    type="tts_done",
                    session_id=session_id,
                    turn_id=turn_id,
                    text="",
                    is_final=True,
                    meta=self._tts_meta(),
                )
            )

    async def _synthesize_to_sink(
        self, sentence: str, *, session_id: str, turn_id: str
    ) -> None:
        if self._audio_sink is None:
            raise RuntimeError("audio_sink is required when streaming_tts_client is set")
        tts = self._streaming_tts_client
        if not self._streaming_tts_started:
            await tts.start()
            self._streaming_tts_started = True
        first_audio = True
        async for audio in tts.synthesize_sentence(sentence):
            await self._audio_sink(audio)
            if first_audio:
                logger.info(
                    "voice_streaming_tts_first_audio",
                    extra={
                        "session_id": session_id,
                        "turn_id": turn_id,
                        "audio_bytes": len(audio),
                        **self._tts_meta(),
                    },
                )
                first_audio = False

    def _tts_meta(self) -> dict[str, str]:
        return {
            "tts_mode": self._tts_mode,
            "voice_tts_sink": self._voice_tts_sink,
        }

    def replace_turn_task(self, turn_id: str, task: asyncio.Task[Any]) -> None:
        old_task = self.current_turn_task
        old_turn_id = self.current_turn_id
        if old_task is not None and not old_task.done():
            old_task.cancel()
            if old_turn_id:
                session_id = voice_session_ctx.get() or "unknown"
                self._schedule_event_publish(
                    VoiceStreamEvent(
                        type="turn_interrupted",
                        session_id=session_id,
                        turn_id=old_turn_id,
                        text="",
                        is_final=True,
                        meta=self._tts_meta(),
                    )
                )
        self.current_turn_id = turn_id
        self.current_turn_task = task

    async def _publish_event(self, event: VoiceStreamEvent) -> None:
        if self._event_publisher is None:
            return
        try:
            await self._event_publisher(event)
        except Exception:
            logger.warning(
                "voice_stream_event_publish_failed",
                exc_info=True,
                extra={
                    "session_id": event.session_id,
                    "turn_id": event.turn_id,
                    "event_type": event.type,
                },
            )

    def _schedule_event_publish(self, event: VoiceStreamEvent) -> None:
        if self._event_publisher is None:
            return
        try:
            task = asyncio.create_task(self._publish_event(event))
        except RuntimeError:
            return
        self._background_event_tasks.add(task)
        task.add_done_callback(self._background_event_tasks.discard)

    async def aclose(self) -> None:
        if self._background_event_tasks:
            await asyncio.gather(
                *tuple(self._background_event_tasks), return_exceptions=True
            )
        if self._streaming_tts_client is not None:
            with contextlib.suppress(Exception):
                await self._streaming_tts_client.finish()
