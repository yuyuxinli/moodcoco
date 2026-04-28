# LiveKit Fast/Slow Voice Demo — Design

**Date**: 2026-04-29
**Status**: DRAFT — pending user review
**Scope**: Runtime-only voice demo, no memU, no long-term memory.
**Author**: brainstorming session 收敛

---

## 0. 目的

验证 fast/slow 编排模式在中文语音场景能否跑通：
- fast filler 能否在 slow 主回复之前给到"我听到了"的体感
- chat_ctx 写回机制能否避免 slow 重复 filler 内容
- 合并决策（search + skill）与 slow 并行能否在不增加延迟前提下为 slow_v2 准备上下文
- DP-continue 能否在 slow_v1 太浅时触发 slow_v2 补深度

**非目的**：
- 不验证记忆检索质量（demo 用 stub）
- 不验证多轮长期记忆（无 memU）
- 不验证印尼场景（中文 only）

---

## 1. 架构总览

```
mic → XfyunSTT → AgentSession.on_user_turn_completed (FastSlowAgent)
                       │
                       ├─ [≤1 次 fast filler]
                       │   触发条件: slow_v1 还没出 token 且 ≥ 0.4s
                       │   fast LLM (豆包 lite) → "嗯我听到了"
                       │   session.say(filler, add_to_chat_ctx=False)
                       │   chat_ctx.add_message(role="assistant", content=filler)
                       │
                       ├─ [并行] 合并决策 (1 次豆包 lite, JSON 输出)
                       │   { "search": {"yes": bool, "kw": str},
                       │     "skill":  "listen|crisis|face-decision|..."  }
                       │       │
                       │       ├─ search.yes=true → 检索 stub (demo 返回 "")
                       │       └─ skill=X        → load SJTU SKILL.md
                       │       └─ stash 到 ctx_for_v2
                       │
                       ├─ slow_v1 (minimax-m2.7) → TTS
                       │   看 chat_ctx (含 filler)，不等决策不等检索
                       │
                       ├─ [DP-continue] slow_v1 完成后 → 豆包 lite
                       │   yes → slow_v2 (用 ctx_for_v2) → TTS
                       │   no  → done
                       ▼
                  MinimaxTTS → speaker
```

**核心机制（沿用 LiveKit fast-preresponse.py 的 chat_ctx 写回模式）**：
- fast filler 通过 `session.say(text, add_to_chat_ctx=False)` 直接 TTS，绕过 LLM
- 手动调 `chat_ctx.add_message(role="assistant", content=filler)` 写回
- slow 看到 chat_ctx 里 assistant 已经说过 filler 内容，自然衔接不重复

---

## 2. 路径分支

3 种用户感知路径，由 slow_v1 出 token 速度自动决定（**无需显式分类器**）：

| 路径 | 触发条件 | 用户听到 | 总时长 |
|---|---|---|---|
| 短 | 用户说"嗯/好"等短消息，slow_v1 < 0.4s 出 token | 仅 slow_v1 | ~1s |
| 标准 | 正常陈述，slow_v1 ≥ 0.4s 出 token | filler + slow_v1 | ~6s |
| 长 | 复杂深度消息 + DP-continue=yes | filler + slow_v1 + slow_v2（中间沉默） | ~12s |

**关键参数**：
- `min_silence_before_kicking = 0.4s`：fast filler 触发前的最小等待
- `fast_filler_max_count = 1`：filler 最多说 1 次（用户已知在等，多说反而吵）
- `dp_continue_timeout = 200ms`：DP-continue 决策超时

---

## 3. 组件清单

| 组件 | 文件 | 继承/职责 | 行数 |
|---|---|---|---|
| `XfyunSTTPlugin` | `backend/voice/plugins/xfyun_stt.py` | `livekit.agents.stt.STT`，包装 psychologists `speech_to_text_xfyun_service.py` | ~200 |
| `MinimaxTTSPlugin` | `backend/voice/plugins/minimax_tts.py` | `livekit.agents.tts.TTS`，包装 psychologists `services/shared/tts/service.py` | ~200 |
| `FastSlowAgent` | `backend/voice/fast_slow_agent.py` | 继承 `Agent`，编排 fast×1 + 合并决策 + slow_v1 + DP-continue + slow_v2 | ~280 |
| `MergedDecision` | `backend/voice/decisions/merged_decision.py` | 1 次豆包 lite 调用，JSON 输出 search+skill | ~80 |
| `SJTUSkillRouter` | `backend/voice/skill_router.py` | 读 `MOODCOCO_SKILLS_DIR` 下 7 个 SKILL.md frontmatter | ~80 |
| `RetrievalStub` | `backend/voice/retrieval_stub.py` | demo 阶段返回 `""`，phase 2 替换为 memU `retrieve_rag` | ~20 |
| `entrypoint.py` | `backend/voice/entrypoint.py` | AgentSession 起 + plugin 装配 | ~80 |
| **总计** | | | **~940 行** |

**LLM provider 配置**（复用 `livekit-plugins-openai`，base_url 切换）：
- fast / 决策：`doubao-seed-2-0-lite-260215` via 火山方舟（`DOUBAO_BASE_URL`）
- slow main：`minimax/minimax-m2.7` via OpenRouter（`OPENAI_BASE_URL`）

---

## 4. 数据流（chat_ctx 演化）

举例用户说："我和我妈昨天吵架了"

```
T0       chat_ctx = [..., user: "我和我妈昨天吵架了"]
T+150ms  filler 生成 = "嗯，听起来不太好受"
         chat_ctx = [..., user: "...", assistant: "嗯，听起来不太好受"]  ← 手动写回
T+150ms  并行：合并决策启动 → JSON: {search: {yes, kw:"我妈"}, skill: "listen"}
                          → load listen/SKILL.md → ctx_for_v2["skill"] = "..."
                          → 检索 stub → ctx_for_v2["retrieved"] = ""
T+200ms  slow_v1 启动，system prompt = 基础人格，messages = chat_ctx
         slow_v1 看到 chat_ctx 里 assistant 已说"嗯，听起来不太好受"
         → 自然衔接："发生什么了？是因为什么吵起来的？"
T+5s     slow_v1 完成
T+5.2s   DP-continue 输入 = slow_v1 输出 + chat_ctx
         → "回得太开放问句了，没有承接情绪" → yes
T+5.5s   slow_v2 启动，system prompt = 基础人格 + listen skill 内容
         messages = chat_ctx (now 含 slow_v1)
         retrieved = ""（stub）
         → "你愿意的话跟我说说，妈妈说了什么让你最难过？"
T+8s     slow_v2 完成 ✅
```

---

## 5. 配置（.env）

```bash
# === 已有，复用 ===
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=${OPENROUTER_API_KEY}
OPENAI_MODEL=minimax/minimax-m2.7

DOUBAO_API_KEY=...
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-seed-2-0-lite-260215  # demo 用 lite 跑决策/fast

MOODCOCO_SKILLS_DIR=SJTU_skills/moodcoco-psych-companion-v1/skills

# === 待补：psychologists 复用 ===
MINIMAX_API_KEY=...           # 复用 OPENROUTER_API_KEY 同账号或单独申请
MINIMAX_TTS_MODEL=speech-01
MINIMAX_TTS_VOICE_ID=female-shaonv

XFYUN_APP_ID=...
XFYUN_API_KEY=...
XFYUN_API_SECRET=...
XFYUN_ASR_URL=...

# === 编排参数 ===
FAST_SLOW_MIN_SILENCE_MS=400
FAST_SLOW_FILLER_MAX_COUNT=1
DP_CONTINUE_TIMEOUT_MS=200
```

---

## 6. 文件结构

```
backend/voice/
├── __init__.py
├── plugins/
│   ├── __init__.py
│   ├── xfyun_stt.py          # 200
│   └── minimax_tts.py        # 200
├── decisions/
│   ├── __init__.py
│   └── merged_decision.py    # 80
├── fast_slow_agent.py        # 280
├── skill_router.py           # 80
├── retrieval_stub.py         # 20
└── entrypoint.py             # 80
```

---

## 7. 不在范围（明确排除）

- memU 集成 / Hybrid 检索（BM25 + pgvector）
- DoubaoTTSPlugin（字节智能语音 appid/token 待申请）
- LLM failover chain（demo 阶段单一 provider，挂了报错）
- VAD / turn detection 优化（用 LiveKit 默认 silero）
- 印尼场景 / Cohere multilingual
- 流式 STT 的 interim results 处理
- 并发用户 / 多 room 路由

---

## 8. Open Questions（明天确认）

1. **TTS 路由**：demo 阶段 MinimaxTTSPlugin 单跑；DoubaoTTSPlugin 骨架什么时候补？（建议拿到字节智能语音 key 后单独 PR）
2. **slow_v2 的 system prompt 拼接**：skill SKILL.md 是直接全文塞，还是只塞"路由优先级"+"核心动作"段？（影响 slow_v2 的 token 成本和聚焦度）
3. **DP-continue prompt 设计**：判断标准是什么？"slow_v1 太浅"如何形式化？需要给豆包 lite 几条规则
4. **filler 的 prompt 是否依赖 skill 决策**：合并决策的 skill 字段在 filler 触发时通常还没出来（fast 0.4s vs 决策 ~150ms 看顺序）。是否要让 fast 先发，等决策完再走？还是 fast 永远只看 user_msg 不看 skill？
5. **检索 stub 的接口签名**：`async def retrieve(user_id, query, top_k=5) -> list[str]`——确认这个签名，phase 2 接 memU 时不变

---

## 9. Next Steps

1. **明天**：用户 review 这份 design，给 4 个 open questions 拍板
2. **拍板后**：生成 implementation plan via `/writing-plans` skill
3. **实现策略**：用 `/evolve` 把这个 design 当 goal，loop 迭代 940 行新代码
   - evolve 评估器：
     - 单元测试：plugin 接口 mock 通过
     - 集成测试：起一个本地 mic → 全链路（用 psychologists 现有 minimax/讯飞 service 做底层）
     - 体验测试：3 种路径手动验证一遍
4. **风险点**：
   - psychologists 的 stt/tts service 是否能直接 import（可能要解 backend 包路径问题）
   - LiveKit AgentSession 跟"chat_ctx 手动 add_message"的兼容（需要看 1.x 版本 API）
   - 豆包 lite JSON 输出稳定性（合并决策依赖结构化输出）

---

## 10. 参考

- LiveKit fast-preresponse.py：`/Users/jianghongwei/Documents/GitHub/agents/examples/voice_agents/fast-preresponse.py`
- LiveKit STT 基类：`livekit.agents.stt.stt.STT`（`stt.py:129`），抽象方法 `_recognize_impl`
- LiveKit TTS 基类：`livekit.agents.tts.tts.TTS`（`tts.py:66`），抽象方法 `synthesize`
- psychologists STT：`/Users/jianghongwei/Documents/psychologists/backend/services/shared/stt/speech_to_text_xfyun_service.py`
- psychologists TTS：`/Users/jianghongwei/Documents/psychologists/backend/services/shared/tts/service.py`
- SJTU skill bundle：`SJTU_skills/moodcoco-psych-companion-v1/skills/`（7 个：base-communication / calm-body / crisis / face-decision / listen / untangle / validation）
- 之前更全的 6-phase plan：`docs/voice-impl-plan.md`（这份 demo design 是其中 Phase 1 的最小切片）
