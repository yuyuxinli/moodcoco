from __future__ import annotations

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


def test_voice_system_prompt_stays_compact_for_low_latency() -> None:
    prompt = build_voice_system_prompt()

    assert len(prompt) < 500
    assert "不要输出 JSON" in prompt
    assert "不要调用工具" in prompt
