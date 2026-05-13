# Voice 2.0 Runtime Evaluation Handoff

**Branch**: `evolve/livekit-fast-slow`
**Date**: 2026-04-30
**Status**: 真实语音链路 ✅ 跑通 / 延迟指标 ❌ 未达标 / 聪明程度 ⚠️ 中等偏可用

## TL;DR

- ✅ **链路跑通**：LiveKit Cloud + Xfyun STT + pydantic-ai Fast/Slow + MiniMax TTS + persona 自动对话可运行，最后一轮无 Fast/Slow failed。
- ✅ **F-2.0c 修复已落地**：P0 VAD、P1 carryover skills cap、P2 Fast/Slow model split、portable e2e runner、Fast voice `ai_message` 后停止 loop。
- ❌ **当前最大问题是语音延迟**：最新 eval `turn_to_fast_tool p50=21896ms / p90=24817ms`，未达到可用线 `p50<=8000ms / p90<=15000ms`。
- ⚠️ **聪明程度未达 pass 线**：回复能接住情绪，但推进弱，最新人工估分约 `3.65/5`，目标 `>=3.8/5`。
- 📝 **接手优先级**：先优化 Fast 首次 tool latency，再调聪明程度；STT/TTS 不是当前主瓶颈。

## What Changed Since `voice-2.0-handoff.md`

| Commit | Status | What changed |
|---|---|---|
| `604666c` | done | 修 P0/P1/P2；e2e 脚本便携化；Fast voice `ai_message` 已发声后不 fallback；全量 tests 95/95 |
| `88aff86` | done | 新增 `.evolve/voice_eval.md` 和 `.evolve/voice_eval.py`，把延迟/聪明程度标准固化为可重复评估 |

## Current Pipeline

```text
persona audio
  -> LiveKit room
  -> Silero VAD(min_silence_duration=1.2)
  -> Xfyun STT final transcript
  -> VoiceBridgeAgent.on_user_turn_completed
      |-> Fast agent: first ai_message publishes TTS, then stops voice loop
      |-> Slow agent: runs in background, mutates next-turn Fast deps
  -> MiniMax TTS
  -> persona listens, transcribes Coco reply, generates next user line
```

Important runtime details:
- Fast uses `create_fast_model()`.
- Slow uses `create_slow_model()`.
- `carryover_inject` is capped to 3.
- `carryover_skills` is capped to 2.
- `.evolve/run_e2e.sh` creates a unique room per run and skips local `livekit-server` when `LIVEKIT_URL` is remote.

## Evaluation Standard

Source of truth:
- `.evolve/voice_eval.md`
- `.evolve/voice_eval.py`

### 1. 语音延迟

Primary metric: `turn_to_fast_tool_ms`, measured from `on_user_turn_completed` entry to first `fast_tool_call`.

Pass line:
- `registered_worker >= 1`
- `received_job_request >= 1`
- `voice_session_started >= 1`
- `stt_transcript_final >= 3`
- persona hears Coco replies `>= 3`
- `fast_agent_run_failed = 0`
- `slow_agent_run_failed = 0`
- `turn_to_fast_tool p50 <= 8000ms`
- `turn_to_fast_tool p90 <= 15000ms`

Tiering:
- 可用线：p50 <= 8000ms, p90 <= 15000ms
- 体验线：p50 <= 5000ms, p90 <= 10000ms
- 优秀线：p50 <= 3000ms, p90 <= 6000ms

### 2. 聪明程度

每条 Coco 回复按 5 个维度各 1-5 分：
- 承接情绪
- 抓重点
- 推进对话
- 安全边界
- 跨轮记忆

Pass line:
- 平均分 >= 3.8/5
- 没有单条回复低于 3.0
- 没有明显空泛 fallback 作为主回复
- 至少 2 次体现跨轮承接，或 `cross_turn_carryover >= 2`

## Latest Real E2E Result

Command:

```bash
bash .evolve/run_e2e.sh
python .evolve/voice_eval.py --json
```

Room:

```text
moodcoco-voice-1777536203
```

### Counts

| Metric | Value |
|---|---:|
| registered_worker | 1 |
| received_job_request | 1 |
| voice_session_started | 1 |
| stt_transcript_final | 3 |
| turn_hook | 3 |
| fast_agent_run_started | 3 |
| fast_agent_run_completed | 2 |
| fast_agent_run_failed | 0 |
| slow_agent_run_started | 3 |
| slow_agent_run_completed | 1 |
| slow_agent_run_failed | 0 |
| cross_turn_carryover | 2 |
| minimax_tts_synthesize_done | 3 |
| fast_tool_call | 3 |
| completed_after_voice_ai_message | 2 |
| persona heard Coco replies | 2 |

### Latency

| Metric | Count | Min | P50 | P90 | Max |
|---|---:|---:|---:|---:|---:|
| turn_to_fast_tool | 2 | 18974 | 21896 | 24817 | 24817 |
| stt_transcript_final | 3 | 2306 | 2306 | 3108 | 3108 |
| fast_tool_call | 3 | 0 | 6470 | 9504 | 9504 |
| fast_agent_run_completed | 2 | 24819 | 28568 | 32316 | 32316 |
| slow_agent_run_completed | 1 | 85102 | 85102 | 85102 | 85102 |
| minimax_tts_synthesize_done | 3 | 1845 | 2620 | 3244 | 3244 |

Latency verdict:

```text
FAIL: turn_to_fast_tool p50=21896ms / p90=24817ms
Target: p50<=8000ms / p90<=15000ms
```

### Persona Heard Coco

1. `委屈的时候，心里像堵了团棉花，对不对？`
2. `被打断的时候，话堵在喉咙里，心里是不是又酸又堵？`

### User STT Finals

1. `可可，我和我妈昨天大吵了一架，我感觉特别委屈。`
2. `他连话都不让我说完，上来就劈头盖脸骂我一顿。`
3. `他还嫌我只会哭，说我纯属就是没事找事。`

## Smartness Manual Score

| # | Reply | Emotion | Focus | Progress | Safety | Memory | Avg | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | 委屈的时候，心里像堵了团棉花，对不对？ | 4 | 3 | 3 | 5 | 2 | 3.4 | 情绪承接可以，但泛化，没有推进到事件细节 |
| 2 | 被打断的时候，话堵在喉咙里，心里是不是又酸又堵？ | 4 | 4 | 3 | 5 | 3.5 | 3.9 | 抓住了“被打断”，但问题还是偏重复感受 |

Overall:

```text
~3.65/5
FAIL / near-pass
```

Interpretation:
- 情绪承接是合格的。
- 安全边界是合格的。
- 主要弱点是推进不足：没有把对话引向“发生了什么、用户希望被怎样对待、下一步如何表达边界”。
- 只听到 2 次 Coco 回复，低于标准里的 `>=3`，所以即使质量接近也不能算 pass。

## Root Cause Readout

### A. 延迟瓶颈在 Fast 首次 tool 前

STT 和 TTS 都不是这轮最大问题：
- STT final p50 `2306ms`
- TTS p50 `2620ms`
- 但 `turn_to_fast_tool p50=21896ms`

这说明下一轮应优先优化：
- Fast prompt 长度
- Fast model 选择
- Fast tool schema / pydantic-ai loop 行为
- voice 模式是否应使用更小、更强约束的 agent/prompt

### B. Slow 仍偏慢，但当前不阻塞 Fast 主链路

Slow 最新只完成 1/3：
- `slow_agent_run_completed=1`
- `slow_agent_run_completed latency=85102ms`

它影响跨轮聪明程度，但不是首响延迟的主因。当前 Fast 首响已足够慢，先不要把下一轮优化重点放在 Slow。

### C. Xfyun timeout 仍存在，但 STT final 正常

本轮仍有 6 条 Xfyun timeout/error sample：

```text
read message from conn timeout
```

但 `stt_transcript_final=3` 且文本可用，所以这是稳定性噪声/后续优化，不是当前 P0 阻塞。

## Files To Know

Runtime:

```text
backend/llm_provider.py
backend/fast.py
backend/slow.py
backend/voice/bridge_agent.py
backend/voice/entrypoint.py
tools/voice_e2e/persona_agent.py
```

Evolve/eval:

```text
.evolve/run_e2e.sh
.evolve/voice_eval.md
.evolve/voice_eval.py
.evolve/run.log
```

Tests added/updated:

```text
tests/test_llm_provider.py
tests/voice/test_voice_entrypoint_runtime_config.py
tests/voice/test_fast_slow_basic.py
tests/voice/test_voice_entrypoint_carryover.py
```

## How To Reproduce

```bash
# Unit tests
uv run --group voice --group test pytest tests/voice/ -q --timeout=60
uv run --group voice --group test pytest tests/ -q

# Real voice e2e
bash .evolve/run_e2e.sh

# Parse latest logs
python .evolve/voice_eval.py
python .evolve/voice_eval.py --json
```

Logs:

```text
/tmp/moodcoco-agent.log
/tmp/moodcoco-persona.log
/tmp/moodcoco-e2e-room.txt
```

## Suggested Next `$evolve` Round

Goal:

```text
Reduce Fast first-tool latency to the 可用线:
turn_to_fast_tool p50 <= 8000ms and p90 <= 15000ms
without reducing smartness below 3.8/5.
```

Recommended order:

1. Measure Fast prompt size per turn and log `fast_prompt_context_chars`.
2. Add a voice-specific minimal Fast prompt or voice-specific Fast agent.
3. Make voice Fast use a strictly small/fast model via `OPENAI_FAST_MODEL` or provider-specific config.
4. Keep `ai_message` as the first and only required tool in voice mode.
5. Re-run `.evolve/run_e2e.sh` and score with `.evolve/voice_eval.py`.

Do not start by tuning Slow. Slow is useful for cross-turn quality, but the current failing metric is Fast first audible response.

## 30 秒接手指南

1. Read `.evolve/voice_eval.md` for the pass/fail standard.
2. Run `bash .evolve/run_e2e.sh`.
3. Run `python .evolve/voice_eval.py`.
4. If `turn_to_fast_tool` is still >15s, optimize Fast prompt/model/tool loop first.
5. Only after latency passes, tune smartness with Slow carryover and skill selection.
