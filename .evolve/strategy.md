# Strategy

## Current Feature
S1: 陌生人 — 首次接触

## Status: FAIL → Continue（聚焦 P0 配置修复 + P1 prompt 补充）

## Execution Order
1. S1 (陌生人) — 首次对话 + 建档
2. S3A (课程) — 课程完整流程（可与 S1 并行）
3. S2 (初识) — 跨会话记忆 + 日记（依赖 S1）
4. S3B (模式) — 单关系模式识别（依赖 S1+S2）
5. S4 (亲密) — 跨关系 + 个人页 + 告别（依赖 S1-S3）

## Decision Log

### 2026-04-01 — S1 eval v1: FAIL (7/2/3, total 4.0)

**决策：Pivot（双轨修复）**

根因一：WorkspaceStorage 写入失效（P0，数据正确性 2 分）
根因二：MBTI 引导（已确认是产品功能，不计入扣分）

---

### 2026-04-01 — S1 eval v2 (MOOD session, 首次): FAIL (9/6/7, total 7.3)

**决策：Continue（聚焦 USE_OPENCLAW_CHAT 配置修复）**

#### 当前分数

| 维度 | 分数 | 阈值 | 达标 |
|------|------|------|------|
| 功能验证 | 9/10 | 8.0 | pass |
| 数据正确性 | 6/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |
| **总分** | **7.3** | - | **fail** |

#### 根因分析

**P0（数据正确性 6 分）：USE_OPENCLAW_CHAT=False**

- 后端走旧 MoodAgent 路径，workspace tool calls 根本不触发
- about_self 全 4 个 section 返回"暂无相关记忆。"
- 小白档案 text = "暂无相关记忆。"，等于未建档
- **修复**：后端 `.env` 添加 `USE_OPENCLAW_CHAT=True` → 重启服务 → 重跑 S1

修复后数据正确性预计：
- workspace 写入生效 → about_self 有内容、小白档案有条目 → 升至 8+
- 前提是 coco agent system prompt 包含 AGENTS.md 文件写入铁律（需 B Agent 确认）

**P1（对话质量 7 分）：中置信度情绪命名缺少分叉试探**

- AGENTS.md §命名vs提问决策树 §中置信度：用户说"好烦"应触发二选一试探（"你是烦他，还是更像……害怕？"）
- Turn 1 实际回复直接定性"又累又委屈"，方向正确但缺少让用户纠正的空间
- Turn 6 "太过分了" — 对不在场第三方作价值评判，轻微安全边界问题
- **修复**：检查 coco agent system prompt 是否包含中置信度处理规则 + 示例话术；补充"不对第三方行为作价值评判"的禁止示例

#### 不属于 B Agent 改进方向的已知限制

- `about_relations` 硬编码空（Memory v2 迁移中）— 产品问题，非 Agent 问题
- workspace 写入失效（USE_OPENCLAW_CHAT=False）— 测试环境配置，非代码问题

---

### 2026-04-01 — S1 eval v2 重评（C Agent 第二轮）: FAIL (9/6/7, total 7.3)

**决策：Continue**

第二轮评估结果与第一轮完全一致，确认评分准确：

| 维度 | 分数 | 阈值 | 达标 |
|------|------|------|------|
| 功能验证 | 9/10 | 8.0 | pass |
| 数据正确性 | 6/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |
| **总分** | **7.3** | - | **fail** |

#### 评分依据（已核实）

**功能验证 9 分**：
- 7/7 有效检查项全通（xiaobo_relation_type_correct 为不可测试项，从分母移除）
- about_self 内容空是已知限制，接口功能本身通达，降 1 分至 9 反映内容空对前端渲染的实质影响

**数据正确性 6 分**：
- Socket event_response 格式、AI_MESSAGE 结构、TTS URL、跨接口 ID 一致性全部合格
- workspace 写入完全失效（USE_OPENCLAW_CHAT=False），建档/记忆落地为零
- 情绪标签层次不足："委屈"反复，缺少次级情绪（无力/被忽视/寒心/自我怀疑）区分

**对话质量 7 分**：
- 情绪命名较稳定，首次接触安全边界基本守住
- 中置信度分叉试探缺失（Turn 1）
- "太过分了"轻微安全边界问题（Turn 6，对不在场第三方作价值评判）
- 连发消息合并处理正确（Turn 3-5）
- 无 MBTI 引导（0/4 轮）

#### 下一步操作（v5，B Agent 执行）

1. **P0 配置修复**：后端 `.env` 添加 `USE_OPENCLAW_CHAT=True`，重启后端服务
2. **P1 Prompt 核查**：确认 coco agent system prompt 包含：
   - AGENTS.md §文件写入铁律
   - §中置信度情绪命名规则（二选一试探话术）
   - §安全边界禁止示例（不对第三方行为作价值评判）
3. **重跑 B Agent (S1 v5)**：MOOD session，同样 7 轮对话脚本
4. **C Agent 重评 v3**：目标三维度均 >= 8.0

#### 预测 v5 结果（如修复生效）

| 维度 | 当前 v4 | 预测 v5 |
|------|---------|---------|
| 功能验证 | 9 | 9-10 |
| 数据正确性 | 6 | 8-9（workspace 写入生效后） |
| 对话质量 | 7 | 8（中置信度 prompt 补充后） |

#### 已知限制（永久注记，不计入 B Agent 改进方向）

- `about_relations` 硬编码空（Memory v2 迁移中）
- workspace 写入（配置修复后自动生效，不需要代码改动）
