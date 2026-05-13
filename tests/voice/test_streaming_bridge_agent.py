from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from livekit.agents import StopResponse

from backend.voice.streaming_bridge_agent import StreamingVoiceBridgeAgent
from backend.voice.streaming_events import VoiceStreamEvent


class _Responder:
    async def stream_reply(self, **_kwargs):
        yield "我听见了。"
        yield "我们先慢一点。"


class _StreamingTTS:
    def __init__(self) -> None:
        self.start_count = 0
        self.started = False
        self.finished = False
        self.sentences: list[str] = []

    async def start(self) -> None:
        self.start_count += 1
        self.started = True

    async def synthesize_sentence(self, text: str):
        self.sentences.append(text)
        yield f"audio:{text}".encode("utf-8")

    async def finish(self) -> None:
        self.finished = True


@pytest.mark.asyncio
async def test_streaming_bridge_says_each_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_publisher = AsyncMock()
    agent = StreamingVoiceBridgeAgent(
        instructions="test",
        responder=_Responder(),
        event_publisher=event_publisher,
    )
    session = MagicMock()
    session.say = AsyncMock()
    activity = MagicMock()
    activity.session = session
    monkeypatch.setattr(agent, "_get_activity_or_raise", MagicMock(return_value=activity))

    user_msg = MagicMock()
    user_msg.text_content = "我今天很烦"

    with pytest.raises(StopResponse):
        await agent.on_user_turn_completed(MagicMock(), user_msg)

    assert session.say.await_args_list[0].args[0] == "我听见了。"
    assert session.say.await_args_list[1].args[0] == "我们先慢一点。"
    event_types = [call.args[0].type for call in event_publisher.await_args_list]
    assert event_types == [
        "coco_sentence",
        "tts_started",
        "tts_done",
        "coco_sentence",
        "tts_started",
        "tts_done",
    ]


@pytest.mark.asyncio
async def test_streaming_bridge_uses_tts_client_when_enabled() -> None:
    tts = _StreamingTTS()
    audio_sink = AsyncMock()
    agent = StreamingVoiceBridgeAgent(
        instructions="test",
        responder=_Responder(),
        streaming_tts_client=tts,
        audio_sink=audio_sink,
    )

    user_msg = MagicMock()
    user_msg.text_content = "我今天很烦"

    with pytest.raises(StopResponse):
        await agent.on_user_turn_completed(MagicMock(), user_msg)

    assert tts.started is True
    assert tts.start_count == 1
    assert tts.sentences == ["我听见了。", "我们先慢一点。"]
    assert tts.finished is False
    assert audio_sink.await_count == 2

    await agent.aclose()
    assert tts.finished is True


@pytest.mark.asyncio
async def test_streaming_bridge_cancels_previous_tts_on_new_turn() -> None:
    events: list[VoiceStreamEvent] = []

    async def publish_event(event: VoiceStreamEvent) -> None:
        events.append(event)

    agent = StreamingVoiceBridgeAgent(
        instructions="test",
        responder=_Responder(),
        event_publisher=publish_event,
    )

    first = asyncio.create_task(asyncio.sleep(10))
    second = asyncio.create_task(asyncio.sleep(10))

    agent.replace_turn_task("turn-1", first)
    agent.replace_turn_task("turn-2", second)
    with contextlib.suppress(asyncio.CancelledError):
        await first

    assert first.cancelled()
    assert second is agent.current_turn_task

    second.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await second

    await agent.aclose()
    assert [event.type for event in events] == ["turn_interrupted"]
    assert events[0].turn_id == "turn-1"
