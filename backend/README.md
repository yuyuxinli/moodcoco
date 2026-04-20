# moodcoco — 快慢思考 MVP

最小化验证 **Fast Thinking / Slow Thinking 双层架构**的可运行 Demo。纯 PydanticAI 实现，完全脱离原 OpenClaw 栈。

## 架构

```
用户消息
   │
   ▼
Fast Agent（tool-only，1 秒级）
  └─ 7 个 UI Tool：ai_message / ai_options / ai_mood_select / ai_praise_popup
                  ai_complete_conversation / ai_body_sensation / ai_safety_brake
  └─ ai_message(needs_deep_analysis=True) ─┐
                                           ▼
                                    Slow Agent（loop，不限时）
                                      └─ list_skills / read_skill / write_memory
                                      └─ 读 backend/skills/*/SKILL.md
                                      └─ 写 backend/state/MEMORY.md
                                      └─ 返回补充气泡文本
```

关键点：

- **快思考**：`output_type=NoneType`（tool-only），静态 `system_prompt` = SOUL + IDENTITY + AGENTS + prompts，动态 `@instructions` 注入 MEMORY.md
- **慢思考**：`output_type=str`，PydanticAI 自带 agent loop，**不设超时**，让它反复 `read_skill → write_memory → ...` 直到收敛
- **协调**：同步串行。快 → 若 `needs_deep_analysis=True` → await 慢 → 打印补充

## 安装

```bash
cd moodcoco
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# 国内网络推荐清华镜像：
# pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .
cp .env.example .env
# 编辑 .env 填入 OPENROUTER_API_KEY
```

> Python 要求 ≥3.12。依赖包括 `pydantic-ai`、`openai`、`python-dotenv`。

默认模型是 `minimax/minimax-m2.5`（via OpenRouter）。换模型只需改 `.env` 的 `OPENAI_MODEL` 与 `OPENAI_BASE_URL`。

## 运行

```bash
python -m backend.chat               # 进入 REPL
python -m backend.chat --reset-memory # 重置 MEMORY.md 后再进
```

REPL 示例：

```
你 > hi

[快思考]
  💬 你好呀，今天想聊点什么？ ⚡deep

[慢思考 loop 运行中…]
  tool 轨迹: ['list_skills', 'read_skill(check-in)', 'write_memory(## 跨关系模式)']

[补充气泡] 最近一切还稳吗？哪怕是一件小事也可以跟我说。
```

## 文件结构

```
backend/
  __init__.py
  fast.py            # Fast Agent + 7 UI Tool
  slow.py            # Slow Agent + 3 Tool + MEMORY.md 读写
  coordinator.py     # fast→slow 协调（无超时）
  chat.py            # CLI REPL 入口
  llm_provider.py    # OpenAI 兼容 provider + load_prompt
  prompts/           # Fast/Slow 静态 prompt
    fast-instructions.md
    fast-tools.md
    slow-instructions.md
    SOUL.md          # Coco 人格
    IDENTITY.md
    AGENTS.md
    USER.md
    TOOLS.md
  skills/            # Slow Agent 动态发现的技能库（20 个）
  state/             # 运行时状态（.gitignored）
    MEMORY.md        # 长期记忆
    SLOW_GUIDANCE.md # Slow→Fast 桥接
```

## 调试 Tips

- 想看 Fast 走了哪些 tool：直接看终端 `[快思考]` 段
- 想看 Slow 调了几轮：看 `tool 轨迹`
- 想看记忆写入：`cat backend/state/MEMORY.md`
- 想加新 Skill：在 `backend/skills/<name>/SKILL.md` 新建即可，Slow Agent 会通过 `list_skills()` 发现
- 想改快思考触发规则：改 `backend/prompts/fast-tools.md`

## 已知限制（MVP 范围）

- 单用户、无 session 持久化、无数据库
- 对话历史不跨 turn 保留（每轮独立调 `fast_agent.run`）
- 无前端，UI Tool 调用只打印到终端
- 无流式输出（`.run()` 一次性返回）

这些都是刻意为之，只为验证 Fast/Slow 双层调度是否可用。
