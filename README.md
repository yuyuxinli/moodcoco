# MoodCoco — AI 情感陪伴

心情可可是一个 AI 情感陪伴 agent，核心能力是帮用户「看见自己」：看见情绪（从模糊到精确命名）、看见原因（连接深层需求）、看见模式（识别重复行为）、看见方法（用户自己找到方向）。

当前实现是 **Fast / Slow 双层思考架构**（PydanticAI），人格和技能定义为 Markdown 文件 + 20 个 Skill，改文件即迭代。

## 目录结构

```
moodcoco/
├── backend/                 ← Fast/Slow Agent 实现（核心代码）
│   ├── fast.py              ← Fast Agent + 7 UI Tool
│   ├── slow.py              ← Slow Agent + 3 Tool + MEMORY 读写
│   ├── coordinator.py       ← fast→slow 协调
│   ├── chat.py              ← CLI REPL 入口
│   ├── llm_provider.py      ← OpenAI 兼容 provider
│   ├── prompts/             ← Fast/Slow 静态 prompt
│   │   ├── SOUL.md          ← 人格：可可是谁
│   │   ├── IDENTITY.md      ← 基础身份
│   │   ├── AGENTS.md        ← 行为规则：四步法、安全红线
│   │   ├── USER.md / TOOLS.md
│   │   └── fast-*.md / slow-instructions.md
│   ├── skills/              ← 20 个 Skill（Slow Agent 动态发现）
│   │   ├── listen / calm-body / breathing-ground / crisis
│   │   ├── diary / pattern-mirror / decision-cooling / ...
│   └── state/               ← [gitignored] 运行时 MEMORY.md / SLOW_GUIDANCE.md
├── eval-reference/          ← 评估参考记录
├── industry-skills/         ← 调研过的业内 skill（参考）
├── docs/                    ← 项目文档
├── tests/                   ← 测试
├── pyproject.toml
└── CLAUDE.md                ← 项目约定（必读）
```

## 快速开始

```bash
cd moodcoco
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# 填入 OPENROUTER_API_KEY

python -m backend.chat                 # 进入 REPL
python -m backend.chat --reset-memory  # 重置 MEMORY 后进
```

详细说明见 `backend/README.md`。

## 四步法（AGENTS.md）

1. **看见情绪**：从"好烦"引导到精准情绪词
2. **看见原因**：连接深层需求，不下结论
3. **看见模式**：通过 MEMORY.md 识别跨 session 的重复行为
4. **看见方法**：用户自己找到方向，不替用户决定

## 安全红线（AGENTS.md）

自伤 / 自杀意念 → 立即停止一切常规对话，走 `ai_safety_brake`。

## 核心资产说明

| 文件 | 作用 | 迭代方式 |
|---|---|---|
| `backend/prompts/SOUL.md` | 可可人格定义 | 直接改文件，改完跑 `/evolve` 验证 |
| `backend/prompts/AGENTS.md` | 四步法 + 状态感知 + 安全规则 | 同上 |
| `backend/skills/<name>/SKILL.md` | 单个技能的触发规则 + 行为指南 | 新建目录即可被 Slow 发现 |
| `backend/state/MEMORY.md` | 跨 session 长期记忆 | Slow Agent 的 `write_memory` 自动维护 |

## /evolve 自动评估

5 维度（看见情绪/原因/模式/方法 + 安全边界），门槛 9.0。用模拟用户对话，自动改 SOUL/AGENTS/skills，直到全部达标。参考 `eval-reference/` 查看历史评估记录。

## 联系方式

| 姓名 | 角色 | 联系方式 |
|------|------|---------|
| 蒋宏伟 | 创始人 | 微信：请联系团队获取 |
| 张鸽 | 联合创始人 / 设计 | 微信：请联系团队获取 |
| 蒋丽园 | 心理学顾问（北大临床心理） | 微信：请联系团队获取 |
