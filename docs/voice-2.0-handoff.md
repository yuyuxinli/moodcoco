# Voice 2.0 Handoff (F-2.0a + F-2.0b complete)

**Branch**: `evolve/livekit-fast-slow`
**Date**: 2026-04-29
**Status**: ✅ Both features pass. Voice 2.0 DONE.

## TL;DR

Voice 2.0 用 pydantic-ai 双 agent（fast + slow）替换 r5 的 hardcoded fast/slow 序列。Slow 后台 mutate Fast.context（4 distinct tools, cross-turn carryover），Fast 主线对用户唯一出声。**净减 1953 行 r5 死代码**，pipeline 更清爽。

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

## Known Issues / Phase 2

### 1. ai_message 仍同时支持文字 + voice 模式
合并 OQ §8.1 default = B：voice 模式调 `session.say()`，文字模式写 chat history。代码里有个 `if voice_session != None` 分支，可以维持不动。如果未来要分两个 agent（一个 voice-only 一个 chat-only），需要拆 deps。

### 2. minimax-m2.7 streaming 偶发空流仍存在
F-2.0a/F-2.0b 没专门处理。Pydantic-ai 内部 retry 机制部分覆盖，加 `result_retries=3` 后实测 R2 跑 3 turn 都正常出 token。如果未来用更长对话观测到回归，需要回到 r5 STAGE_K retry+fallback 那个机制。

### 3. Slow 跨 turn 状态目前 in-memory（OQ §8.2 default A）
死了 session 就丢。如果要持久化到 memU 或 Redis，未来 phase 3 再做。

### 4. browser-audio-flowing checker 仍依赖 Chrome MCP
C 跑评分时用 `mcp__claude-in-chrome__*` 取 sample 写 `/tmp/browser_audio_sample.json`。已有 sample 在 r3-r5 跑通。

### 5. cross-turn-memory 4 分（不是 5 分）
要拿 5 分需要：`pending_actions` 真被消费跨 turn。目前只 reasoning_trail / inject / skill / retrieval 跨 turn，pending_actions 字段定义了但 slow LLM 没主动用。

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

1. 跑 e2e + 浏览器，确认本地能听到双 AI 真对话（不是 r5 fallback echo）
2. 看 `/tmp/moodcoco-agent.log` 一个 turn 的 `fast_agent_run_*` `slow_tool_call: slow_*` 日志结构
3. **可以直接 PR 到 main**：13 commits + 8 维评分 + 45/45 测试 + 净减 1507 行
4. Phase 3 候选：memU 持久化 / pending_actions 消费 / 长对话稳定性
