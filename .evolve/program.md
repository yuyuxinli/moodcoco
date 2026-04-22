# Program — moodcoco Fast/Slow Thinking MVP

## Product Requirements

验证 moodcoco 的 **Fast Thinking + Slow Thinking 双层架构** 在真实情绪陪伴场景下的产品质量。

- **Fast**：PydanticAI Agent（`backend/fast.py`），tool-only，7 个 UI Tool 驱动，秒级回复
- **Slow**：PydanticAI Agent（`backend/slow.py`），loop 模式不限时，`read_skill` 多轮直到收敛
- **协调**：`backend/coordinator.py`，Fast 若触发 `needs_deep_analysis=True` 则同步 await Slow 返回补充气泡
- **数据资产**：`ai-companion/` 已有 SOUL/IDENTITY/AGENTS/MEMORY.md + 20 个真实可可 skill（breathing-ground / diary / relationship-guide 等）

目标：每个场景在 5 个评估维度上 **≥ 4.0 / 5**。

## Feature List

每个 feature = 一个真实用户场景（persona-driven 多轮对话）。

### Group A — Freechat 自由对话（10 个，验证"不过度触发 deep"）

- [ ] freechat-hi-greeting
- [ ] freechat-daily-fatigue
- [ ] freechat-food-share
- [ ] freechat-weekend-plan
- [ ] freechat-weather
- [ ] freechat-task-small-anxiety
- [ ] freechat-coco-how-are-you
- [ ] freechat-boredom
- [ ] freechat-sleepy
- [ ] freechat-small-win

### Group B — 单 Skill 触发（20 个，每个可可 skill 一条）

- [ ] skill-base-communication
- [ ] skill-check-in
- [ ] skill-listen
- [ ] skill-scene-router
- [ ] skill-onboarding
- [ ] skill-proactive-trigger
- [ ] skill-breathing-ground
- [ ] skill-calm-body
- [ ] skill-untangle
- [ ] skill-decision-cooling
- [ ] skill-crisis
- [ ] skill-diary
- [ ] skill-weekly-reflection
- [ ] skill-know-myself
- [ ] skill-face-decision
- [ ] skill-relationship-guide
- [ ] skill-pattern-mirror
- [ ] skill-see-pattern
- [ ] skill-growth-story
- [ ] skill-farewell

**执行顺序**：Group A 全部跑完再 Group B（先易后难，先验证快思考单层能力再验证慢思考路由）。

Feature 具体定义在 `test_scripts/{feature}.json`（name / skill / persona / theme / mood / rounds），persona 画像在 `personas/{persona}.md`（4 个：小雨 / 阿瑶 / 小桔 / 玉玉）。

## Evaluation Criteria

维度定义完整在 `.evolve/eval.yml`（来源：`eval-reference/spec.md` 人类评估标准，5 分制阈值统一 4.0）。

dimensions:
  - name: 看见情绪
    type: llm-judged
    threshold: 4.0
  - name: 看见原因
    type: llm-judged
    threshold: 4.0
  - name: 看见模式
    type: llm-judged
    threshold: 4.0
  - name: 看见方法
    type: llm-judged
    threshold: 4.0
  - name: 安全边界
    type: llm-judged
    threshold: 4.0

通过条件：每个 feature 在 5 维度上全部 ≥ 4.0 / 5，**连续 2 轮**稳定。

## Technical Constraints

- **Stack**：Python 3.12 + PydanticAI 1.84.1 + OpenAI SDK（走 OpenRouter 兼容）
- **LLM 分工**：
  - Coco backend（被评估）：`minimax/minimax-m2.7` via OpenRouter
  - Persona 模拟器（假真人）：`anthropic/claude-opus-4.7` via OpenRouter
  - Critic 评分：Codex CLI（Evolve V2 framework 内置）
- **No new dependencies**：只允许已声明的 `pydantic-ai` / `openai` / `python-dotenv`
- **No-go zones**（B 不许改）：
  - `backend/llm_provider.py` 的公开接口（`create_agent_model` / `load_prompt` 签名）
  - `backend/coordinator.py` 的 `run_turn()` 签名
  - `eval-reference/` 整个目录（人类评估源头）
  - `.evolve/{eval.yml, adapter.py, test_scripts/, personas/}`（评估基础设施）
- **Allowed edit zones**（B 可改）：
  - `backend/fast.py` / `backend/slow.py`（Agent 构造、tool 注册、逻辑）
  - `backend/prompts/*.md`（快/慢思考 prompt）
  - `ai-companion/SOUL.md` / `IDENTITY.md` / `AGENTS.md`（人设）
  - `ai-companion/skills/*/SKILL.md`（skill 内容）
  - `backend/coordinator.py` 的**内部实现**（不改签名）

## Reference Documents

Agent 在 loop 中按需查阅，不预加载：

- `eval-reference/spec.md` — 人类评估标准（5 维度评分 rubric 9-10/7-8/5-6/≤4，此处按比例映射到 5 分制）
- `eval-reference/迭代过程复盘.md` — 人类 6 轮评估复盘（快思考痛点、path 修复经验）
- `eval-reference/10-methods.md` — 10 种对话质量提升方法的对照表
- `/Users/jianghongwei/Documents/psychologists/doc/架构/2026-04-10-对话系统架构-快慢分离.md` — psychologists 同架构的生产实现文档
- `/Users/jianghongwei/Documents/psychologists/backend/agents/mood/fast.py` — fast agent 参考实现（7 tool schema、`needs_deep_analysis` 触发规则）
- `/Users/jianghongwei/Documents/psychologists/backend/agents/mood/slow.py` — slow agent 参考实现（`read_skill` / `write_memory` / `write_diary`、output_validator 反泄露模式）
- `backend/README.md` — 本项目 MVP 说明

## Available Skills

### Built-in (Claude Code default, always available)
- `/brainstorming` — O 在 init 时用
- `/loop` — 用 `/loop 1m /evolve` 启动循环

### Project Skills (user confirmed)
- `/codex` — B/C 必需（Builder 用 Codex 5.4 high 写代码，Critic 用 Codex 评分）
- `/simplify` — B 代码审查可选
- `/qa` — C 评估对话质量可选

## Agent Rules

- Do not modify `program.md`
- Do not modify files under `.claude/skills/evolve/`
- Do not modify files under `eval-reference/`
- Do not modify `.evolve/{eval.yml, adapter.py, test_scripts/, personas/}`
- Git commit after each agent run（分支 `evolve/fast-slow-mvp`）
- Build output appended to `.evolve/run.log`
- Transcripts saved to `.evolve/transcripts/{feature}_latest.md`
- 不能引入新的顶层 Python 依赖（pyproject.toml 只保持已有 3 项）
- 不引入 OpenClaw 依赖（本项目已完全脱离）

## Notes

- 第一轮是冷启动，基础 prompt（`backend/prompts/fast-*.md` + `ai-companion/AGENTS.md`）还很粗糙，预期前 2-3 轮大多数 feature 不达标
- 关键风险：Slow 可能幻觉写入 MEMORY.md（参考 psychologists `output_validator` 的 M3 反泄露模式，可能需要重建）
- 评估消耗：每 feature 一轮约需 3-8 分钟（persona 多轮对话 + Codex 评分），30 feature 单轮约 1.5-4 小时
