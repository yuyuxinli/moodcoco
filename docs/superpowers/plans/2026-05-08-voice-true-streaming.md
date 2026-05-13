# Voice True Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current batch voice pipeline with a true streaming voice pipeline: streaming ASR input, streaming LLM sentence output, streaming MiniMax TTS audio, and live browser transcript events.

**Architecture:** Keep the existing pydantic-ai Fast/Slow text/UI path intact. Add a voice-only streaming path under `backend/voice/` that converts LiveKit audio frames into partial transcripts, converts final transcript into streamed LLM sentence chunks, streams those chunks to MiniMax WebSocket TTS, and publishes audio/events back through LiveKit. Preserve current batch STT/TTS as fallback until streaming is proven in e2e.

**Tech Stack:** Python 3.12, LiveKit Agents, OpenAI-compatible streaming chat via `openai.AsyncOpenAI`, Xfyun WebSocket ASR, MiniMax T2A WebSocket, FastAPI, Next.js, pytest, npm eslint.

---

## Current State

The current voice path is not true streaming:

- `backend/voice/entrypoint.py` wraps `XfyunSTTPlugin()` with LiveKit `stt.StreamAdapter` and Silero VAD. Audio is streamed into LiveKit, but recognition starts only after VAD cuts a full utterance.
- `backend/voice/plugins/xfyun_stt.py` is batch/offline: it writes PCM to a temp file and calls `XfyunASR.recognize()`.
- `backend/voice/bridge_agent.py` waits for `on_user_turn_completed()` before starting Fast/Slow.
- `backend/fast.py` uses pydantic-ai tool calls. In voice mode, `ai_message()` calls `session.say(text, add_to_chat_ctx=True)` once it receives complete tool arguments.
- `backend/voice/plugins/minimax_tts.py` advertises `TTSCapabilities(streaming=False)` and waits for full `synthesize_bytes()` MP3 before pushing audio chunks to LiveKit.
- `web/lib/use-livekit-voice.ts` subscribes to LiveKit audio, but does not show transcript or reply deltas.

The target is a new streaming path that can be enabled by env flag first, then become default.

---

## File Structure

### New Backend Files

- `backend/voice/streaming_events.py`
  - Defines typed event payloads for `user_partial`, `user_final`, `coco_delta`, `coco_sentence`, `tts_started`, `tts_done`, `turn_interrupted`, and `stream_error`.

- `backend/voice/livekit_data.py`
  - Serializes streaming events to LiveKit data channel.
  - Keeps browser display independent from audio playback.

- `backend/voice/streaming_text.py`
  - Sentence segmentation for streamed LLM tokens.
  - Chinese punctuation-aware buffering.
  - Unit-tested without network.

- `backend/voice/streaming_responder.py`
  - Voice-only OpenAI-compatible streaming LLM client.
  - Reuses project prompts and memory/guidance.
  - Yields sentence chunks, not UI tool calls.

- `backend/voice/plugins/minimax_streaming_tts.py`
  - MiniMax T2A WebSocket streaming TTS plugin.
  - Implements streaming text input to audio output.
  - Falls back to current `MinimaxTTSPlugin` on startup failure.

- `backend/voice/plugins/xfyun_streaming_stt.py`
  - Xfyun streaming ASR plugin or voice-node helper.
  - Handles PCM frame upload, partial/final transcript parsing, dynamic correction, and end-of-turn finalization.

- `backend/voice/streaming_bridge_agent.py`
  - Streaming voice agent/turn manager.
  - Coordinates ASR partial/final, LLM sentence chunks, TTS stream, interruption, and Slow background work.

### Modified Backend Files

- `backend/voice/entrypoint.py`
  - Adds env flag `VOICE_STREAMING_MODE=true`.
  - Chooses streaming vs current batch path.
  - Wires new streaming bridge and plugins.

- `backend/voice/bridge_agent.py`
  - Leave batch path working.
  - Share any reusable Slow carryover helper only if needed.

- `backend/llm_provider.py`
  - Add helper for voice streaming OpenAI client/model resolution if existing helpers are insufficient.

- `pyproject.toml`
  - Add `websockets>=12` if not already available through dependencies.

### Modified Frontend Files

- `web/lib/voice-types.ts`
  - Add streaming event TypeScript types.

- `web/lib/use-livekit-voice.ts`
  - Subscribe to LiveKit data messages.
  - Maintain `userPartial`, `lastUserFinal`, `cocoPartial`, and `cocoSentences`.

- `web/components/voice/VoiceButton.tsx`
  - Show compact live transcript/debug status under the button.

### Tests

- `tests/voice/test_streaming_text.py`
- `tests/voice/test_streaming_responder.py`
- `tests/voice/test_minimax_streaming_tts.py`
- `tests/voice/test_xfyun_streaming_stt.py`
- `tests/voice/test_streaming_bridge_agent.py`
- `web` lint only initially; add component tests later if a web test framework is introduced.

---

## Rollout Strategy

Use an env-gated rollout:

```bash
VOICE_STREAMING_MODE=false  # default during development
VOICE_STREAMING_MODE=true   # opt into new path
VOICE_STREAMING_TTS_MODE=session_say  # Task 6 default
VOICE_STREAMING_TTS_MODE=minimax_ws    # Task 7 MiniMax WebSocket path
```

Task 7 also requires `MINIMAX_GROUP_ID` in `.env`; `MINIMAX_API_KEY` alone is not enough for the MiniMax WebSocket URL.

Keep existing batch voice path available until these e2e gates pass:

- `time_to_first_audio_ms <= 1800` for a normal short Chinese utterance.
- `user_partial` appears before final transcript.
- `coco_sentence` appears before TTS completion.
- User can speak a second turn without losing agent audio.
- Batch fallback still works if streaming TTS/STT initialization fails.

---

### Task 1: Streaming Event Contract

**Files:**
- Create: `backend/voice/streaming_events.py`
- Create: `backend/voice/livekit_data.py`
- Modify: `web/lib/voice-types.ts`
- Test: `tests/voice/test_streaming_events.py`

- [ ] **Step 1: Write failing backend event serialization tests**

Create `tests/voice/test_streaming_events.py`:

```python
from __future__ import annotations

import json

from backend.voice.streaming_events import VoiceStreamEvent


def test_voice_stream_event_serializes_minimal_payload() -> None:
    event = VoiceStreamEvent(
        type="user_partial",
        session_id="room-1",
        turn_id="turn-1",
        text="我今天",
        is_final=False,
    )

    payload = event.to_json_bytes()
    decoded = json.loads(payload.decode("utf-8"))

    assert decoded == {
        "type": "user_partial",
        "session_id": "room-1",
        "turn_id": "turn-1",
        "text": "我今天",
        "is_final": False,
        "meta": {},
    }


def test_voice_stream_event_rejects_unknown_type() -> None:
    try:
        VoiceStreamEvent(
            type="unknown",
            session_id="room-1",
            turn_id="turn-1",
            text="x",
        )
    except ValueError as exc:
        assert "unknown voice stream event type" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/voice/test_streaming_events.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.voice.streaming_events'`.

- [ ] **Step 3: Implement event dataclass**

Create `backend/voice/streaming_events.py`:

```python
"""Typed events for browser-visible voice streaming state."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

VoiceStreamEventType = Literal[
    "user_partial",
    "user_final",
    "coco_delta",
    "coco_sentence",
    "tts_started",
    "tts_done",
    "turn_interrupted",
    "stream_error",
]

_VALID_EVENT_TYPES: set[str] = {
    "user_partial",
    "user_final",
    "coco_delta",
    "coco_sentence",
    "tts_started",
    "tts_done",
    "turn_interrupted",
    "stream_error",
}


@dataclass(slots=True)
class VoiceStreamEvent:
    type: VoiceStreamEventType
    session_id: str
    turn_id: str
    text: str = ""
    is_final: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in _VALID_EVENT_TYPES:
            raise ValueError(f"unknown voice stream event type: {self.type}")

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "type": self.type,
                "session_id": self.session_id,
                "turn_id": self.turn_id,
                "text": self.text,
                "is_final": self.is_final,
                "meta": self.meta,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
```

- [ ] **Step 4: Implement LiveKit data publisher wrapper**

Create `backend/voice/livekit_data.py`:

```python
"""LiveKit data-channel helpers for voice streaming events."""
from __future__ import annotations

import inspect
import logging
from typing import Any

from backend.voice.streaming_events import VoiceStreamEvent

logger = logging.getLogger("voice.livekit_data")


async def publish_voice_event(room: Any, event: VoiceStreamEvent) -> None:
    """Publish a voice event to all participants.

    The LiveKit Python SDK has had small API differences across versions, so this
    wrapper tries the local participant first and logs a warning if publishing is
    unavailable. It must never break the audio path.
    """
    local_participant = getattr(room, "local_participant", None)
    publish_data = getattr(local_participant, "publish_data", None)
    if not callable(publish_data):
        logger.warning(
            "voice_event_publish_unavailable",
            extra={"event_type": event.type, "session_id": event.session_id},
        )
        return

    try:
        result = publish_data(event.to_json_bytes(), reliable=True, topic="voice-stream")
    except TypeError:
        result = publish_data(event.to_json_bytes(), reliable=True)
    if inspect.isawaitable(result):
        await result
```

- [ ] **Step 5: Add frontend event types**

Modify `web/lib/voice-types.ts` and add:

```ts
export type VoiceStreamEventType =
  | "user_partial"
  | "user_final"
  | "coco_delta"
  | "coco_sentence"
  | "tts_started"
  | "tts_done"
  | "turn_interrupted"
  | "stream_error";

export interface VoiceStreamEvent {
  type: VoiceStreamEventType;
  session_id: string;
  turn_id: string;
  text: string;
  is_final: boolean;
  meta: Record<string, unknown>;
}
```

- [ ] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/voice/test_streaming_events.py -q
npm run lint
```

Expected: pytest PASS, lint PASS.

- [ ] **Step 7: Review changed files**

```bash
git diff --stat backend/voice/streaming_events.py backend/voice/livekit_data.py tests/voice/test_streaming_events.py web/lib/voice-types.ts
```

---

### Task 2: Sentence Segmentation For Streaming LLM

**Files:**
- Create: `backend/voice/streaming_text.py`
- Test: `tests/voice/test_streaming_text.py`

- [ ] **Step 1: Write failing tests**

Create `tests/voice/test_streaming_text.py`:

```python
from __future__ import annotations

from backend.voice.streaming_text import SentenceChunker


def test_sentence_chunker_flushes_on_chinese_punctuation() -> None:
    chunker = SentenceChunker(max_chars=40)

    assert chunker.push("我知道") == []
    assert chunker.push("这很难。") == ["我知道这很难。"]
    assert chunker.flush() == []


def test_sentence_chunker_flushes_when_buffer_is_long() -> None:
    chunker = SentenceChunker(max_chars=8)

    assert chunker.push("你现在心里很堵") == ["你现在心里很堵"]


def test_sentence_chunker_keeps_short_tail_until_flush() -> None:
    chunker = SentenceChunker(max_chars=40)

    assert chunker.push("我们先慢一点") == []
    assert chunker.flush() == ["我们先慢一点"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/voice/test_streaming_text.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement `SentenceChunker`**

Create `backend/voice/streaming_text.py`:

```python
"""Utilities for turning streamed LLM tokens into speakable sentence chunks."""
from __future__ import annotations

_BOUNDARY_CHARS = set("。！？!?；;\n")


class SentenceChunker:
    def __init__(self, *, max_chars: int = 36) -> None:
        self._max_chars = max_chars
        self._buffer = ""

    def push(self, text: str) -> list[str]:
        self._buffer += text
        out: list[str] = []

        while self._buffer:
            boundary = self._find_boundary(self._buffer)
            if boundary is not None:
                segment = self._buffer[: boundary + 1].strip()
                self._buffer = self._buffer[boundary + 1 :]
                if segment:
                    out.append(segment)
                continue

            if len(self._buffer) >= self._max_chars:
                segment = self._buffer.strip()
                self._buffer = ""
                if segment:
                    out.append(segment)
            break

        return out

    def flush(self) -> list[str]:
        segment = self._buffer.strip()
        self._buffer = ""
        return [segment] if segment else []

    @staticmethod
    def _find_boundary(text: str) -> int | None:
        for idx, char in enumerate(text):
            if char in _BOUNDARY_CHARS:
                return idx
        return None
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/voice/test_streaming_text.py -q
```

Expected: PASS.

- [ ] **Step 5: Review changed files**

```bash
git diff --stat backend/voice/streaming_text.py tests/voice/test_streaming_text.py
```

---

### Task 3: Voice Streaming LLM Responder

**Files:**
- Create: `backend/voice/streaming_responder.py`
- Modify: `backend/llm_provider.py`
- Test: `tests/voice/test_streaming_responder.py`

- [ ] **Step 1: Write failing tests for streamed sentence chunks**

Create `tests/voice/test_streaming_responder.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from backend.voice.streaming_responder import VoiceStreamingResponder


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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/voice/test_streaming_responder.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Add OpenAI streaming client helper**

Modify `backend/llm_provider.py`:

```python
def create_voice_streaming_client():
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        base_url=os.environ.get("DOUBAO_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.environ.get("DOUBAO_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("OPENROUTER_API_KEY"),
    )


def get_voice_streaming_model_name() -> str:
    return (
        os.environ.get("DOUBAO_MODEL")
        or os.environ.get("OPENAI_FAST_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "doubao-seed-2-0-lite-260215"
    )
```

- [ ] **Step 4: Implement responder**

Create `backend/voice/streaming_responder.py`:

```python
"""Voice-only streaming LLM responder.

This intentionally does not use pydantic-ai tool calls. The voice path needs
token/sentence streaming, while the text UI path keeps the existing tool model.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from backend.llm_provider import load_prompt
from backend.voice.streaming_text import SentenceChunker


def _load_prompt_or_empty(relative_path: str) -> str:
    try:
        return load_prompt(relative_path)
    except FileNotFoundError:
        return ""


def build_voice_system_prompt() -> str:
    return "\n\n".join(
        part
        for part in [
            _load_prompt_or_empty("backend/prompts/SOUL.md"),
            _load_prompt_or_empty("backend/prompts/IDENTITY.md"),
            _load_prompt_or_empty("backend/prompts/AGENTS.md"),
            "## 实时语音模式\n"
            "只输出可直接说给用户听的中文短句。"
            "不要输出 JSON。不要调用工具。"
            "优先一句承接情绪，再问一个具体问题。"
            "每句尽量 10 到 30 个中文字符。",
        ]
        if part.strip()
    )


class VoiceStreamingResponder:
    def __init__(self, *, client: Any, model: str, system_prompt: str | None = None) -> None:
        self._client = client
        self._model = model
        self._system_prompt = system_prompt or build_voice_system_prompt()

    async def stream_reply(
        self,
        *,
        user_text: str,
        memory_text: str,
        slow_guidance: str,
        dynamic_inject: list[str],
        skill_bundle: list[str],
        retrieval_block: str,
    ) -> AsyncGenerator[str, None]:
        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "system",
                "content": self._format_context(
                    memory_text=memory_text,
                    slow_guidance=slow_guidance,
                    dynamic_inject=dynamic_inject,
                    skill_bundle=skill_bundle,
                    retrieval_block=retrieval_block,
                ),
            },
            {"role": "user", "content": user_text},
        ]
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            temperature=0.7,
        )
        chunker = SentenceChunker(max_chars=36)
        async for event in stream:
            if not getattr(event, "choices", None):
                continue
            token = getattr(event.choices[0].delta, "content", None)
            if not token:
                continue
            for sentence in chunker.push(token):
                yield sentence
        for sentence in chunker.flush():
            yield sentence

    @staticmethod
    def _format_context(
        *,
        memory_text: str,
        slow_guidance: str,
        dynamic_inject: list[str],
        skill_bundle: list[str],
        retrieval_block: str,
    ) -> str:
        parts: list[str] = []
        if memory_text.strip():
            parts.append("## MEMORY\n" + memory_text.strip())
        if slow_guidance.strip():
            parts.append("## 上一轮慢思考指导\n" + slow_guidance.strip())
        if dynamic_inject:
            parts.append("## Slow 动态注入\n" + "\n".join(dynamic_inject))
        if skill_bundle:
            parts.append("## Skill 片段\n" + "\n\n---\n\n".join(skill_bundle))
        if retrieval_block.strip():
            parts.append("## 检索补充\n" + retrieval_block.strip())
        return "\n\n".join(parts) or "无额外上下文。"
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/voice/test_streaming_text.py tests/voice/test_streaming_responder.py -q
```

Expected: PASS.

- [ ] **Step 6: Review changed files**

```bash
git diff --stat backend/llm_provider.py backend/voice/streaming_responder.py tests/voice/test_streaming_responder.py
```

---

### Task 4: MiniMax WebSocket Streaming TTS

**Files:**
- Create: `backend/voice/plugins/minimax_streaming_tts.py`
- Test: `tests/voice/test_minimax_streaming_tts.py`
- Modify: `pyproject.toml`

MiniMax WebSocket `data.audio` is treated as hex-encoded audio bytes in this plan. For the LiveKit `AudioSource` path, first verify `audio_setting.format="pcm"` with the real provider. Do not decode individual MP3 chunks with `miniaudio.decode()`.

- [ ] **Step 1: Add dependency**

Modify `pyproject.toml` voice dependency group:

```toml
voice = [
    "livekit-agents>=1.0",
    "livekit-api>=1.0",
    "livekit-plugins-openai>=1.0",
    "livekit-plugins-silero>=1.0",
    "websocket-client>=1.0",
    "websockets>=12",
    "httpx>=0.27",
]
```

- [ ] **Step 2: Write failing unit test with fake websocket**

Create `tests/voice/test_minimax_streaming_tts.py`:

```python
from __future__ import annotations

import json
from asyncio import Queue

import pytest

from backend.voice.plugins.minimax_streaming_tts import (
    MiniMaxStreamingTTSClient,
    MiniMaxStreamingTTSConfig,
)


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.recv_queue: Queue[dict] = Queue()
        self.closed = False

    def push(self, message: dict) -> None:
        self.recv_queue.put_nowait(message)

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def recv(self) -> str:
        return json.dumps(await self.recv_queue.get())

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_minimax_streaming_client_sends_text_and_yields_audio() -> None:
    ws = _FakeWebSocket()
    ws.push({"event": "connected_success", "base_resp": {"status_code": 0}})
    ws.push({"event": "task_started", "base_resp": {"status_code": 0}})
    ws.push(
        {
            "data": {"audio": b"audio-1".hex()},
            "is_final": False,
            "base_resp": {"status_code": 0},
        }
    )
    ws.push(
        {
            "data": {"audio": b"audio-2".hex()},
            "is_final": True,
            "base_resp": {"status_code": 0},
        }
    )
    seen: dict[str, object] = {}
    client = MiniMaxStreamingTTSClient(
        config=MiniMaxStreamingTTSConfig(api_key="key", group_id="group"),
        websocket_factory=lambda url, headers: (seen.update(url=url, headers=headers) or ws),
    )

    await client.start()
    chunks = [chunk async for chunk in client.synthesize_sentence("你好。")]
    await client.finish()

    assert chunks == [b"audio-1", b"audio-2"]
    assert ws.sent[0]["event"] == "task_start"
    assert ws.sent[0]["audio_setting"]["format"] == "pcm"
    assert ws.sent[1] == {"event": "task_continue", "text": "你好。"}
    assert ws.sent[-1] == {"event": "task_finish"}
    assert seen["url"] == "wss://api.minimax.io/ws/v1/t2a_v2?GroupId=group"
    assert seen["headers"] == {"Authorization": "Bearer key"}
    assert ws.closed is True
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
uv run pytest tests/voice/test_minimax_streaming_tts.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 4: Implement WebSocket client**

Create `backend/voice/plugins/minimax_streaming_tts.py` with this public interface:

```python
"""MiniMax WebSocket T2A streaming client and LiveKit TTS adapter."""
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

import websockets


@dataclass(slots=True)
class MiniMaxStreamingTTSConfig:
    api_key: str
    group_id: str
    model: str = "speech-2.8-turbo"
    voice_id: str = "Chinese (Mandarin)_Cute_Spirit"
    sample_rate: int = 32000
    channel: int = 1
    audio_format: str = "pcm"
    language_boost: str = "Chinese"

    @classmethod
    def from_env(cls) -> "MiniMaxStreamingTTSConfig":
        return cls(
            api_key=os.environ["MINIMAX_API_KEY"],
            group_id=os.environ["MINIMAX_GROUP_ID"],
            model=os.environ.get("MINIMAX_TTS_MODEL", "speech-2.8-turbo"),
            voice_id=os.environ.get(
                "MINIMAX_TTS_VOICE_ID",
                "Chinese (Mandarin)_Cute_Spirit",
            ),
        )


class MiniMaxStreamingTTSClient:
    def __init__(
        self,
        *,
        config: MiniMaxStreamingTTSConfig,
        websocket_factory: Callable[[str, dict[str, str]], Any] | None = None,
    ) -> None:
        self._config = config
        self._websocket_factory = websocket_factory
        self._ws: Any | None = None

    async def start(self) -> None:
        url = f"wss://api.minimax.io/ws/v1/t2a_v2?GroupId={self._config.group_id}"
        headers = {"Authorization": f"Bearer {self._config.api_key}"}
        if self._websocket_factory is None:
            self._ws = await websockets.connect(url, additional_headers=headers)
        else:
            self._ws = self._websocket_factory(url, headers)

        await self._expect_ok("connected_success")
        await self._send(
            {
                "event": "task_start",
                "model": self._config.model,
                "language_boost": self._config.language_boost,
                "voice_setting": {
                    "voice_id": self._config.voice_id,
                    "speed": 1,
                    "vol": 1,
                    "pitch": 0,
                },
                "audio_setting": {
                    "sample_rate": self._config.sample_rate,
                    "format": self._config.audio_format,
                    "channel": self._config.channel,
                },
            }
        )
        await self._expect_ok("task_started")

    async def synthesize_sentence(self, text: str) -> AsyncIterator[bytes]:
        await self._send({"event": "task_continue", "text": text})
        while True:
            message = await self._recv()
            audio_hex = (message.get("data") or {}).get("audio")
            if audio_hex:
                yield bytes.fromhex(audio_hex)
            if message.get("is_final"):
                break

    async def finish(self) -> None:
        await self._send({"event": "task_finish"})
        ws = self._require_ws()
        await ws.close()

    async def _send(self, payload: dict[str, Any]) -> None:
        await self._require_ws().send(json.dumps(payload, ensure_ascii=False))

    async def _recv(self) -> dict[str, Any]:
        return json.loads(await self._require_ws().recv())

    async def _expect_ok(self, event_name: str) -> None:
        message = await self._recv()
        if message.get("event") != event_name:
            raise RuntimeError(f"expected {event_name}, got {message}")
        status = (message.get("base_resp") or {}).get("status_code", 0)
        if status != 0:
            raise RuntimeError(f"MiniMax TTS error: {message}")

    def _require_ws(self) -> Any:
        if self._ws is None:
            raise RuntimeError("MiniMax streaming TTS websocket is not started")
        return self._ws
```

- [ ] **Step 5: Add LiveKit adapter**

Extend the same file with a `MiniMaxStreamingTTSPlugin` that advertises streaming:

```python
from livekit.agents.tts import TTS, TTSCapabilities


class MiniMaxStreamingTTSPlugin(TTS):
    def __init__(self, *, config: MiniMaxStreamingTTSConfig | None = None) -> None:
        config = config or MiniMaxStreamingTTSConfig.from_env()
        super().__init__(
            capabilities=TTSCapabilities(streaming=True),
            sample_rate=config.sample_rate,
            num_channels=config.channel,
        )
        self.config = config

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def provider(self) -> str:
        return "minimax"
```

Keep this adapter unreferenced from `entrypoint.py` in this task. Task 7 performs the LiveKit integration decision and must prove whether this repo version can publish MiniMax WebSocket audio directly.

- [ ] **Step 6: Run tests**

Run:

```bash
uv run pytest tests/voice/test_minimax_streaming_tts.py -q
```

Expected: PASS.

- [ ] **Step 7: Verify provider PCM support with real MiniMax**

With `MINIMAX_API_KEY` and `MINIMAX_GROUP_ID` loaded, run a single real WebSocket request and print the first audio payload:

```bash
uv run python - <<'PY'
import asyncio
import os
from dotenv import load_dotenv

from backend.voice.plugins.minimax_streaming_tts import (
    MiniMaxStreamingTTSClient,
    MiniMaxStreamingTTSConfig,
)

async def main() -> None:
    load_dotenv("/home/yizhuo_wang/code1/moodcoco/.env", override=False)
    client = MiniMaxStreamingTTSClient(config=MiniMaxStreamingTTSConfig.from_env())
    await client.start()
    try:
        async for chunk in client.synthesize_sentence("你好。"):
            print("first_chunk_len", len(chunk))
            break
    finally:
        await client.finish()

asyncio.run(main())
PY
```

Expected:

- `client.start()` succeeds with `audio_setting.format="pcm"`.
- it prints a non-zero `first_chunk_len`.
- `first_chunk_len % 2 == 0`, because the chunk should be signed 16-bit mono PCM.

If MiniMax rejects `format="pcm"` or the real payload is not raw 16-bit PCM, stop before Task 7 Branch B. In that case Branch B cannot use `rtc.AudioSource` directly; use Branch A if encoded-audio publication exists, or add a stateful MP3 streaming decoder plan. Do not reintroduce `miniaudio.decode()` on individual MP3 chunks.

If `bytes.fromhex(...)` fails, capture `repr(raw_audio[:40])` from the provider response before changing the decoder.

For that capture, temporarily add a debug log in `MiniMaxStreamingTTSClient.synthesize_sentence()` before decoding:

```python
logger.info("minimax_raw_audio_prefix", extra={"raw_audio_prefix": repr(audio_hex[:40])})
```

Remove the raw prefix log after the provider encoding is confirmed.

- [ ] **Step 8: Review changed files**

```bash
git diff --stat pyproject.toml backend/voice/plugins/minimax_streaming_tts.py tests/voice/test_minimax_streaming_tts.py
```

---

### Task 5: Xfyun Streaming STT Client

**Files:**
- Create: `backend/voice/plugins/xfyun_streaming_stt.py`
- Test: `tests/voice/test_xfyun_streaming_stt.py`

- [ ] **Step 1: Write parsing tests first**

Create `tests/voice/test_xfyun_streaming_stt.py`:

```python
from __future__ import annotations

from backend.voice.plugins.xfyun_streaming_stt import parse_xfyun_iat_message


def test_parse_xfyun_iat_partial_message() -> None:
    message = {
        "code": 0,
        "data": {
            "status": 1,
            "result": {
                "ws": [
                    {"cw": [{"w": "我"}]},
                    {"cw": [{"w": "今天"}]},
                ]
            },
        },
    }

    event = parse_xfyun_iat_message(message)

    assert event.text == "我今天"
    assert event.is_final is False


def test_parse_xfyun_iat_final_message() -> None:
    message = {
        "code": 0,
        "data": {
            "status": 2,
            "result": {
                "ws": [
                    {"cw": [{"w": "很"}]},
                    {"cw": [{"w": "难过"}]},
                ]
            },
        },
    }

    event = parse_xfyun_iat_message(message)

    assert event.text == "很难过"
    assert event.is_final is True


def test_parse_xfyun_iat_dynamic_replacement_metadata() -> None:
    message = {
        "code": 0,
        "data": {
            "status": 1,
            "result": {
                "pgs": "rpl",
                "rg": [2, 4],
                "ws": [{"cw": [{"w": "现在"}]}, {"cw": [{"w": "很难过"}]}],
            },
        },
    }

    event = parse_xfyun_iat_message(message)

    assert event.text == "现在很难过"
    assert event.segments == ["现在", "很难过"]
    assert event.pgs == "rpl"
    assert event.rg == [2, 4]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/voice/test_xfyun_streaming_stt.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement parser and event type**

Create `backend/voice/plugins/xfyun_streaming_stt.py`:

```python
"""Xfyun streaming ASR helpers.

First implementation provides protocol parsing and a client boundary. The full
LiveKit STT integration is wired in Task 8.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class XfyunTranscriptEvent:
    text: str
    is_final: bool
    segments: list[str] = field(default_factory=list)
    pgs: str | None = None
    rg: list[int] | None = None


def parse_xfyun_iat_message(message: dict[str, Any]) -> XfyunTranscriptEvent:
    code = int(message.get("code", 0))
    if code != 0:
        raise RuntimeError(f"Xfyun streaming ASR error: {message}")
    data = message.get("data") or {}
    result = data.get("result") or {}
    segments: list[str] = []
    for item in result.get("ws") or []:
        candidates = item.get("cw") or []
        if candidates:
            text = str(candidates[0].get("w") or "")
            if text:
                segments.append(text)
    return XfyunTranscriptEvent(
        text="".join(segments),
        is_final=int(data.get("status", 0)) == 2,
        segments=segments,
        pgs=result.get("pgs"),
        rg=result.get("rg"),
    )
```

- [ ] **Step 4: Add client boundary with explicit disabled runtime methods**

Extend `backend/voice/plugins/xfyun_streaming_stt.py`:

```python
class XfyunStreamingASRClient:
    async def start(self) -> None:
        raise RuntimeError("Xfyun streaming ASR runtime is disabled before Task 8")

    async def send_pcm(self, pcm: bytes, *, status: int) -> None:
        raise RuntimeError("Xfyun streaming ASR runtime is disabled before Task 8")

    async def events(self):
        raise RuntimeError("Xfyun streaming ASR runtime is disabled before Task 8")

    async def close(self) -> None:
        raise RuntimeError("Xfyun streaming ASR runtime is disabled before Task 8")
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/voice/test_xfyun_streaming_stt.py -q
```

Expected: PASS.

- [ ] **Step 6: Review changed files**

```bash
git diff --stat backend/voice/plugins/xfyun_streaming_stt.py tests/voice/test_xfyun_streaming_stt.py
```

---

### Task 6: Streaming Bridge Agent With Existing Final Transcript Input

**Files:**
- Create: `backend/voice/streaming_bridge_agent.py`
- Modify: `backend/voice/entrypoint.py`
- Test: `tests/voice/test_streaming_bridge_agent.py`

**Boundary:** This milestone validates only LLM sentence streaming and one-by-one LiveKit playback through the existing `session.say()` path. It must not create or start `MiniMaxStreamingTTSClient`; Task 7 is the first task that proves the MiniMax WebSocket audio path.

This task does not yet replace STT. It keeps current VAD final transcript input and streams only LLM output to MiniMax streaming TTS. This gives a working intermediate milestone.

Before implementing, inspect the installed LiveKit Agent session access path:

```bash
uv run python - <<'PY'
import inspect
from livekit.agents import Agent

print(hasattr(Agent, "_get_activity_or_raise"))
print(inspect.getsource(Agent._get_activity_or_raise))
PY
```

If this private helper is unavailable in the installed version, use the public session access path exposed by that version and update the test accordingly.

- [ ] **Step 1: Write failing bridge test**

Create `tests/voice/test_streaming_bridge_agent.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from livekit.agents import StopResponse

from backend.voice.streaming_bridge_agent import StreamingVoiceBridgeAgent


class _Responder:
    async def stream_reply(self, **_kwargs):
        yield "我听见了。"
        yield "我们先慢一点。"


@pytest.mark.asyncio
async def test_streaming_bridge_says_each_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = StreamingVoiceBridgeAgent(
        instructions="test",
        responder=_Responder(),
    )
    session = MagicMock()
    session.say = AsyncMock()
    activity = MagicMock()
    activity.session = session
    agent._get_activity_or_raise = MagicMock(return_value=activity)

    user_msg = MagicMock()
    user_msg.text_content = "我今天很烦"

    with pytest.raises(StopResponse):
        await agent.on_user_turn_completed(MagicMock(), user_msg)

    assert session.say.await_args_list[0].args[0] == "我听见了。"
    assert session.say.await_args_list[1].args[0] == "我们先慢一点。"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/voice/test_streaming_bridge_agent.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement bridge agent milestone**

Create `backend/voice/streaming_bridge_agent.py`:

```python
"""Streaming voice bridge milestone.

Milestone 1 keeps current final transcript input but streams LLM sentence chunks
to speech one by one through the existing LiveKit `session.say()` path. Task 7
switches output to the MiniMax WebSocket audio path, and Task 8 replaces input
with true streaming STT.
"""
from __future__ import annotations

import logging
import uuid
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

logger = logging.getLogger("voice.streaming_bridge_agent")


class StreamingVoiceBridgeAgent(Agent):
    def __init__(
        self,
        *,
        instructions: str,
        responder: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(instructions=instructions, **kwargs)
        self._responder = responder
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

        memory_file = PROJECT_ROOT / "backend" / "state" / "MEMORY.md"
        guidance_file = PROJECT_ROOT / "backend" / "state" / "SLOW_GUIDANCE.md"
        memory_text = memory_file.read_text(encoding="utf-8") if memory_file.exists() else ""
        slow_guidance = guidance_file.read_text(encoding="utf-8") if guidance_file.exists() else ""

        activity = self._get_activity_or_raise()
        session = activity.session
        async for sentence in self._responder.stream_reply(
            user_text=user_text,
            memory_text=memory_text,
            slow_guidance=slow_guidance,
            dynamic_inject=list(self._slow_state["carryover_inject"]),
            skill_bundle=list(self._slow_state["carryover_skills"]),
            retrieval_block=str(self._slow_state["carryover_retrieval"]),
        ):
            logger.info(
                "voice_streaming_sentence",
                extra={
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "text_len": len(sentence),
                },
            )
            await session.say(sentence, add_to_chat_ctx=True)

        raise StopResponse()
```

- [ ] **Step 4: Wire env flag in entrypoint**

Modify `backend/voice/entrypoint.py` imports:

```python
from backend.llm_provider import create_voice_streaming_client, get_voice_streaming_model_name
from backend.voice.streaming_bridge_agent import StreamingVoiceBridgeAgent
from backend.voice.streaming_responder import VoiceStreamingResponder
```

Modify the agent construction block:

```python
        if os.environ.get("VOICE_STREAMING_MODE", "").lower() == "true":
            responder = VoiceStreamingResponder(
                client=create_voice_streaming_client(),
                model=get_voice_streaming_model_name(),
            )
            agent = StreamingVoiceBridgeAgent(
                instructions=_DEFAULT_INSTRUCTIONS,
                responder=responder,
            )
        else:
            agent = VoiceBridgeAgent(instructions=_DEFAULT_INSTRUCTIONS)
```

Keep `stt_plugin` and `tts_plugin` unchanged in this task so final transcript and fallback audio still work.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/voice/test_streaming_bridge_agent.py tests/voice/test_streaming_responder.py tests/voice/test_minimax_streaming_tts.py -q
```

Expected: PASS.

- [ ] **Step 6: Manual smoke test**

Run backend worker with:

```bash
VOICE_STREAMING_MODE=true uv run python -c "import os; from dotenv import load_dotenv; load_dotenv('/home/yizhuo_wang/code1/moodcoco/.env', override=False); os.environ.setdefault('DOUBAO_API_KEY', os.environ.get('OPENAI_API_KEY','')); os.environ.setdefault('DOUBAO_BASE_URL', os.environ.get('OPENAI_BASE_URL','')); os.environ.setdefault('DOUBAO_MODEL', os.environ.get('OPENAI_FAST_MODEL') or os.environ.get('OPENAI_MODEL','')); from backend.voice.entrypoint import voice_entrypoint; from livekit.agents import cli, WorkerOptions; cli.run_app(WorkerOptions(entrypoint_fnc=voice_entrypoint, agent_name='moodcoco-coco'))" start
```

Expected logs:

- `voice_streaming_sentence`
- browser hears each sentence in order
- no `minimax_streaming_tts_*` requirement in this task

This manual smoke is not accepted as MiniMax WebSocket streaming evidence. It only proves that final transcript input can drive sentence-level LLM output without waiting for the complete reply.

- [ ] **Step 7: Review changed files**

```bash
git diff --stat backend/voice/streaming_bridge_agent.py backend/voice/entrypoint.py tests/voice/test_streaming_bridge_agent.py
```

---

### Task 7: MiniMax Streaming TTS Audio Integration

**Files:**
- Modify: `backend/voice/streaming_bridge_agent.py`
- Modify: `backend/voice/entrypoint.py`
- Test: `tests/voice/test_streaming_bridge_agent.py`

**Boundary:** This task chooses one output path and uses it consistently. When `VOICE_STREAMING_TTS_MODE=minimax_ws`, Coco audio must come from `MiniMaxStreamingTTSClient.synthesize_sentence()`. Do not call `session.say()` in that mode.

- [ ] **Step 1: Write bridge test for real TTS client usage**

Extend `tests/voice/test_streaming_bridge_agent.py`:

```python
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
```

- [ ] **Step 2: Add explicit output modes**

Add imports:

```python
import contextlib
from collections.abc import Awaitable, Callable
```

Modify `StreamingVoiceBridgeAgent.__init__`:

```python
        streaming_tts_client: Any | None = None,
        audio_sink: Callable[[bytes], Awaitable[None]] | None = None,
```

Rules:

- If `streaming_tts_client is None`, use the Task 6 `session.say()` path.
- If `streaming_tts_client` is set, do not call `session.say()` for Coco audio.
- Start the streaming TTS client once and reuse it across turns. Do not open a new MiniMax WebSocket for every user turn; the connection handshake would erase much of the streaming latency gain.
- Send every byte chunk yielded by `synthesize_sentence()` to `audio_sink`.
- Wrap `tts.finish()` in `contextlib.suppress(Exception)` inside the `finally` block so cancelled turns cannot leak WebSocket cleanup exceptions over the original cancellation.
- Keep sentence-level `coco_sentence` data events in both modes.

Streaming TTS branch shape:

```python
tts = self._streaming_tts_client
if not self._streaming_tts_started:
    await tts.start()
    self._streaming_tts_started = True
try:
    async for sentence in self._responder.stream_reply(...):
        async for audio in tts.synthesize_sentence(sentence):
            await self._audio_sink(audio)
finally:
    pass
```

Close the reusable client from an explicit `aclose()` method on the bridge agent:

```python
async def aclose(self) -> None:
    if self._streaming_tts_client is not None:
        with contextlib.suppress(Exception):
            await self._streaming_tts_client.finish()
```

- [ ] **Step 3: Implement the LiveKit audio sink**

In `backend/voice/entrypoint.py`, implement exactly one of these branches after checking the installed LiveKit API. Do not publish MiniMax MP3 bytes as PCM frames.

Branch A, preferred if this LiveKit version supports an encoded-audio publication API:

```python
async def livekit_audio_sink(encoded_audio: bytes) -> None:
    await encoded_audio_publisher.write(encoded_audio)
```

Acceptance for Branch A:

- the published track is audible in the browser
- the code path logs `voice_tts_sink=encoded_audio`
- tests assert `session.say` is not called in `minimax_ws` mode

Branch B, fallback if only `rtc.AudioSource` PCM publication is available and Task 4 Step 7 proved MiniMax accepts `audio_setting.format="pcm"`:

```python
from livekit import rtc

audio_source = rtc.AudioSource(sample_rate=32000, num_channels=1)
track = rtc.LocalAudioTrack.create_audio_track("coco-minimax", audio_source)
await room.local_participant.publish_track(track)

from dataclasses import dataclass

@dataclass(slots=True)
class PCMFrame:
    data: bytes
    sample_rate: int
    num_channels: int
    samples_per_channel: int


class PCMFrameChunker:
    def __init__(self, *, sample_rate: int = 32000, num_channels: int = 1) -> None:
        self._sample_rate = sample_rate
        self._num_channels = num_channels
        self._pending = b""

    def push(self, pcm: bytes) -> list[PCMFrame]:
        data = self._pending + pcm
        whole_len = len(data) - (len(data) % 2)
        self._pending = data[whole_len:]
        if whole_len == 0:
            return []
        chunk = data[:whole_len]
        return [
            PCMFrame(
                data=chunk,
                sample_rate=self._sample_rate,
                num_channels=self._num_channels,
                samples_per_channel=len(chunk) // 2 // self._num_channels,
            )
        ]


pcm_chunker = PCMFrameChunker(sample_rate=32000, num_channels=1)

async def livekit_audio_sink(raw_pcm: bytes) -> None:
    for pcm_frame in pcm_chunker.push(raw_pcm):
        frame = rtc.AudioFrame(
            data=pcm_frame.data,
            sample_rate=pcm_frame.sample_rate,
            num_channels=pcm_frame.num_channels,
            samples_per_channel=pcm_frame.samples_per_channel,
        )
        await audio_source.capture_frame(frame)
```

Acceptance for Branch B:

- MiniMax real provider test confirms `format="pcm"` succeeds.
- raw PCM bytes are passed to `rtc.AudioFrame`; no per-chunk MP3 decode exists.
- if provider only supports MP3 streaming, stop this branch and either use Branch A or add a separate stateful MP3 decoder design.
- log `voice_tts_sink=pcm_audio_source`

If neither branch can be implemented in the installed LiveKit version, implement an explicit failing sink and stop Task 7:

```python
async def livekit_audio_sink(_encoded_audio: bytes) -> None:
    raise NotImplementedError(
        "MiniMax WebSocket TTS is generating audio, but this LiveKit version has no wired audio sink"
    )
```

In that case, the task is not considered complete and the handoff must record the exact missing LiveKit API. Do not silently fall back to `session.say()` while claiming MiniMax WebSocket streaming success.

- [ ] **Step 4: Wire env flag**

Use:

```bash
VOICE_STREAMING_MODE=true
VOICE_STREAMING_TTS_MODE=minimax_ws
```

`entrypoint.py` should construct `StreamingVoiceBridgeAgent` with:

```python
streaming_tts_client=MiniMaxStreamingTTSClient(
    config=MiniMaxStreamingTTSConfig.from_env()
),
audio_sink=livekit_audio_sink,
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/voice/test_streaming_bridge_agent.py tests/voice/test_minimax_streaming_tts.py -q
```

Expected: PASS.

- [ ] **Step 6: Manual smoke test**

Expected evidence:

- `minimax_streaming_tts_start`
- `task_continue` is sent before full Coco reply is generated
- browser hears the first MiniMax WebSocket audio chunk before the full LLM reply completes
- no `session.say()` call in `minimax_ws` mode

- [ ] **Step 7: Review changed files**

```bash
git diff --stat backend/voice/streaming_bridge_agent.py backend/voice/entrypoint.py tests/voice/test_streaming_bridge_agent.py
```

---

### Task 8: True Streaming STT Input

**Files:**
- Modify: `backend/voice/plugins/xfyun_streaming_stt.py`
- Modify: `backend/voice/streaming_bridge_agent.py`
- Modify: `backend/voice/entrypoint.py`
- Test: `tests/voice/test_xfyun_streaming_stt.py`

- [ ] **Step 1: Add tests for dynamic transcript aggregation**

Extend `tests/voice/test_xfyun_streaming_stt.py`:

```python
from backend.voice.plugins.xfyun_streaming_stt import TranscriptAggregator


def test_transcript_aggregator_appends_partials() -> None:
    agg = TranscriptAggregator()

    assert agg.update(["我", "今天"], is_final=False) == "我今天"
    assert agg.update(["很", "难过"], is_final=True) == "我今天很难过"
    assert agg.final_text == "我今天很难过"


def test_transcript_aggregator_replaces_dynamic_correction_multi_slot_range() -> None:
    agg = TranscriptAggregator()

    assert agg.update(["我", "今天", "很", "烦"], is_final=False) == "我今天很烦"
    assert (
        agg.update(["现在", "很难过"], is_final=True, pgs="rpl", rg=[2, 4])
        == "我现在很难过"
    )
    assert agg.final_text == "我现在很难过"
```

- [ ] **Step 2: Implement aggregator**

Add to `backend/voice/plugins/xfyun_streaming_stt.py`:

```python
class TranscriptAggregator:
    def __init__(self) -> None:
        self._segments: list[str] = []
        self.final_text = ""

    def update(
        self,
        segments: list[str],
        *,
        is_final: bool,
        pgs: str | None = None,
        rg: list[int] | None = None,
    ) -> str:
        cleaned = [segment for segment in segments if segment]
        if pgs == "rpl":
            if not rg or len(rg) != 2:
                raise RuntimeError("Xfyun rpl event missing rg range")
            start = max(rg[0] - 1, 0)
            end = max(rg[1], start)
            self._segments[start:end] = cleaned
        elif pgs == "apd" or pgs is None:
            self._segments.extend(cleaned)
        else:
            raise RuntimeError(f"unknown Xfyun pgs mode: {pgs}")
        current = "".join(self._segments)
        if is_final:
            self.final_text = current
        return current
```

- [ ] **Step 3: Implement real WebSocket auth and frame upload**

Use Xfyun IAT (`wss://ws-api.xfyun.cn/v2/iat`) for this task. Do not switch to RTASR; RTASR uses a different URL, protocol, and response shape and would invalidate the parser tests above.

Extend `XfyunStreamingASRClient` so it:

- Builds authenticated URL from `XFYUN_APP_ID`, `XFYUN_API_KEY`, `XFYUN_API_SECRET`.
- Connects to Xfyun streaming endpoint.
- Sends first frame with business params and status `0`.
- Sends middle PCM frames with status `1`.
- Sends final empty/end frame with status `2`.
- Yields `XfyunTranscriptEvent` from receive loop.

Add this concrete auth URL helper:

```python
import base64
import hashlib
import hmac
from datetime import UTC, datetime
from email.utils import format_datetime
from urllib.parse import urlencode, urlparse


def build_xfyun_iat_url(
    *,
    base_url: str,
    api_key: str,
    api_secret: str,
    now: datetime | None = None,
) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc
    path = parsed.path or "/v2/iat"
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    date = format_datetime(timestamp, usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", '
        f'algorithm="hmac-sha256", '
        f'headers="host date request-line", '
        f'signature="{signature}"'
    )
    authorization = base64.b64encode(
        authorization_origin.encode("utf-8")
    ).decode("utf-8")
    return f"{base_url}?{urlencode({'authorization': authorization, 'date': date, 'host': host})}"
```

Add tests that freeze `now` and assert:

- the query string contains `authorization`, `date`, and `host`
- the decoded authorization contains `headers="host date request-line"`
- the path used in the signature is `/v2/iat`

Replace the disabled Task 5 client boundary with concrete methods that satisfy this interface:

```python
async def start(self) -> None:
    """Open the authenticated Xfyun websocket and send the first frame."""

async def send_pcm(self, pcm: bytes, *, status: int) -> None:
    """Send one base64-encoded PCM frame with Xfyun status 0, 1, or 2."""

async def events(self) -> AsyncIterator[XfyunTranscriptEvent]:
    """Yield parsed transcript events until Xfyun sends final status 2."""

async def close(self) -> None:
    """Close the websocket and release the receive task."""
```

- [ ] **Step 4: Wire partial events to browser inside the STT plugin**

First extend `backend/voice/plugins/_context.py` with a tiny latest-turn registry because STT partials are emitted before `on_user_turn_completed()`:

```python
_latest_voice_turn_ids: dict[str, str] = {}


def set_latest_voice_turn_id(session_id: str, turn_id: str) -> None:
    _latest_voice_turn_ids[session_id] = turn_id


def get_latest_voice_turn_id(session_id: str) -> str | None:
    return _latest_voice_turn_ids.get(session_id)
```

In `backend/voice/plugins/xfyun_streaming_stt.py`, generate one `turn_id` when the STT stream starts, set `voice_turn_ctx`, call `set_latest_voice_turn_id(session_id, turn_id)`, and publish:

```python
VoiceStreamEvent(
    type="user_partial",
    session_id=session_id,
    turn_id=turn_id,
    text=partial_text,
    is_final=False,
)
```

`StreamingVoiceBridgeAgent.on_user_turn_completed()` must reuse the STT-generated turn id:

```python
turn_id = (
    voice_turn_ctx.get()
    or get_latest_voice_turn_id(session_id)
    or uuid.uuid4().hex[:8]
)
```

This keeps `user_partial`, `user_final`, and `coco_sentence` on the same turn id.

and:

```python
VoiceStreamEvent(
    type="user_final",
    session_id=session_id,
    turn_id=turn_id,
    text=final_text,
    is_final=True,
)
```

- [ ] **Step 5: Inspect installed LiveKit STT interface**

Before writing the streaming plugin, capture the installed interface:

```bash
uv run python - <<'PY'
import inspect
from livekit.agents import stt

print("STTCapabilities", inspect.signature(stt.STTCapabilities))
print("RecognizeStream.__init__", inspect.signature(stt.RecognizeStream.__init__))
print(inspect.getsource(stt.RecognizeStream))
PY
```

Expected for the current local environment:

- `STTCapabilities` accepts `streaming`, `interim_results`, and `offline_recognize`
- `RecognizeStream` exposes the same input/output channel names used below

If the installed source differs, adapt `XfyunRecognizeStream` to that exact version before coding. Do not guess private attribute names.

- [ ] **Step 6: Write LiveKit STT plugin tests**

Extend `tests/voice/test_xfyun_streaming_stt.py` with a fake client and at least these red tests:

```python
import asyncio

import pytest
from livekit import rtc
from livekit.agents.stt import SpeechEventType

from backend.voice.plugins.xfyun_streaming_stt import (
    XfyunStreamingSTTPlugin,
    XfyunTranscriptEvent,
)


class _FakeStreamingClient:
    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self.sent_statuses: list[int] = []
        self.events_queue: asyncio.Queue[XfyunTranscriptEvent | None] = asyncio.Queue()

    async def start(self) -> None:
        self.started = True

    async def send_pcm(self, pcm: bytes, *, status: int) -> None:
        self.sent_statuses.append(status)

    async def events(self):
        while True:
            item = await self.events_queue.get()
            if item is None:
                return
            yield item

    async def close(self) -> None:
        self.closed = True


def _frame() -> rtc.AudioFrame:
    return rtc.AudioFrame(
        data=bytes(1600),
        sample_rate=16000,
        num_channels=1,
        samples_per_channel=800,
    )


async def _wait_until(predicate, *, timeout_s: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


def test_streaming_stt_capabilities() -> None:
    plugin = XfyunStreamingSTTPlugin(client_factory=_FakeStreamingClient)

    assert plugin.capabilities.streaming is True
    assert plugin.capabilities.interim_results is True


@pytest.mark.asyncio
async def test_streaming_stt_sends_first_frame_and_flush_status() -> None:
    client = _FakeStreamingClient()
    plugin = XfyunStreamingSTTPlugin(client_factory=lambda: client)
    stream = plugin.stream()

    stream.push_frame(_frame())
    stream.flush()
    await _wait_until(lambda: len(client.sent_statuses) >= 2)
    client.events_queue.put_nowait(None)
    await stream.aclose()

    assert client.started is True
    assert client.sent_statuses[:2] == [0, 2]
    assert client.closed is True


@pytest.mark.asyncio
async def test_streaming_stt_emits_interim_and_final_events() -> None:
    client = _FakeStreamingClient()
    plugin = XfyunStreamingSTTPlugin(client_factory=lambda: client)
    stream = plugin.stream()

    client.events_queue.put_nowait(
        XfyunTranscriptEvent(text="我今天", segments=["我", "今天"], is_final=False)
    )
    client.events_queue.put_nowait(
        XfyunTranscriptEvent(text="我今天很难过", segments=["很", "难过"], is_final=True)
    )
    client.events_queue.put_nowait(None)

    first = await stream.__anext__()
    second = await stream.__anext__()
    await stream.aclose()

    assert first.type == SpeechEventType.INTERIM_TRANSCRIPT
    assert first.alternatives[0].text == "我今天"
    assert second.type == SpeechEventType.FINAL_TRANSCRIPT
    assert second.alternatives[0].text == "我今天很难过"
```

- [ ] **Step 7: Implement `XfyunStreamingSTTPlugin` with the LiveKit streaming interface**

Add these class signatures to `backend/voice/plugins/xfyun_streaming_stt.py`:

```python
import asyncio
import contextlib
import inspect
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from livekit.agents.stt import (
    RecognizeStream,
    STT,
    STTCapabilities,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr

from backend.voice.plugins._context import (
    set_latest_voice_turn_id,
    voice_session_ctx,
    voice_turn_ctx,
)
from backend.voice.streaming_events import VoiceStreamEvent

VoiceEventPublisher = Callable[[VoiceStreamEvent], Awaitable[None]]


def _stt_capabilities() -> STTCapabilities:
    params = inspect.signature(STTCapabilities).parameters
    kwargs: dict[str, Any] = {
        "streaming": True,
        "interim_results": True,
    }
    if "offline_recognize" in params:
        kwargs["offline_recognize"] = False
    return STTCapabilities(**kwargs)


class XfyunStreamingSTTPlugin(STT):
    def __init__(
        self,
        *,
        client_factory: Callable[[], XfyunStreamingASRClient] | None = None,
        event_publisher: VoiceEventPublisher | None = None,
        language: str = "zh-cn",
        sample_rate: int = 16000,
    ) -> None:
        super().__init__(capabilities=_stt_capabilities())
        self._client_factory = client_factory or XfyunStreamingASRClient
        self._event_publisher = event_publisher
        self._language = language
        self._sample_rate = sample_rate

    @property
    def model(self) -> str:
        return "xfyun-iat-streaming"

    @property
    def provider(self) -> str:
        return "xfyun"

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> RecognizeStream:
        return XfyunRecognizeStream(
            stt=self,
            conn_options=conn_options,
            sample_rate=self._sample_rate,
            client=self._client_factory(),
            event_publisher=self._event_publisher,
            language=self._language,
        )


class XfyunRecognizeStream(RecognizeStream):
    def __init__(
        self,
        *,
        stt: STT,
        conn_options: APIConnectOptions,
        sample_rate: int,
        client: XfyunStreamingASRClient,
        event_publisher: VoiceEventPublisher | None,
        language: str,
    ) -> None:
        super().__init__(stt=stt, conn_options=conn_options, sample_rate=sample_rate)
        self._client = client
        self._event_publisher = event_publisher
        self._language = language
        self._aggregator = TranscriptAggregator()
        self._turn_id = uuid.uuid4().hex[:8]

    async def _run(self) -> None:
        session_id = voice_session_ctx.get() or "unknown"
        voice_turn_ctx.set(self._turn_id)
        set_latest_voice_turn_id(session_id, self._turn_id)
        await self._client.start()
        input_task = asyncio.create_task(self._send_audio_from_input())
        receive_task = asyncio.create_task(self._emit_transcripts())
        try:
            done, _pending = await asyncio.wait(
                {input_task, receive_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                task.result()
            if input_task in done and receive_task not in done:
                await receive_task
            elif receive_task in done and input_task not in done:
                input_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await input_task
        finally:
            for task in (input_task, receive_task):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            await self._client.close()

    async def _send_audio_from_input(self) -> None:
        status = 0
        async for item in self._input_ch:
            if isinstance(item, RecognizeStream._FlushSentinel):
                await self._client.send_pcm(b"", status=2)
                status = 0
                continue
            await self._client.send_pcm(bytes(item.data), status=status)
            status = 1

    async def _emit_transcripts(self) -> None:
        async for transcript in self._client.events():
            text = self._aggregator.update(
                transcript.segments,
                is_final=transcript.is_final,
                pgs=transcript.pgs,
                rg=transcript.rg,
            )
            speech_type = (
                SpeechEventType.FINAL_TRANSCRIPT
                if transcript.is_final
                else SpeechEventType.INTERIM_TRANSCRIPT
            )
            self._event_ch.send_nowait(
                SpeechEvent(
                    type=speech_type,
                    alternatives=[
                        SpeechData(
                            language=self._language,
                            text=text,
                            confidence=1.0 if text else 0.0,
                        )
                    ],
                )
            )
            if self._event_publisher is not None:
                await self._event_publisher(
                    VoiceStreamEvent(
                        type="user_final" if transcript.is_final else "user_partial",
                        session_id=voice_session_ctx.get() or "unknown",
                        turn_id=self._turn_id,
                        text=text,
                        is_final=transcript.is_final,
                    )
                )
```

- [ ] **Step 8: Replace StreamAdapter with one LiveKit STT owner**

Use option B: implement a custom LiveKit STT plugin backed by `XfyunStreamingASRClient`. Do not consume the room's audio tracks directly inside `StreamingVoiceBridgeAgent`, because `AgentSession` already owns microphone frame consumption when an STT plugin is configured.

Modify `backend/voice/entrypoint.py`:

```python
        streaming_enabled = os.environ.get("VOICE_STREAMING_MODE", "").lower() == "true"
        if streaming_enabled:
            async def voice_stream_event_publisher(event: VoiceStreamEvent) -> None:
                await publish_voice_event(ctx.room, event)

            stt_plugin = XfyunStreamingSTTPlugin(
                event_publisher=voice_stream_event_publisher,
            )
        else:
            vad = _silero.VAD.load(min_silence_duration=1.2)
            stt_plugin = _agent_stt.StreamAdapter(stt=XfyunSTTPlugin(), vad=vad)
```

Add imports in `backend/voice/entrypoint.py`:

```python
from backend.voice.livekit_data import publish_voice_event
from backend.voice.streaming_events import VoiceStreamEvent
from backend.voice.plugins.xfyun_streaming_stt import XfyunStreamingSTTPlugin
```

`XfyunStreamingSTTPlugin` is responsible for:

- receiving audio frames from LiveKit's STT stream interface
- sending PCM frames to Xfyun with status `0`, `1`, `2`
- emitting LiveKit interim/final speech events for `AgentSession`
- publishing `user_partial` and `user_final` browser data events

The bridge agent receives final transcript through `on_user_turn_completed()` exactly once. This avoids double-consuming audio and keeps partial transcript display inside the STT plugin boundary.

- [ ] **Step 9: Run tests**

Run:

```bash
uv run pytest tests/voice/test_xfyun_streaming_stt.py tests/voice/test_streaming_bridge_agent.py -q
```

Expected: PASS.

- [ ] **Step 10: Manual smoke test**

With `VOICE_STREAMING_MODE=true`, say a long sentence. Expected:

- Browser receives `user_partial` before the user stops speaking.
- Browser receives `user_final`.
- Coco starts LLM/TTS after final.

- [ ] **Step 11: Review changed files**

```bash
git diff --stat backend/voice/plugins/xfyun_streaming_stt.py backend/voice/streaming_bridge_agent.py backend/voice/entrypoint.py tests/voice/test_xfyun_streaming_stt.py
```

---

### Task 9: Frontend Streaming Transcript Display

**Files:**
- Modify: `web/lib/use-livekit-voice.ts`
- Modify: `web/components/voice/VoiceButton.tsx`
- Modify: `web/lib/voice-types.ts`

- [ ] **Step 1: Extend hook return type**

Modify `web/lib/use-livekit-voice.ts` return interface:

```ts
  userPartial: string;
  lastUserFinal: string;
  cocoPartial: string;
  cocoSentences: Array<{ id: string; text: string }>;
```

- [ ] **Step 2: Parse LiveKit data messages**

Inside the hook, add state:

```ts
  const [userPartial, setUserPartial] = useState("");
  const [lastUserFinal, setLastUserFinal] = useState("");
  const [cocoPartial, setCocoPartial] = useState("");
  const [cocoSentences, setCocoSentences] = useState<Array<{ id: string; text: string }>>([]);
```

Add handler:

```ts
    handle.room.on(RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
      if (topic !== "voice-stream") return;
      let event: VoiceStreamEvent;
      try {
        event = JSON.parse(new TextDecoder().decode(payload)) as VoiceStreamEvent;
      } catch {
        return;
      }
      if (event.type === "user_partial") setUserPartial(event.text);
      if (event.type === "user_final") {
        setLastUserFinal(event.text);
        setUserPartial("");
      }
      if (event.type === "coco_delta") setCocoPartial(event.text);
      if (event.type === "coco_sentence") {
        setCocoSentences((items) => [
          ...items.slice(-4),
          { id: crypto.randomUUID(), text: event.text },
        ]);
        setCocoPartial("");
      }
    });
```

- [ ] **Step 3: Render compact transcript**

Modify `web/components/voice/VoiceButton.tsx`:

```tsx
      {(userPartial || lastUserFinal || cocoPartial || cocoSentences.length > 0) && (
        <div className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-xs text-zinc-600">
          {userPartial && <p>你：{userPartial}</p>}
          {!userPartial && lastUserFinal && <p>你：{lastUserFinal}</p>}
          {cocoSentences.slice(-2).map((item) => (
            <p key={item.id}>Coco：{item.text}</p>
          ))}
          {cocoPartial && <p>Coco：{cocoPartial}</p>}
        </div>
      )}
```

- [ ] **Step 4: Run lint**

Run:

```bash
cd web
npm run lint
```

Expected: PASS.

- [ ] **Step 5: Review changed files**

```bash
git diff --stat web/lib/use-livekit-voice.ts web/components/voice/VoiceButton.tsx web/lib/voice-types.ts
```

---

### Task 10: Interruption And Turn Cancellation

**Files:**
- Modify: `backend/voice/streaming_bridge_agent.py`
- Modify: `backend/voice/livekit_data.py`
- Test: `tests/voice/test_streaming_bridge_agent.py`

- [ ] **Step 1: Write interruption test**

Extend `tests/voice/test_streaming_bridge_agent.py` with a cancellation-focused unit test:

```python
import contextlib


@pytest.mark.asyncio
async def test_streaming_bridge_cancels_previous_tts_on_new_turn() -> None:
    agent = StreamingVoiceBridgeAgent(
        instructions="test",
        responder=_Responder(),
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
```

- [ ] **Step 2: Implement turn task holder**

Add to `StreamingVoiceBridgeAgent.__init__`:

```python
        self.current_turn_id: str | None = None
        self.current_turn_task: asyncio.Task[Any] | None = None
```

Add method:

```python
    def replace_turn_task(self, turn_id: str, task: asyncio.Task[Any]) -> None:
        if self.current_turn_task is not None and not self.current_turn_task.done():
            self.current_turn_task.cancel()
        self.current_turn_id = turn_id
        self.current_turn_task = task
```

Use this method at the point where the bridge starts a new user turn so every new turn owns exactly one active response/TTS task.

- [ ] **Step 3: Publish interruption event**

When cancelling an active turn, publish:

```python
VoiceStreamEvent(
    type="turn_interrupted",
    session_id=session_id,
    turn_id=old_turn_id,
    text="",
    is_final=True,
)
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/voice/test_streaming_bridge_agent.py -q
```

Expected: PASS.

- [ ] **Step 5: Manual smoke**

Start Coco speaking, then speak over it. Expected:

- Current TTS stops or is no longer queued.
- New user partial appears.
- New Coco turn begins.

- [ ] **Step 6: Review changed files**

```bash
git diff --stat backend/voice/streaming_bridge_agent.py backend/voice/livekit_data.py tests/voice/test_streaming_bridge_agent.py
```

---

### Task 11: E2E Metrics And Evolve Harness

**Files:**
- Modify: `.evolve/voice_eval.py`
- Create: `.evolve/voice_streaming_expected.md`
- Modify: `docs/voice-2.0-handoff.md` or create new handoff doc after validation

- [ ] **Step 1: Add streaming metrics**

In `.evolve/voice_eval.py`, add metrics:

```python
time_to_user_partial_ms
time_to_user_final_ms
time_to_first_coco_sentence_ms
time_to_first_audio_ms
barge_in_success
streaming_mode_enabled
tts_mode
voice_tts_sink
```

- [ ] **Step 2: Add expected thresholds**

Create `.evolve/voice_streaming_expected.md`:

```markdown
# Voice Streaming Expected Path

- `streaming_mode_enabled=true`
- `time_to_user_partial_ms <= 800`
- `time_to_user_final_ms <= 2500`
- `time_to_first_coco_sentence_ms <= 1500` after final transcript
- `time_to_first_audio_ms <= 1800` after final transcript
- `tts_mode=minimax_ws` for true streaming TTS validation runs
- `voice_tts_sink` is `encoded_audio` or `pcm_audio_source`, not `session_say`
- `barge_in_success=true` when user interrupts Coco speech
- no `AGENT_AUDIO_TIMEOUT`
- at least two consecutive turns produce audible Coco replies
```

- [ ] **Step 3: Run automated checks**

Run the existing test set:

```bash
uv run pytest tests/voice tests/test_coordinator.py -q
cd web && npm run lint
```

Expected: PASS.

- [ ] **Step 4: Run real LiveKit smoke**

Start services:

```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv('/home/yizhuo_wang/code1/moodcoco/.env', override=False); import uvicorn; uvicorn.run('backend.api:app', host='0.0.0.0', port=8002)"
```

```bash
cd web
NEXT_PUBLIC_API_BASE=http://localhost:8002 npm run dev -- --hostname 0.0.0.0 --port 3001
```

```bash
VOICE_STREAMING_MODE=true uv run python -c "import os; from dotenv import load_dotenv; load_dotenv('/home/yizhuo_wang/code1/moodcoco/.env', override=False); os.environ.setdefault('DOUBAO_API_KEY', os.environ.get('OPENAI_API_KEY','')); os.environ.setdefault('DOUBAO_BASE_URL', os.environ.get('OPENAI_BASE_URL','')); os.environ.setdefault('DOUBAO_MODEL', os.environ.get('OPENAI_FAST_MODEL') or os.environ.get('OPENAI_MODEL','')); from backend.voice.entrypoint import voice_entrypoint; from livekit.agents import cli, WorkerOptions; cli.run_app(WorkerOptions(entrypoint_fnc=voice_entrypoint, agent_name='moodcoco-coco'))" start
```

Expected:

- Web at `http://localhost:3001`
- LiveKit worker logs `voice_session_started`
- User sees partial transcript
- User hears first Coco sentence before full reply completes

- [ ] **Step 5: Write validation handoff**

Create `docs/voice-true-streaming-handoff.md` with:

```markdown
# Voice True Streaming Handoff

## What Changed
- Streaming ASR:
- Streaming LLM:
- Streaming TTS:
- Frontend transcript:

## Commands
- Backend:
- Web:
- Worker:

## Evidence
- pytest:
- npm lint:
- e2e room:
- time_to_user_partial_ms:
- time_to_first_audio_ms:
- tts_mode:
- voice_tts_sink:
- barge_in_success:

## Remaining Risks
- Provider WebSocket instability:
- Echo cancellation:
- Slow background carryover:
```

- [ ] **Step 6: Review changed files**

```bash
git diff --stat .evolve/voice_eval.py .evolve/voice_streaming_expected.md docs/voice-true-streaming-handoff.md
```

---

## Risks And Mitigations

- **Provider protocol mismatch:** MiniMax and Xfyun WebSocket payload formats can drift. Mitigation: keep protocol parsing isolated in provider files and test parsing without network.
- **LiveKit Python audio publication mismatch:** The current repo version may not expose an encoded-audio sink for MiniMax MP3 chunks. Mitigation: Task 7 requires an explicit encoded-audio branch, decoded-PCM branch, or a hard `NotImplementedError`; `session.say()` is not accepted as MiniMax WebSocket evidence.
- **Echo and interruption false positives:** Streaming ASR may hear Coco's own TTS. Mitigation: add `speaking`/`cooldown` state and test barge-in manually.
- **Pydantic-ai tool path conflict:** Voice streaming must not depend on Fast tool calls. Mitigation: `VoiceStreamingResponder` is voice-only; text/UI path remains unchanged.
- **Latency still high from model provider:** If token first-byte exceeds target, switch `DOUBAO_MODEL`/`OPENAI_FAST_MODEL` before changing app architecture.

---

## Verification Checklist

- [ ] `uv run pytest tests/voice -q` passes.
- [ ] `uv run pytest tests/test_coordinator.py -q` passes.
- [ ] `cd web && npm run lint` passes.
- [ ] `VOICE_STREAMING_MODE=false` keeps current batch path working.
- [ ] `VOICE_STREAMING_MODE=true` enables streaming logs and browser transcript.
- [ ] User hears at least two consecutive Coco turns.
- [ ] E2E evidence is written to `docs/voice-true-streaming-handoff.md`.
