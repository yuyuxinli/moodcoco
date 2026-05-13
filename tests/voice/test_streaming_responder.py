from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pytest

from backend.voice.streaming_responder import (
    VoiceStreamingResponder,
    build_voice_system_prompt,
)


@dataclass
class _Delta:
    content: str | None


@dataclass
class _Choice:
    delta: _Delta


@dataclass
class _Chunk:
    choices: list[_Choice]


class _FakeCompletions:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self.kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs):
        self.kwargs = kwargs

        async def _stream():
            for token in self._chunks:
                yield _Chunk(choices=[_Choice(delta=_Delta(content=token))])

        return _stream()


class _FakeClient:
    def __init__(self, chunks: list[str]) -> None:
        self.chat = type("Chat", (), {})()
        self.chat.completions = _FakeCompletions(chunks)


@pytest.mark.asyncio
async def test_stream_reply_yields_sentence_chunks() -> None:
    client = _FakeClient(["我知道", "这很难。", "先慢一点"])
    responder = VoiceStreamingResponder(
        client=client,
        model="test-model",
        system_prompt="system",
    )

    chunks = [
        chunk
        async for chunk in responder.stream_reply(
            user_text="我很烦",
            memory_text="",
            slow_guidance="",
            dynamic_inject=[],
            skill_bundle=[],
            retrieval_block="",
        )
    ]

    assert chunks == ["我知道这很难。", "先慢一点"]
    assert client.chat.completions.kwargs["stream"] is True
    assert client.chat.completions.kwargs["model"] == "test-model"


@pytest.mark.asyncio
async def test_stream_reply_logs_llm_latency_milestones(caplog: pytest.LogCaptureFixture) -> None:
    client = _FakeClient(["我知道", "这很难。"])
    responder = VoiceStreamingResponder(
        client=client,
        model="test-model",
        system_prompt="system",
    )

    with caplog.at_level(logging.INFO, logger="voice.streaming_responder"):
        chunks = [
            chunk
            async for chunk in responder.stream_reply(
                user_text="我很烦",
                memory_text="",
                slow_guidance="",
                dynamic_inject=[],
                skill_bundle=[],
                retrieval_block="",
                session_id="session-a",
                turn_id="turn-a",
            )
        ]

    assert chunks == ["我知道这很难。"]
    messages = [record.message for record in caplog.records]
    assert messages == [
        "voice_llm_request_started",
        "voice_llm_first_token",
        "voice_llm_first_sentence",
    ]
    assert caplog.records[0].session_id == "session-a"
    assert caplog.records[0].turn_id == "turn-a"
    assert caplog.records[0].model == "test-model"


def test_voice_system_prompt_stays_compact_for_low_latency() -> None:
    prompt = build_voice_system_prompt()

    assert len(prompt) < 500
    assert "不要输出 JSON" in prompt
    assert "不要调用工具" in prompt
