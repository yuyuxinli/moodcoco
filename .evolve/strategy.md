# Strategy

## Current Feature
S1: 陌生人 — 首次接触

## Status: FAIL → Pivot

## Execution Order
1. S1 (陌生人) — 首次对话 + 建档
2. S3A (课程) — 课程完整流程（可与 S1 并行）
3. S2 (初识) — 跨会话记忆 + 日记（依赖 S1）
4. S3B (模式) — 单关系模式识别（依赖 S1+S2）
5. S4 (亲密) — 跨关系 + 个人页 + 告别（依赖 S1-S3）

## Decision Log

### 2026-04-01 — S1 eval: FAIL (7/2/3, total 4.0)

**决策：Pivot（双轨修复）**

#### 根因一：WorkspaceStorage 写入失效（P0，数据正确性 2 分）

AI 生成了完整对话内容，但**没有任何 WorkspaceStorage 写入发生**。`about_self` 全空，`about_relations` 空列表，小白档案为占位符。

可能根因：
1. AI 的 system prompt / skill 没有包含建档写入指令（最可能）
2. Session create 返回 201 而非 200 → B Agent 使用随机 UUID → 写入定向到不存在的工作区

**修复方向**：
- 检查 `openclaw.json` → coco agent 的 system prompt 是否包含 AGENTS.md 中的文件写入规则（§文件写入铁律）
- 检查 OpenClaw workspace 配置是否正确绑定了 `ai-companion/` 目录作为工作区
- 检查 `/api/sessions` 接口：201 是否是正常的"已创建"语义（而非错误），B Agent 是否应接受 201

#### 根因二：AI system prompt 是错误的产品（P1，对话质量 3 分）

每一轮 AI 回复均以 MBTI 引导结束（Turn 1-7 全覆盖），完全不符合 AGENTS.md 的情绪陪伴路由规则。这是系统性行为，不是偶发错误。

**修复方向**：
- 检查 `openclaw.json` → coco agent 的 `system_prompt` 或 `skills` 配置
- 确认加载的是 `ai-companion/AGENTS.md`，而非某个 MBTI/课程产品的 prompt
- 如果 system prompt 正确，则检查 model 是否在 prompt 中泄漏了 MBTI 训练偏好（换 `minimax-m2.7` 重跑）

#### 下一步操作（有序执行）

1. **检查 openclaw.json** — 确认 coco agent 配置中 system_prompt 来源和 workspace 路径
2. **检查 /api/sessions 语义** — 201 是否合法，B Agent 脚本是否误判
3. **修复 system prompt** — 确保 AGENTS.md 内容完整注入（重点：§文件写入铁律 + §情绪事件路由）
4. **重跑 B Agent (S1)** — 验证修复效果
5. **C Agent 重评** — 三维度是否达到阈值（功能验证 ≥8, 数据正确性 ≥8, 对话质量 ≥8）
