# Voice Context Intelligence Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the current Moodcoco voice demo so it is stable for manual Web use, remembers short-term voice context, avoids voice-room cross-talk, and makes LLM latency measurable before optimizing it.

**Architecture:** Keep the existing true-streaming voice path: Web mic -> LiveKit -> Xfyun streaming STT -> `VoiceStreamingResponder` -> MiniMax WebSocket TTS -> LiveKit audio. Add an in-memory per-room voice context store for short-term history and committed carryover, and keep background Slow/carryover work non-blocking so the first spoken response remains on the voice fast path.

**Tech Stack:** Python 3.12, FastAPI, LiveKit Agents, LiveKit JS client, Xfyun streaming STT, MiniMax WS TTS, OpenAI-compatible streaming chat, Next.js, pytest, ESLint.

---

## Current Baseline

- True streaming STT/TTS is already working in e2e.
- Measured STT final latency after endpoint is fast: about 130-173 ms.
- Current major latency bottleneck is `user_final -> first_coco_sentence`, recently around 5-8 s.
- Current intelligence issue is that `VoiceStreamingResponder` mostly sees the current utterance plus a compact voice prompt, so it feels weaker than the text Fast/Slow path.
- Current manual Web issue is room/track isolation: fixed-room use can leave multiple agents in one room, and the frontend must never attach non-agent remote audio as Coco audio.

## Defaults And Decisions

- `room_name` is the voice context key, not `session_id`.
- Default Web token creation generates a fresh room: `moodcoco-voice-{safe_session_id}-{uuid8}`.
- v1 voice context is process-local memory only. It does not survive API/worker restart.
- Keep one active agent per generated voice room. Do not reuse `moodcoco-voice` for Web manual testing unless explicitly requested.
- Do not put full Fast/Slow execution on the first-sentence blocking path.
- Do not use two different LLMs for first sentence vs later sentences in the first implementation. Use one voice streaming model until prompt/context behavior is stable.
- Carryover is versioned and non-blocking. A turn reads only the latest committed carryover available when the turn starts.
- Add feature flags so this work can be disabled without reverting code:
  - `VOICE_CONTEXT_ENABLED=true` enables prompt context injection.
  - `VOICE_CARRYOVER_ENABLED=true` enables background carryover generation.
  - `VOICE_AUTO_DISPATCH_AGENT=true` keeps Web token creation dispatching the voice agent by default.
  - `VOICE_CARRYOVER_TIMEOUT_S=3.0` controls the background carryover timeout.

## Task 1: Stabilize Web Voice Room Lifecycle

**Files:**
- Modify: `backend/api.py`
- Modify: `web/lib/livekit.ts`
- Modify: `web/lib/use-livekit-voice.ts`
- Test: `tests/voice/test_voice_entrypoint.py`

- [ ] **Step 1: Verify token API default room behavior test exists**

Run:

```bash
uv run pytest tests/voice/test_voice_entrypoint.py::test_voice_token_default_room_name -q
```

Expected:

```text
1 passed
```

The test must assert that an omitted `room_name` returns a fresh room whose value starts with `moodcoco-voice-web-demo-`, and that the JWT grant uses the exact same room.

- [ ] **Step 2: Verify token API dispatch behavior test exists**

Run:

```bash
uv run pytest tests/voice/test_voice_entrypoint.py::test_voice_token_dispatches_agent_to_same_room tests/voice/test_voice_entrypoint.py::test_voice_token_does_not_dispatch_browser_listener -q
```

Expected:

```text
3 passed
```

The dispatch test must monkeypatch `backend.api._dispatch_voice_agent` and assert it receives the generated or requested room and `moodcoco-coco`. The listener test must assert `session_id="browser-listener"` does not dispatch.

- [ ] **Step 3: Ensure frontend only attaches agent audio**

In `web/lib/livekit.ts`, expose:

```ts
export function isAgentParticipant(participant: RemoteParticipant | undefined): boolean {
  return participant?.identity.startsWith("agent-") === true;
}
```

In `web/lib/use-livekit-voice.ts`, check this before `attachAgentAudio(track)`. Non-agent remote audio tracks must be logged and ignored.

- [ ] **Step 4: Ensure click cannot create repeated dispatches**

In `web/lib/use-livekit-voice.ts`, transition to `processing` immediately after the idle-state guard and before token fetch:

```ts
transitionTo("processing", "token_fetching");
```

On token or room connection failure, transition back to `idle` before setting the visible error.

- [ ] **Step 5: Handle dispatch success but agent never joins**

The frontend must not wait forever in an empty room after a successful token response. Add a bounded wait for an agent participant or agent audio track after room connection.

Acceptance:

- if no agent joins within the existing audio/agent timeout window, transition back to `idle`;
- surface `AGENT_AUDIO_TIMEOUT` or a more specific `AGENT_JOIN_TIMEOUT`;
- log an event with `room_name`, `session_id`, and timeout duration;
- a second click after timeout must request a new fresh room, not reuse the abandoned room.

- [ ] **Step 6: Verify frontend checks**

Run:

```bash
cd web && npm run lint
```

Expected:

```text
web@0.1.0 lint
eslint
```

No ESLint errors.

## Task 2: Add Per-Room Voice Context Store

**Files:**
- Create: `backend/voice/voice_context.py`
- Test: `tests/voice/test_voice_context.py`

- [ ] **Step 1: Write tests for short-term history and budget trimming**

Create `tests/voice/test_voice_context.py` with tests covering:

```python
from backend.voice.voice_context import VoiceCarryover, VoiceContextStore, VoiceMessage


def test_voice_context_keeps_recent_messages() -> None:
    store = VoiceContextStore(max_messages=4, max_context_chars=1000)
    for index in range(6):
        store.append_message(
            "room-a",
            VoiceMessage(role="user" if index % 2 == 0 else "coco", text=f"msg-{index}"),
        )

    snapshot = store.snapshot("room-a")

    assert [item.text for item in snapshot.messages] == ["msg-2", "msg-3", "msg-4", "msg-5"]


def test_voice_context_formats_recent_history_with_budget() -> None:
    store = VoiceContextStore(max_messages=8, max_context_chars=30)
    store.append_message("room-a", VoiceMessage(role="user", text="我和妈妈吵架了，特别委屈"))
    store.append_message("room-a", VoiceMessage(role="coco", text="你觉得她没有看见你的努力。"))

    text = store.format_for_prompt("room-a")

    assert len(text) <= 30
    assert "妈妈" in text or "努力" in text


def test_voice_context_preserves_carryover_when_trimming() -> None:
    store = VoiceContextStore(max_messages=8, max_context_chars=64)
    store.commit_carryover(
        "room-a",
        VoiceCarryover(source_turn_seq=1, text="用户状态：很委屈\n关键事实：妈妈翻聊天记录"),
    )
    store.append_message("room-a", VoiceMessage(role="user", text="这是一条很长很长的补充内容" * 5))

    text = store.format_for_prompt("room-a")

    assert len(text) <= 64
    assert "用户状态" in text
    assert "关键事实" in text
```

- [ ] **Step 2: Run tests and confirm red if file is absent**

Run:

```bash
uv run pytest tests/voice/test_voice_context.py -q
```

Expected before implementation:

```text
FAILED
```

- [ ] **Step 3: Implement the store**

`backend/voice/voice_context.py` must provide:

```python
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock
from typing import Literal

Role = Literal["user", "coco"]


@dataclass(frozen=True, slots=True)
class VoiceMessage:
    role: Role
    text: str


@dataclass(frozen=True, slots=True)
class VoiceCarryover:
    source_turn_seq: int
    text: str


@dataclass(frozen=True, slots=True)
class VoiceContextSnapshot:
    messages: tuple[VoiceMessage, ...]
    carryover: VoiceCarryover | None


class VoiceContextStore:
    def __init__(self, *, max_messages: int = 8, max_context_chars: int = 1200) -> None:
        self._max_messages = max_messages
        self._max_context_chars = max_context_chars
        self._messages: dict[str, deque[VoiceMessage]] = {}
        self._carryover: dict[str, VoiceCarryover] = {}
        self._turn_seq: dict[str, int] = {}
        self._lock = RLock()

    def next_turn_seq(self, room_name: str) -> int:
        with self._lock:
            value = self._turn_seq.get(room_name, 0) + 1
            self._turn_seq[room_name] = value
            return value

    def append_message(self, room_name: str, message: VoiceMessage) -> None:
        text = message.text.strip()
        if not text:
            return
        with self._lock:
            items = self._messages.setdefault(room_name, deque(maxlen=self._max_messages))
            items.append(VoiceMessage(role=message.role, text=text))

    def commit_carryover(self, room_name: str, carryover: VoiceCarryover) -> None:
        text = carryover.text.strip()
        if not text:
            return
        with self._lock:
            current = self._carryover.get(room_name)
            if current is None or carryover.source_turn_seq > current.source_turn_seq:
                self._carryover[room_name] = VoiceCarryover(
                    source_turn_seq=carryover.source_turn_seq,
                    text=text,
                )

    def snapshot(self, room_name: str) -> VoiceContextSnapshot:
        with self._lock:
            return VoiceContextSnapshot(
                messages=tuple(self._messages.get(room_name, ())),
                carryover=self._carryover.get(room_name),
            )

    def format_for_prompt(self, room_name: str) -> str:
        snapshot = self.snapshot(room_name)
        lines: list[str] = []
        remaining = self._max_context_chars

        if snapshot.carryover is not None:
            carryover = "上一轮状态：\n" + snapshot.carryover.text
            if len(carryover) >= remaining:
                return carryover[:remaining]
            lines.append(carryover)
            remaining -= len(carryover) + 1

        selected_messages: list[str] = []
        for message in reversed(snapshot.messages):
            speaker = "用户" if message.role == "user" else "可可"
            line = f"{speaker}：{message.text}"
            cost = len(line) + (1 if lines or selected_messages else 0)
            if cost > remaining:
                continue
            selected_messages.append(line)
            remaining -= cost

        lines.extend(reversed(selected_messages))
        return "\n".join(lines)
```

- [ ] **Step 4: Run context tests**

Run:

```bash
uv run pytest tests/voice/test_voice_context.py -q
```

Expected:

```text
2 passed
```

## Task 3: Inject Context Into VoiceStreamingResponder

**Files:**
- Modify: `backend/voice/streaming_responder.py`
- Modify: `backend/voice/streaming_bridge_agent.py`
- Test: `tests/voice/test_streaming_responder.py`
- Test: `tests/voice/test_streaming_bridge_agent.py`

- [ ] **Step 1: Add responder test for voice context**

Add a test asserting the OpenAI-compatible request contains a compact `## 近期语音上下文` block when `voice_context` is passed.

The expected request messages must include:

```text
## 近期语音上下文
用户：我和妈妈吵架了
可可：你觉得她没有看见你的努力。
```

- [ ] **Step 2: Extend responder input**

Change `VoiceStreamingResponder.stream_reply(...)` to accept:

```python
voice_context: str = ""
```

Append it inside `_format_context` after carryover-related context and before the current user message. If `voice_context.strip()` is empty, omit the section.

- [ ] **Step 3: Write bridge test for storing user and Coco messages**

In `tests/voice/test_streaming_bridge_agent.py`, assert:

- `user_final` text is appended as `role="user"`.
- Each emitted Coco sentence is appended as `role="coco"`.
- The next turn's responder receives formatted context.

Use a fake context store rather than real LiveKit.

- [ ] **Step 4: Wire context store into streaming bridge**

In `backend/voice/streaming_bridge_agent.py`, use `room_name` or `voice_session_ctx` as the context key.

For each user turn:

1. Get `turn_seq = store.next_turn_seq(room_name)`.
2. Append `VoiceMessage(role="user", text=user_text)` immediately after final transcript.
3. Pass `store.format_for_prompt(room_name)` as `voice_context`.
4. Append each yielded Coco sentence as soon as it is yielded from the responder, before sending it to TTS. This lets a fast next user turn see Coco's intended reply even if TTS playback is still catching up. If TTS later fails, keep the stored Coco sentence and log the TTS error separately.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/voice/test_voice_context.py tests/voice/test_streaming_responder.py tests/voice/test_streaming_bridge_agent.py -q
```

Expected: all selected tests pass.

## Task 4: Add Versioned Non-Blocking Carryover

**Files:**
- Modify: `backend/voice/voice_context.py`
- Modify: `backend/voice/streaming_bridge_agent.py`
- Test: `tests/voice/test_voice_context.py`
- Test: `tests/voice/test_streaming_bridge_agent.py`

- [ ] **Step 1: Add carryover race and prompt-shape tests**

Add tests that prove:

- Carryover from turn 1 can be committed after turn 2 starts and will not block turn 2.
- Carryover from older turn cannot overwrite newer committed carryover.
- The carryover prompt/output shape contains these four headings: `用户状态：`, `关键事实：`, `下一轮建议：`, `避免重复：`.

Expected assertions:

```python
store.commit_carryover("room-a", VoiceCarryover(source_turn_seq=2, text="new"))
store.commit_carryover("room-a", VoiceCarryover(source_turn_seq=1, text="old"))
assert store.snapshot("room-a").carryover.text == "new"
```

- [ ] **Step 2: Implement background carryover task**

In the bridge, after starting the main voice reply, schedule a background task that creates a short carryover from:

- current user text
- emitted Coco sentence text
- prior snapshot carryover

The task must:

- have a timeout from `VOICE_CARRYOVER_TIMEOUT_S`, default `3.0`;
- suppress exceptions after logging;
- commit only with the source `turn_seq`;
- never be awaited by the first-sentence path.

Use explicit async timeout handling:

```python
async def _run_carryover_with_timeout(room_name: str, turn_seq: int, payload: CarryoverPayload) -> None:
    try:
        text = await asyncio.wait_for(
            generate_voice_carryover(payload),
            timeout=settings.voice_carryover_timeout_s,
        )
    except asyncio.TimeoutError:
        logger.warning("voice_carryover_timeout", extra={"room_name": room_name, "turn_seq": turn_seq})
        return
    except Exception:
        logger.exception("voice_carryover_failed", extra={"room_name": room_name, "turn_seq": turn_seq})
        return

    store.commit_carryover(room_name, VoiceCarryover(source_turn_seq=turn_seq, text=text))

task = asyncio.create_task(_run_carryover_with_timeout(room_name, turn_seq, payload))
self._background_tasks.add(task)
task.add_done_callback(self._background_tasks.discard)
```

- [ ] **Step 3: Keep carryover simple for v1**

Use the existing OpenAI-compatible voice client or the configured voice model. The output must be plain text with this format:

```text
用户状态：...
关键事实：...
下一轮建议：...
避免重复：...
```

Do not call tools or the full PydanticAI Fast/Slow agents in this task.

- [ ] **Step 4: Verify no blocking regression**

Run the focused bridge tests and then one e2e. In e2e, compare:

- `user_final -> first_coco_sentence`
- `voice_llm_first_token`
- `voice_llm_first_sentence`

Acceptance for this task: context/carryover enabled must not add more than 500 ms to `user_final -> first_coco_sentence` versus the most recent no-context baseline.

## Task 5: Add LLM And TTS Latency Instrumentation

**Files:**
- Modify: `backend/voice/streaming_responder.py`
- Modify: `backend/voice/streaming_bridge_agent.py`
- Modify: `.evolve/voice_eval.py`
- Test: `tests/test_voice_eval_streaming.py`

- [ ] **Step 1: Add evaluator test**

Add log fixtures for:

- `voice_llm_request_started`
- `voice_llm_first_token`
- `voice_llm_first_sentence`
- `voice_streaming_tts_first_audio`

Assert the evaluator reports:

- `llm_request_to_first_token_ms`
- `llm_first_token_to_first_sentence_ms`
- `llm_first_sentence_to_first_audio_ms`
- `user_final_to_first_audio_ms`

- [ ] **Step 2: Emit LLM timestamps**

In responder/bridge code:

- log `voice_llm_request_started` immediately before `client.chat.completions.create`;
- log `voice_llm_first_token` on the first non-empty token;
- log `voice_llm_first_sentence` when the first sentence is yielded.

Include `session_id`, `turn_id`, and `model` in every event.

- [ ] **Step 3: Extend evaluator**

Update `.evolve/voice_eval.py` to compute latency from the new events. Keep the existing STT metrics, especially `stt_endpoint_to_user_final_ms`.

- [ ] **Step 4: Verify focused tests**

Run:

```bash
uv run pytest tests/test_voice_eval_streaming.py tests/voice/test_streaming_responder.py -q
```

Expected: all selected tests pass.

## Task 6: Tune Sentence Chunking Without Residual Fragments

**Files:**
- Modify: `backend/voice/streaming_text.py`
- Test: `tests/voice/test_streaming_text.py`

- [ ] **Step 1: Add chunker tests**

Add tests for these cases:

```python
def test_chunker_prefers_chinese_punctuation():
    chunker = SentenceChunker(max_chars=24)
    assert chunker.push("我听见你真的很委屈，") == ["我听见你真的很委屈，"]


def test_chunker_does_not_emit_short_residual_phrase():
    chunker = SentenceChunker(max_chars=12)
    assert chunker.push("我听到你") == []
```

- [ ] **Step 2: Implement conservative early chunking**

Rules:

- yield immediately on `，。？！；`;
- if no punctuation appears by 18-24 Chinese characters, allow a chunk only at a phrase boundary; default to `soft_max_chars=18` and `hard_max_chars=24`;
- do not emit fragments shorter than 8 characters unless they end with punctuation;
- flush at stream end as before.

This task intentionally trades a small amount of first-sentence latency for fewer broken fragments. Use Task 5 metrics to verify the tradeoff: `llm_first_token_to_first_sentence_ms.p50` must not increase by more than 300 ms versus the pre-Task-6 baseline. If it does, keep punctuation-first behavior but lower the phrase-boundary threshold rather than shipping a slower default.

- [ ] **Step 3: Verify chunker tests**

Run:

```bash
uv run pytest tests/voice/test_streaming_text.py -q
```

Expected: all selected tests pass.

## Task 7: E2E And Manual Acceptance

**Files:**
- Modify: `.evolve/voice_eval.py`
- Optional doc update: `docs/voice-context-intelligence-handoff.md`

- [ ] **Step 1: Run focused unit suite**

Run:

```bash
uv run pytest \
  tests/voice/test_voice_entrypoint.py \
  tests/voice/test_voice_context.py \
  tests/voice/test_streaming_responder.py \
  tests/voice/test_streaming_bridge_agent.py \
  tests/voice/test_streaming_text.py \
  tests/test_voice_eval_streaming.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run real voice e2e**

Run:

```bash
VOICE_STREAMING_MODE=true \
VOICE_STREAMING_STT_MODE=true \
VOICE_STREAMING_TTS_MODE=minimax_ws \
E2E_DURATION_S=120 \
PERSONA_MAX_TURNS=3 \
bash .evolve/run_e2e.sh
```

Then run:

```bash
python .evolve/voice_eval.py --json
```

Acceptance:

- `error_count == 0`
- `user_final >= 3`
- `voice_streaming_tts_first_audio >= 3`
- `stt_endpoint_to_user_final_ms.p50 < 300`
- context/carryover enabled does not add more than 500 ms to the previous `user_final -> first_coco_sentence` baseline
- `context_recall_pass == true` for a scripted two-turn recall check:
  - turn 1: `我和妈妈吵架了，她翻我聊天记录，还说我不懂事。`
  - turn 2: `你还记得我刚才最委屈的点是什么吗？`
  - Coco's reply must include at least one fact keyword from `妈妈`, `翻聊天记录`, `不懂事` and one emotion/validation keyword from `委屈`, `难受`, `生气`, `不被尊重`.

- [ ] **Step 3: Manual Web check**

Start:

```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv('.env', override=False); import uvicorn; uvicorn.run('backend.api:app', host='0.0.0.0', port=8002)"
```

```bash
VOICE_STREAMING_MODE=true VOICE_STREAMING_STT_MODE=true VOICE_STREAMING_TTS_MODE=minimax_ws uv run --group voice python -c "import os; from dotenv import load_dotenv; load_dotenv('.env', override=False); from backend.voice.entrypoint import voice_entrypoint; from livekit.agents import cli, WorkerOptions; cli.run_app(WorkerOptions(entrypoint_fnc=voice_entrypoint, agent_name='moodcoco-coco'))" start
```

```bash
cd web && NEXT_PUBLIC_API_BASE=http://localhost:8002 npm run dev -- --hostname 0.0.0.0 --port 3000
```

Manual acceptance:

- refresh `http://localhost:3000`;
- click voice once;
- one token request creates one fresh room;
- one agent job joins that room;
- speaking produces `voice_streaming_stt_speech_started`;
- Coco can refer to a fact from the previous voice turn;
- user does not hear local mic echo.

## Out Of Scope For This Plan

- Redis or persistent cross-session voice memory.
- Full Fast/Slow PydanticAI execution on the blocking first-sentence path.
- Two-model fast-first plus regular-followup generation.
- Full root-cause fix for MiniMax/persona repeated-word artifacts. This remains a separate diagnostic task unless raw `coco_sentence` logs prove the repetition starts in the responder/chunker.
