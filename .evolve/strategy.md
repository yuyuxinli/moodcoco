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

---

### 2026-04-01 — S1 eval v5: FAIL (7/6/7, total 6.7)

**决策：Pivot（GATEWAY_TOKEN 根因未解，对话质量停滞，需要换方向主动解除阻断）**

#### 当前分数

| 维度 | 分数 | 阈值 | 达标 |
|------|------|------|------|
| 功能验证 | 7/10 | 8.0 | fail |
| 数据正确性 | 6/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |
| **总分** | **6.7** | - | **fail** |

独立评估器（gpt-5.4）对话质量评分：**7分**（与 C Agent 一致）

#### 根因分析

**功能验证 7 分（70% = 7/10 通过）**：
- 三个失败项：xiaobo_relation_type_correct（Memory v2 硬编码）、workspace_user_md_updated（USE_OPENCLAW_CHAT=False）、workspace_people_created（同上）
- 相比 v4（9 分），本次总检查项从 8 增加到 10（新增两个 workspace 检查），使通过率从 87.5% 降至 70%
- 7/10 通过率对应 rubric 70-80%→**7分**

**数据正确性 6 分**（与 v4 持平）：
- workspace 写入完全失效（USE_OPENCLAW_CHAT=False），about_self 全空、小白档案全空、people/ 目录不存在
- Socket event 格式合格，stream_id 跨接口一致，auth 字段完整
- 情绪标签层次不足（仅有委屈/不被理解/被忽视，缺少次级情绪：无力感/被反复否定后的失望）
- 根因：ChatProxy GATEWAY_TOKEN 问题，USE_OPENCLAW_CHAT=True 时需要 device token（不是 shared secret），B Agent 尝试 v5d7435e0 时 GATEWAY_TOKEN 为空，所有 AI 回复全部失败；c1e7530 回退到 USE_OPENCLAW_CHAT=False（旧 ChatEngine），workspace 工具调用不触发

**对话质量 7 分**（与 v4 持平）：
- 中置信度分叉试探缺失（Turn 1 "好烦"→应为"你是烦他，还是更像……害怕？"，实际给了开放式邀请）
- 安全边界轻微违规（Turn 6 "他这样真的很过分"，对不在场第三方做价值评判，AGENTS.md §2 明确禁止）
- 早给建议（Turn 3-5 末"或许可以试着告诉他"，情绪尚未稳定时给出具体行动建议）
- Turn 7 收尾仅 AI_PRAISE_POPUP，无实质回应（用户感谢后没有自然收尾）
- 连发消息处理正确（rapid_fire_merged），陪伴温度整体一致

#### ChatProxy GATEWAY_TOKEN 问题 — P0 阻断根因

- B Agent 调查发现：USE_OPENCLAW_CHAT=True 时，系统通过 ChatProxy 路由 AI 请求，需要传入 `GATEWAY_TOKEN=<device token>`，而不是普通 shared secret
- v5 (d7435e0) 尝试 USE_OPENCLAW_CHAT=True，因 GATEWAY_TOKEN 为空导致 Bearer 错误，所有 AI 回复失败
- c1e7530 被迫回退 USE_OPENCLAW_CHAT=False，workspace 工具调用随之失效
- **解决路径**：查阅 OpenClaw 官方文档（/Users/jianghongwei/Documents/GitHub/openclaw/docs/）找到 device token 获取方式

#### 轨迹分析

- v1: 4.0（基线）
- v2-v3: 7.3（两轮持平）
- v5: 6.7（下降，功能验证多了 workspace 检查项）
- 趋势：rising → flat → falling，判定 **Pivot**

#### B Agent v6 具体操作指南

**优先级 P0：解决 GATEWAY_TOKEN，让 workspace 写入生效**

1. **查阅 OpenClaw 文档，找到 device token 配置方式**：
   - 文档路径：`/Users/jianghongwei/Documents/GitHub/openclaw/docs/`
   - 重点查找：`gateway-token`、`device-token`、`auth`、`ChatProxy`、`GATEWAY_TOKEN` 等关键词
   - 目标：找到获取 device token 的正确方式（是 API 调用获取？还是管理后台生成？还是 .env 中的其他变量？）
   - 如果文档中有 `openclaw register-device` 或类似命令，尝试执行
   - 也可尝试查看 psychologists backend 代码中 ChatProxy 的 token 验证逻辑

2. **配置 GATEWAY_TOKEN 并验证**：
   - 后端 `.env`：`USE_OPENCLAW_CHAT=True` + `OPENCLAW_GATEWAY_TOKEN=<正确的 device token>`
   - 重启后端服务
   - 验证方式：发送一条测试消息，确认 workspace 目录有文件写入

3. **修复对话质量问题（P1）**：
   - 确认运行时 workspace 的 AGENTS.md（路径：`/Users/jianghongwei/Documents/psychologists/backend/ai-companion/ai-companion/AGENTS.md`）中是否包含：
     a. §1 中置信度二选一试探话术（"你是烦他，还是更像……害怕？"）
     b. §2 安全边界禁止示例（禁止"他这样真的很过分"式第三方价值评判）
     c. 情绪稳定前不给建议的规则
   - 如果运行时 AGENTS.md 与 moodcoco 源码 AGENTS.md 内容不一致（已知两者分离），B Agent 需要**同步最新内容**：`cp /Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md /Users/jianghongwei/Documents/psychologists/backend/ai-companion/ai-companion/AGENTS.md`
   - 注意：不修改源码，只更新运行时 workspace 的配置文件

4. **重跑 S1 测试（v6）**：
   - 使用同样的 7 轮对话脚本
   - 确认 workspace 写入生效（workspace_user_md_updated = true，workspace_people_created = true）
   - 目标：功能验证 ≥ 8（8/10）、数据正确性 ≥ 8（workspace 写入生效）、对话质量 ≥ 8（prompt 修复后）

#### 已知限制（永久注记，不计入 B Agent 改进方向）

- `about_relations` 硬编码空（Memory v2 迁移中，`list_relation_names()` 返回 `[]`，每日批处理任务未接入，无法通过对话修复）
- `xiaobo_relation_type_correct`：依赖 about_relations，同上，永久 FAIL
- 以上两项对应功能验证 -1 分（无法消除）
