# Program: 前端用户旅程端到端测试

通过 B/C Agent 自动化验证迁移后的全链路功能、数据契约和 AI 体验质量。

## Product Requirements

1. B Agent 模拟真实用户旅程，通过 API/Socket.IO 调用后端
2. C Agent 从前端页面代码反推数据契约，校验 B 的返回值
3. 覆盖：对话、课程、日记、关系档案、个人页
4. 不只验证"能通"，还验证 AI 回复质量（情绪命名、模式识别等 moodcoco 能力）

## Feature List

- [ ] S1: 陌生人 — 首次接触（对话 + 建档）
- [ ] S2: 初识 — 记忆与解读（跨会话记忆 + 日记）
- [ ] S3A: 熟悉/课程 — 课程完整流程
- [ ] S3B: 熟悉/模式 — 单关系模式识别
- [ ] S4: 亲密 — 跨关系模式 + "我的"页面 + 告别

## Evaluation Criteria

全部阈值 8.0，详细评分锚点见 `.evolve/eval.yml`。

| 维度 | 类型 | 说明 | 阈值 |
|------|------|------|------|
| 功能验证 | deterministic | B agent 自动打分：通过检查数/总检查数×10；检查 HTTP 200、字段完整、类型正确、ID 一致、状态持久化 | 8.0 |
| 数据正确性 | llm-judged | C agent 读前端 wxml/ts 推断字段需求，校验格式合法性 + 情绪标签/建档内容语义正确性 | 8.0 |
| 对话质量 | llm-judged | C agent 对照 AGENTS.md 评估：精准情绪命名、跨会话记忆召回、具体事件支撑的模式识别、安全边界 | 8.0 |

## Technical Constraints

- 后端：localhost:8000（psychologists `evolve/migration` 分支）
- 前端代码：psychologists/frontend/miniprogram/（只读，用于 C 校验）
- B Agent 调用方式：Socket.IO + REST API
- 不修改任何代码，纯测试验证

## Model Allocation

- O (Orchestrator): Claude Code Sonnet 4.6（本对话，轻量调度）
- B (Builder): Claude Code Sonnet subagent；重活通过 `agent -p --model claude-4.6-opus-high` 执行（Cursor Opus）
- C (Critic): Claude Code Sonnet subagent；重活通过 `agent -p --model gpt-5.4-high` 执行（Cursor GPT-5.4）

## Agent Rules

- Do not modify program.md
- Do not modify files under .claude/skills/evolve/
- B Agent 必须先读前端 service 层代码再调 API
- C Agent 必须先读前端 page/component 代码再校验
- B 的输出（API 返回值 + AI 回复）保存到 .evolve/b_output/ 目录
- C 的校验报告保存到 .evolve/c_report/ 目录
- Git commit after each agent run

## Reference

- 测试设计文档: `docs/superpowers/specs/2026-04-01-frontend-journey-test-design.md`
- 产品上下文: `docs/product/product-context.md`
- Agent 行为规范: `ai-companion/AGENTS.md`

## 双仓库

| 仓库 | 路径 | 角色 |
|------|------|------|
| psychologists | `/Users/jianghongwei/Documents/psychologists` | 后端 API + 前端代码（只读） |
| moodcoco | `/Users/jianghongwei/Documents/moodcoco` | AI companion 配置 + evolve 状态 |
