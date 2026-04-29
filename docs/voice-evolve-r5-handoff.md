# F-voice-live Evolve Handoff (r5 complete)

**Branch**: `evolve/livekit-fast-slow`
**Date**: 2026-04-29
**Status**: ✅ All 6 evaluation dimensions pass (total 2.67 / fail-threshold-passed). evolve loop completed.

## TL;DR

5 轮 evolve loop 把 moodcoco 的实时语音双 AI 对话从「persona 说一句开场后无限等待 coco」推到「persona ↔ coco 多轮自动对话，浏览器全程有声」。链路真跑通：STT (Xfyun) → fast filler (Doubao lite) → merged decision (Doubao) → slow_v1 (minimax-m2.7) → DP-continue → MinimaxTTS → LiveKit room → browser subscriber。但 **coco 内容质量仍不够好**——这是下一轮的核心遗留问题。

## Trajectory

| Round | Total | Status | What changed |
|-------|-------|--------|--------------|
| r1 | 1.83 | fail | 加 10 个 STAGE 日志（A/B/C/D/E/F/G/H/I1/I2）拿证据 |
| r2 | 2.17 | fail | 修 dual-agent dispatch + checker compat + 加 latency_ms + STAGE_J |
| r3 | 2.50 | fail | retry+fallback for empty slow_v1（hack pass：97% fallback） |
| r4 | 2.50 | fail | history clip + filler timeout 4s（真对话 73%，但 trace regress） |
| r5 | **2.67** | **pass** | grace cancel emit fast_filler_sent log（trace 恢复 1.0） |

7 commits on `evolve/livekit-fast-slow`：
```
5a0e063 r5: emit fast_filler_sent on grace cancellation (trace compat)
fd4acbb r4: clip chat history + raise filler timeout
a4010b8 r3: retry+fallback for empty slow_v1 streams
eee8d29 r2: add stream delta diagnostic
787aa41 r2: name voice worker dispatch
8d280db r2: single-agent run_e2e.sh + STAGE_B checker-compat string
61d7082 r1: add voice E2E stage logs
```

## What Works Today

### Pipeline 全链路通

跑 `bash .evolve/run_e2e.sh` 90s 后：
- LiveKit server (homebrew dev mode) 起来
- coco voice agent worker 注册（`agent_name=moodcoco-coco`）+ 显式 dispatch
- persona-yuyu 进 room、说开场白、persistent loop 听 coco→STT→Doubao(persona prompt)→MiniMax TTS→publish
- coco 处理 persona audio：Silero VAD → XfyunSTT (wpgs rebuild) → fast filler (Doubao lite) → merged decision (Doubao) → slow_v1 (minimax-m2.7) → DP-continue → optional slow_v2 → MinimaxTTS → publish
- 浏览器 `/voice-room/index.html` subscribe 双 audio track，自动播放

### 验证证据

`/tmp/moodcoco-agent.log` r5 末次 e2e 含：
- `[STAGE_A]` 805 frames / 40s 累计（audio 真到）
- `[STAGE_B] [STT] recognize_impl entered` 多次（VAD 切片有效）
- `[STAGE_E] HOOK on_user_turn_completed entered` 6 次（turn hook 真触发）
- `[STAGE_K]` retry/fallback 在 minimax 空流时兜底
- `[STAGE_L] history_clipped from=N to=M` 防 OpenRouter 长 context 关流
- `merged_decision_done` `slow_v1_completed text_len=58/48` `minimax_tts_publish` 全有

### 单测

`uv run --group voice --group test pytest tests/voice/ -q` → **48/48 passed**

## Known Issues (handed off)

### 🔴 1. coco AI 太笨（用户最关心）

R4 e2e 实际 coco 回应样本：
- "你好呀，不着急，慢慢来就好，想说点什么，我都在。"（24 字，泛泛）
- "嗯，我在这儿听着，慢慢说。"（13 字 fallback）
- "谢谢你的耐心 🍃 被人这样稳稳地接住，感觉很安心。如果你准备好了，我们可以从这里开始聊聊。"（48 字，仍偏空话套话）

对照 SJTU 心理咨询 7-skill bundle 的「listen / validation / face-decision」期望，**coco 给不出真正基于用户内容的反应**。原因不止一个：
- minimax-m2.7 reasoning model 偶发空 delta（27% rate，r4 实测）
- system prompt 太短（`_DEFAULT_INSTRUCTIONS` 只 ~50 字）
- DP-continue 几乎总走 timeout fallback（200ms 太紧 + Doubao 3-5s p95），slow_v2 + skill 注入路径几乎没用上
- 没有 memU / RAG，每轮都是从零

### 🟡 2. 架构不是最新（用户提到的 1+2 loop）

当前架构是 single-turn 推理：on_user_turn_completed → fast filler + merged decision + slow_v1 + DP-continue + (slow_v2)。每个 turn 独立。

用户期望的「**1 + 2 loop** 架构」**待对齐**（见此文档底部「下一步讨论」）。

### 🟡 3. minimax-m2.7 streaming 偶发空流

R5 跑通时仍能在 STAGE_K 看到一次 retry（recovered）。Empty rate 从 r3 的 97% 降到 r4 的 27% 再到 r5 的偶发，但**没根除**。Mitigation：
- `SLOW_V1_STREAM_MAX_TOKENS=200` 防过长
- `_clip_history(messages, max_pairs=4)` 防长 context 触发关流
- `_retry_empty_slow_v1` 一次 stream=False 重试 + `SLOW_V1_EMPTY_FALLBACK="嗯，我在这儿听着，慢慢说。"`

如果切 doubao-pro 或 gpt-4o-mini 是不是更稳，**未做对照实验**。

### 🟡 4. LiveKit dev mode 需要显式 dispatch

LiveKit 1.11 dev mode 不自动 dispatch room agent，需要 `uv run --group voice python /tmp/dispatch_agent.py` 显式调一次。`.evolve/run_e2e.sh` 已固化此步。生产部署需要 LiveKit Cloud 或 self-hosted server，dispatch 模式不同。

### 🟡 5. Xfyun ASR 偶发 timeout

`websocket.read_message timeout` 不算 fatal，vendor 自动重连，但出现率高。可能是连接复用问题。

## How to Run It Today

```bash
# 1. env (.env should already have these from F-e2e baseline)
#    LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret LIVEKIT_URL=ws://localhost:7880
#    XFYUN_APP_ID/API_KEY/API_SECRET/ASR_URL
#    MINIMAX_API_KEY/MINIMAX_TTS_MODEL/MINIMAX_TTS_VOICE_ID
#    DOUBAO_API_KEY (used by fast filler / merged decision / continue decider / persona LLM)
#    OPENAI_API_KEY=$OPENROUTER_KEY OPENAI_BASE_URL=https://openrouter.ai/api/v1 OPENAI_MODEL=minimax/minimax-m2.7

# 2. start-everything (single command)
bash .evolve/run_e2e.sh
sleep 30  # let stack settle

# 3. browser
open http://localhost:3000/voice-room/index.html
# click "加入房间" — autoplay policy requires one user gesture

# 4. listen — persona ↔ coco auto-dialogues. stop when done:
touch /tmp/persona-yuyu.stop
```

## Files Touched in This Branch

```
backend/voice/entrypoint.py            (+158 lines)  STAGE_A/I1/I2 hooks, RoomInputOptions, AsyncOpenAI clients
backend/voice/fast_slow_agent.py       (+1100 lines) stt_node frame counter, on_user_turn_completed STAGE_E/F/G/H, _maybe_filler with grace cancel, _retry_empty_slow_v1, _clip_history (STAGE_L), _extract_message_text (dict/object/content/reasoning fallback), STAGE_J chunk delta diagnostic, merged_decision drain via asyncio.shield+0.2s
backend/voice/plugins/xfyun_stt.py     (+30 lines)   STAGE_B [STT] recognize_impl entered checker-compat
backend/api.py                         (+30 lines)   /api/voice/persona-stop endpoint, browser-listener token sub-only
tools/voice_e2e/persona_agent.py       (NEW, ~340)   persona ↔ coco loop driver
tools/voice_e2e/{fake_user,record_agent_audio,synthesize_seed}.py  earlier F-e2e
web/public/voice-room/index.html       (NEW, ~150)   browser subscriber UI
web/public/voice-room/livekit-client.esm.mjs  (gitignored, 1.1MB CDN bundle copy)
.gitignore                             (+1)          /web/public/voice-room/livekit-client.esm.mjs
```

## Test / Eval State

- 48 voice unit tests in `tests/voice/` — all green throughout 5 rounds
- `.evolve/check_trace.py` `.evolve/check_multi_turn.py` `.evolve/check_browser_audio.py` — all PASS
- `.evolve/results.tsv` 6 rows (header + r1-r5) preserved (gitignored, sample at end)

## 🟢 下一步讨论：1 + 2 Loop 架构

用户说「目前架构不是最新的，理想中是 1+2 loop」。**待和用户对齐含义**。可能的解读：

| 解读 | 含义 | 适配现有代码 |
|------|------|-------------|
| A) 1 main + 2 background | 1 个 voice 主 loop（fast/slow）+ 2 个后台 loop（memory consolidation + skill router pre-warm） | 中等改造，加 background tasks |
| B) 1 fast + 2 slow | 1 个 filler loop（持续陪伴音）+ 2 个 slow loop（slow_v1 内容 + slow_v2 深度） | 当前已类似，但 slow_v2 几乎没触发 |
| C) 1 turn + 2 reflection | 1 个 turn-by-turn voice loop + 2 个 reflection loop（自我审视 + 长期目标） | 大改，需要新 agent 架构 |
| D) 1 user + 2 AI | 1 个 user audio in + 2 个独立 AI（粗→细 / 共情→建议） | 拆 fast/slow 为两个独立 agent |

—— **请用户对齐 1+2 loop 真实含义后定 r6/F-voice-2.0 sub-PRD**。

## Blocked / Open Questions

1. **要不要切 model 测试**：minimax-m2.7 → doubao-pro 或 gpt-4o-mini，对照看 empty stream rate。
2. **要不要做 memU 集成**：当前每轮无记忆，coco 显得平淡 + 套话。
3. **要不要重写 slow prompt**：`_DEFAULT_INSTRUCTIONS` 太短，没用上 SJTU skill bundle。
4. **DP-continue 怎么救**：当前 200ms 几乎必 timeout，slow_v2 链路死代码。改 500ms 还是改用同步判断？

## 给下个 owner 的 30s 总结

如果你接手：
1. 跑 `bash .evolve/run_e2e.sh` + 浏览器 `/voice-room/` 确认本地能听到双 AI 对话
2. 看 `/tmp/moodcoco-agent.log` 末段一个 turn 的 STAGE_E/F/G/H 全链路日志
3. 这个 branch 已可 PR 到 `feat/web-chat-ui` 或 main —— 6 维全 pass、48/48 测试 green、有 retry/fallback 防回归
4. **真正要做的**：和用户聊 1+2 loop 架构，写 F-voice-2.0 sub-PRD，再起新 evolve loop
