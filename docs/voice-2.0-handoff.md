# Voice 2.0 Handoff

**Branch**: `evolve/livekit-fast-slow`（已 push origin）
**Date**: 2026-04-29
**Status**: 架构 + 单测 ✅ DONE / 真实演练发现 3 个待修 BUG（P0/P1/P2）

## TL;DR

- ✅ **完成**：Voice 2.0 用 pydantic-ai 双 agent（fast + slow）替换 r5 的 hardcoded fast/slow 序列。8 维全 pass，净减 1953 行 r5 死代码。
- ⚠️ **待修**：真实浏览器演练发现 5 个问题，P0/P1/P2 是 "AI 回复非常短" 的根因，都是 1-3 行改动，建议 F-2.0c 一并修。
- 📝 **接手**：直接读"真实浏览器演练发现的 BUG"那段，按修复杠杆表的顺序动手。

## Trajectory

| Phase | Total | Status | What changed |
|-------|-------|--------|--------------|
| F-2.0a r1 | 2.38 | fail | 桥接到位（3 deterministic 全 PASS）但 slow 只用 1 tool / 无 cross-turn carryover |
| F-2.0a r2 | **3.13** | **pass** | slow prompt + persist mutations + trim fallback → 4 distinct tools / 2 carryover events / 3 真心理咨询回应 |
| F-2.0b r1 | **3.25** | **pass** | cleanup 删 r5 死代码 -1953 行 / bridge_agent.py 提取 / 45 测试全 green |

## 13 commits on `evolve/livekit-fast-slow`

```
7db3ec3 F-2.0b r1: repoint bridge-style tests to bridge_agent
1dfa28c F-2.0b r1: purge r5 dead code (decisions module + obsolete tests)
980c223 F-2.0b r1: delete deprecated r5 fast_slow_agent.py
3a34c5c F-2.0b r1: extract pydantic-ai bridge to bridge_agent.py
55c7526 F-2.0a r2: trim bridge fallback to honor real slow no-op
97fef38 F-2.0a r2: persist fast-context mutations across turns
b530878 F-2.0a r2: tune slow prompt to use ≥3 distinct mutation tools
f5b011e F-2.0a r1: make slow mutation trace deterministic
43e9ec9 F-2.0a r1: lengthen voice e2e window
5a6f15d test: fix backend skill script import paths
231668f F-2.0a r1: update voice tests for bridge hook
8cb6d6b F-2.0a r1: replace voice turn hook with bridge
909b041 F-2.0a r1: extend fast and slow voice deps
```

## What Works Today

### Pipeline 全链路（pydantic-ai-driven）

```
user audio → STT → on_user_turn_completed (bridge ~30 lines)
   │
   ├─ fast_agent.run(user_msg, deps=fast_deps)   ── pydantic-ai loop, ≤3 iter, tools=[ai_message → say + 7 现有]
   │   主线对用户出声，唯一 TTS publish
   │
   └─ slow_agent.run(user_msg, deps=slow_deps)   ── pydantic-ai loop, ≤3 iter, tools=[3 现有 + 3 mutation]
       ├─ slow_inject_to_fast(text)
       ├─ slow_set_fast_retrieval(block)
       └─ slow_attach_skill_to_fast(name)
       后台 mutate fast_deps 字段，跨 turn carryover 持久化
```

### 验证证据（F-2.0b r1 e2e log）

- 3 deterministic checker 全 PASS
- 4 distinct slow mutation tools 串使用：`slow_inject_to_fast` `read_skill` `slow_attach_skill_to_fast` `slow_set_fast_retrieval`
- 3 个 `cross_turn_carryover` 事件（inject_count 1→2→3 增长，turn N+1 Fast prompt 含 turn N Slow 注入）
- 3 个真心理咨询回应（listen / validation / emotion-granularity tier）
- bridge fallback **完全 suppressed**（无 `bridge_no_mutation` `bridge_default_inject`）
- Logger `voice.bridge_agent` 166 entries / `voice.fast_slow_agent` **0 entries**（彻底清理）

### Tests

- `tests/voice/` 45/45 passed（删 6 旧 + 修 13 import）
- `tests/` 整体 90/90 passed（文字 chat 不受影响）

## Files Touched

```
NEW:
  backend/voice/bridge_agent.py             (~370 lines, 提取 F-2.0a 桥接)
  tests/voice/test_voice_entrypoint_carryover.py  (新增 carryover 测试)

MODIFIED:
  backend/fast.py                            (+voice_session, skill_bundle, retrieval_block, dynamic_inject + voice_system_extras() + ai_message voice mode + slow_voice_carryover_payload)
  backend/slow.py                            (+fast_deps, reasoning_trail, search_cache, pending_actions + 3 new mutation tools + voice prompt guidance)
  backend/voice/entrypoint.py                (替换 on_user_turn_completed 为 ~30 行桥接)
  tests/voice/test_*.py                      (13 测试 import 路径改 bridge_agent)

DELETED:
  backend/voice/fast_slow_agent.py           (-1471 lines, r5 hardcoded loop)
  backend/voice/decisions/__init__.py
  backend/voice/decisions/continue_decider.py(-265)
  backend/voice/decisions/merged_decision.py (-209)
  tests/voice/test_merged_decision.py        (-160, 5 tests)
  tests/voice/test_filler_max_count_one section in test_fast_slow_basic.py
  
NET: +1150 / -2657 = -1507 lines code
```

## 真实浏览器演练发现的 BUG（P0–P4）

8 维测试全 pass 后跑了一次真实端到端浏览器对话（persona ↔ coco，~110s 音频），扒日志发现 5 个问题。**P0/P1/P2 是导致"AI 回复非常短"的根因**，P3 是 P0 副作用，P4 是 by-design。

### P0 — STT 把一句话切成 36 段（最严重）

**根因**：`backend/voice/entrypoint.py:132-133`
```python
vad = _silero.VAD.load()  # 用默认 min_silence_duration ≈ 0.55s
stt_plugin = _agent_stt.StreamAdapter(stt=XfyunSTTPlugin(), vad=vad)
```

**机制**：人说话中间自然停顿（吸气、想词）≥0.55s 就被 VAD 当 turn 结束，触发 `on_user_turn_completed`。一句"我和我妈昨天吵架了 我有点难受 不想说话"被切成 5-7 个独立 turn。叠加 Xfyun WPGS partial→final 模式，turn `8a3b5647` 实测 **53 条 stt_transcript_final**，多数 text 长度=0。

**后果**：每段都跑一次 fast+slow，AI 只来得及回 1-2 字"嗯""我懂"。

**修法**（一行）：`_silero.VAD.load(min_silence_duration=1.2)` 或加 STT debouncer 合并 same-turn finals。

### P1 — Slow 注入累积 6316 字（短回复次因）

**根因**：`backend/voice/bridge_agent.py:244-245`
```python
self._slow_state["carryover_inject"] = slow_deps.carryover_inject[-3:]  # 有 cap
self._slow_state["carryover_skills"] = slow_deps.carryover_skills        # 没 cap，无限累积
```

**机制**：F-2.0a r2 加了跨 turn carryover，但 `skill_bundle` 漏写 LRU。Slow 一次 `slow_attach_skill_to_fast("listen")` 就把 3505 字 SJTU SKILL.md 永久挂上。实测 24× inject + 1× attach_skill = **6316 字** 永远在 Fast 系统提示里。

**后果**：Fast prompt 越涨越大 → minimax-m2.7 流式吐字越来越慢。

**修法**（一行）：`bridge_agent.py:245` 改 `[-2:]`。

### P2 — Fast latency p90=15s（架构偏差）

**根因**：`backend/llm_provider.py:49-56` Fast 和 Slow 共用同一个 `create_agent_model()`，都跑 `minimax/minimax-m2.7` thinking 模式。

**偏差**：原始设计是 `Fast = no-thinking + Slow = thinking`，**这个区分在代码里没落地**。`backend/fast.py:73` 和 `backend/slow.py:90` 都调 `create_agent_model()` —— 完全相同。

**后果**：每条用户说话 Fast 也走完整 reasoning，叠加 P1 那 6316 字 prompt → 单 say latency p50=6873ms / p90=15185ms / max=21221ms，30% 单 say >10s。

**修法**：`llm_provider.py` 拆 `create_fast_model()` / `create_slow_model()`，Fast 用 `extra_body={"reasoning_effort":"none"}` 或换成 minimax-m2.5 / doubao-lite。

### P3 — Xfyun WS timeout 37 次（P0 副作用）

**根因**：`backend/voice/_vendor/psy/stt/streaming_stt_manager.py:133` 每个 STT recognize 调用开新 WebSocket。P0 把 1 句切成 36 turn → 36× 新 WS → 累积 37 次 timeout。

**修法**：P0 修了 P3 自动跟着修。

### P4 — bridge_no_mutation fallback 4 次（by-design）

**根因**：`bridge_agent.py:208-232` Slow 偶尔 thinking 不 emit tool_call，bridge 兜底注入 fallback hint。17% 触发率，**这是设计内的兜底，不是 bug**。

### 修复杠杆排序

| Fix | 改动 | 一行核心 | 预期影响 |
|---|---|---|---|
| **P2** | `llm_provider.py` 拆双 model | `extra_body={"reasoning_effort":"none"}` 或换 minimax-m2.5 | Fast latency 减半 |
| **P0** | `entrypoint.py:132` VAD 参数 | `min_silence_duration=1.2` | 36 段 → 3-5 段 |
| **P1** | `bridge_agent.py:245` 加 cap | `[-2:]` 一行 | prompt 6316→2000 字 |
| P0b | STT debouncer 合并 same-turn finals | ~30 行 | P0 兜底 |

P2 + P0 + P1 三处都是 1-3 行改动，建议一并 F-2.0c 跑一轮 evolve 验证。

## 其他遗留问题（非演练发现）

### 1. ai_message 仍同时支持文字 + voice 模式
合并 OQ §8.1 default = B：voice 模式调 `session.say()`，文字模式写 chat history。`if voice_session != None` 分支可以维持不动。未来要分两个 agent（voice-only / chat-only）需要拆 deps。

### 2. Slow 跨 turn 状态目前 in-memory（OQ §8.2 default A）
死了 session 就丢。要持久化到 memU 或 Redis 留 phase 3。

### 3. browser-audio-flowing checker 仍依赖 Chrome MCP
C 跑评分时用 `mcp__claude-in-chrome__*` 取 sample 写 `/tmp/browser_audio_sample.json`。

### 4. cross-turn-memory 4 分（不是 5 分）
要拿 5 分需要：`pending_actions` 真被消费跨 turn。目前只 reasoning_trail / inject / skill / retrieval 跨 turn，`pending_actions` 字段定义了但 slow LLM 没主动用。

## How to Run It

```bash
# .env 已配 LIVEKIT/XFYUN/MINIMAX/DOUBAO/OPENROUTER

# 起完整 stack
bash .evolve/run_e2e.sh
sleep 30

# 浏览器
open http://localhost:3000/voice-room/index.html
# 点「加入房间」
# 听 persona ↔ coco 自动对话

# 停
touch /tmp/persona-yuyu.stop
```

或直接跑 unit tests 验证：
```bash
uv run --group voice --group test pytest tests/voice/ -q --timeout=60   # 45/45
uv run --group voice --group test pytest tests/ -q                       # 90/90
```

## 30 秒接手指南

1. 跑 e2e + 浏览器（见 How to Run It），确认本地能听到双 AI 真对话
2. 看 `/tmp/moodcoco-agent.log` 一个 turn 的 `fast_agent_run_*` `slow_tool_call: slow_*` 日志结构
3. **先动 P0/P1/P2 三处 BUG**（修复杠杆表）→ 跑一轮 evolve 验证 → 再 PR 到 main
4. Phase 3 候选：memU 持久化 / pending_actions 消费 / 长对话稳定性
