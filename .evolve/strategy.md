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

---

### 2026-04-01 — S1 eval v6: FAIL (7/5/7, total 6.3)

**决策：Decompose（workspace 写入阻断根本未解决，需要拆解子任务单独攻坚）**

#### 当前分数

| 维度 | 分数 | 阈值 | 达标 |
|------|------|------|------|
| 功能验证 | 7/10 | 8.0 | fail |
| 数据正确性 | 5/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |
| **总分** | **6.3** | - | **fail** |

独立评估器（gpt-5.4）对话质量评分：**6分**（低于 C Agent 自评 7 分，主因 JSON 格式污染 + 结尾温度不足）

#### 轨迹分析

- v1: 4.0（基线）
- v2-v3: 7.3（两轮持平）
- v5: 6.7（首次下降）
- v6: 6.3（继续下降）
- 趋势：rising → flat → falling → falling，判定 **Decompose**

#### 根因分析

**功能验证 7 分（与 v5 持平，70% = 7/10）**：
- P0 依然未修复：workspace_user_md_updated = false，workspace_people_created = false
- workspace_user_md_mtime = 1774938869（约18小时前），不是本次测试时间（1775028103），说明 B Agent 的 GATEWAY_TOKEN 修复在 v6 依然未生效
- 三个 FAIL 项：xiaobo_relation_type_correct（永久）+ 两个 workspace 检查项（P0 阻断）

**数据正确性 5 分（下降 1 分，v5 也是 6 分）**：
- workspace 全空，与 v5 相同
- 新增严重问题：Turn 3-5 ai_responses 中出现 JSON 格式污染，`{"content_type": "AI_MESSAGE", "messages": [...]}` 字符串被直接拼入用户可见回复文本，数据污染属于格式错误
- about_self 全4个 section 依然"暂无相关记忆。"

**对话质量 7 分（与 v5 持平）**：
- 改善：Turn 6 安全边界大幅改善（v5 "他这样真的很过分" → v6 执行 AGENTS.md §0.5 人名消歧"你说的小白，是男朋友小凯吗？"），正确
- 仍然存在：Turn 1 中置信度规则未执行（"好烦"→应为二选一试探，实际给时态询问"吵完了还是正在吵？"）
- 仍然存在：Turn 2 开放式问句（"他这么说，你什么感觉？"），情绪命名缺位
- 仍然存在：Turn 7 结尾温度不足（"不客气。下次烦的时候再来。"）
- JSON 格式污染对话质量影响较小（Turn 3-5 实际情绪内容正确），不额外扣分

#### P0 阻断根因——workspace 写入 (B Agent v6 报告 8ba44ee)

根据 B Agent v6 提交记录，B Agent 声称已修复 GATEWAY_TOKEN 并设置 USE_OPENCLAW_CHAT=True，但 workspace_user_md_mtime 时间戳显示文件未更新。可能根因：
1. B Agent 修复了代码但后端服务未重启生效
2. GATEWAY_TOKEN 值配置错误（仍然是空或错误值）
3. chat_proxy.py 中 x-openclaw-scopes 头仍有问题（v6 提交显示已添加但效果待验证）
4. workspace 路径配置错误（文件写入了错误位置）

#### B Agent v7 具体操作指南

**优先级 P0：直接验证并修复 workspace 写入**

1. **验证当前 workspace 写入状态**：
   - 直接检查后端 .env：`cat /Users/jianghongwei/Documents/psychologists/backend/.env | grep -E "USE_OPENCLAW|GATEWAY"`
   - 查看运行中进程：`ps aux | grep uvicorn`
   - 发送一条测试消息，在后端日志中确认是否有 workspace tool call 触发

2. **定位 JSON 格式污染根因**：
   - 检查 run_s1_v6.py 中 Turn 3-5 回复解析逻辑：ai_responses 中为什么 JSON 字符串会混入用户可见文本
   - 可能是 ChatProxy 返回 AI_MESSAGE 格式但解析器将整个 JSON 字符串当成文本拼接
   - 修复：在解析 ai_responses 时，如果内容是 JSON 格式，提取 `messages` 数组而不是返回原始字符串

3. **修复对话质量问题（P1）**：
   - Turn 1 中置信度二选一试探：确认运行时 AGENTS.md 中 §1 命名vs提问决策树是否存在于运行时 workspace
   - 路径：检查 `/Users/jianghongwei/Documents/psychologists/backend/ai-companion/ai-companion/AGENTS.md` 是否包含"中置信度：二选一试探，用省略号制造停顿"规则
   - Turn 7 结尾：在 AGENTS.md 的对话风格章节添加"对话自然结束时，给出有温度的收尾（如'好好休息，有什么随时来'），不能只说'不客气'"

4. **重跑 S1 测试（v7）**：
   - 确认后端服务已重启（workspace 写入才能生效）
   - 目标：功能验证 ≥ 8（workspace 两项 FAIL 修复）、数据正确性 ≥ 8、对话质量 ≥ 8

#### 已知限制（永久注记，不计入 B Agent 改进方向）

- `about_relations` 硬编码空（Memory v2 迁移中）
- `xiaobo_relation_type_correct`：依赖 about_relations，同上，永久 FAIL
- 以上两项对应功能验证 -1 分（无法消除）

---

### 2026-04-01 — S1 eval v7: FAIL (7/6/7, total 6.7)

**决策：Force-Write（绕过模型判断，强制在对话结束时触发 workspace 写入）**

#### 当前分数

| 维度 | 分数 | 阈值 | 达标 |
|------|------|------|------|
| 功能验证 | 7/10 | 8.0 | fail |
| 数据正确性 | 6/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |
| **总分** | **6.7** | - | **fail** |

#### 轨迹分析

- v1: 4.0（基线）
- v2-v3: 7.3（两轮持平）
- v5: 6.7（首次下降）
- v6: 6.3（继续下降）
- v7: 6.7（轻微回弹，JSON 污染修复贡献 +0.4，但未突破 7.3 平台）
- 趋势：rising → flat → falling → falling → slight_rebound，判定 **Force-Write**

#### 根因分析

**功能验证 7 分（与 v5/v6 持平，70% = 7/10）**：
- workspace_user_md_mtime 早于测试 15.7 小时 → 本次测试模型完全未写入
- people_files = [] → people/小白.md 未创建
- memory_recent_writes = [] → memory/ 无任何写入
- 三个 FAIL 项：xiaobo_relation_type_correct（永久）+ workspace 两项（模型行为）

**数据正确性 6 分（从 v6 的 5 分回弹 +1）**：
- conversations 字段 JSON 污染消除（修复生效，+1）
- workspace 仍全空（主要扣分，about_self 四 section 全"暂无相关记忆"）
- stream_id 异化：Turn 3-5 出现 mood_msg 前缀 ID（非 session_id），轻微不一致
- 情绪标签层次不足：全对话仅"无力"1 个次级情绪词

**对话质量 7 分（与 v5/v6 持平）**：
- 改善：Turn 6 人名消歧正确执行（§0.5 合规）；Turn 7 结尾温度微改善
- 持续问题：Turn 1 中置信度二选一试探第 4 次未执行（"好烦"→"嗯，吵完了？"而非"你是烦他，还是更像……害怕？"）
- 持续问题：Turn 7 告别后无文件写入（AGENTS.md §对话结束时铁律违反）
- 持续问题：Turn 7 收尾无具体细节回指（§3 收尾锚点规则违反）

#### workspace 写入问题 — 根因确认

**根因：模型行为问题（不执行 tool call），非配置问题**

证据链：
1. AGENTS.md 已同步（runtime == source，1682 行）→ 规则存在
2. 告别语"谢谢你"在 Turn 7 出现 → 触发条件满足
3. workspace 无任何写入 → 模型知道规则但未执行
4. 连续 v4/v5/v6/v7 均未执行 → 模型在告别场景稳定地跳过 tool call

**三条备选方向评估**：

| 方向 | 描述 | 评估 |
|------|------|------|
| A：强化 AGENTS.md 文字 | 改措辞、加示例、加警告符号 | 已试过（v6→v7 AGENTS.md 同步后无改善），边际收益极低 |
| B：运行时 system prompt 插入显式指令 | 在每次告别检测后注入 tool call 指令 | 需要后端 hook，有效但改动范围大 |
| **C：后端强制触发写入** | 对话结束时后端主动调用 workspace 写入 API，不依赖模型判断 | **推荐**：最可靠，绕过模型不确定性，产品级保证 |

**决策：方向 C（后端强制写入）为主，方向 B（system prompt 插入）为辅**

理由：模型在告别场景连续 4 次跳过 tool call，说明文字层面的 prompt 工程已达天花板。需要从架构层面保证写入，而不是继续依赖模型理解规则后自愿执行。

#### B Agent v8 具体操作指南

**优先级 P0：后端强制 workspace 写入（方向 C）**

1. **定位对话结束检测点**：
   - 查找后端处理 Socket.IO 消息的位置（`psychologists/backend/`）
   - 找到消息处理完成后的 hook 点（`event_processing_end` 触发后）
   - 在此 hook 中：检测消息是否含告别词（"谢谢""再见""拜拜""晚安""好了"+"谢谢"组合）

2. **实现后端强制写入逻辑**：
   - 告别检测命中时 → 主动调用 workspace API：
     a. 读取当前 session 的对话记录
     b. 提取本次对话中出现的人名（从对话记录搜索）
     c. 调用 workspace write：创建/更新 `people/{人名}.md`（如果对话中确认了新人物）
     d. 调用 workspace write：更新 `USER.md`（追加本次情绪事件摘要）
   - 不依赖模型判断，后端直接执行

3. **备选方向 B：system prompt 强制插入**（如果 C 实现周期太长）：
   - 在 `event_processing_end` 检测到告别词后，下一次模型调用时在 system prompt 末尾追加：
     ```
     ⚠️ 检测到告别语。你的下一条回复必须包含至少一个 write tool call。
     必须写入：
     - write("people/小白.md", ...) — 创建小白档案（如果本次对话中确认了身份）
     - edit("USER.md", ...) — 追加本次情绪事件
     如果你没有在本轮回复中调用 write/edit，将触发后端补偿写入。
     ```

4. **修复对话质量 P1：中置信度二选一试探**（连续 4 次 FAIL，需要在运行时 workspace AGENTS.md 再次强化）：
   - 在 §1 情绪命名部分，在"中置信度"规则前加红色警告（强调级别）：
     ```
     ⛔⛔ 当用户说"好烦""烦死了""真的很烦"时，禁止用"你很烦"或时态确认作为第一句话。
     必须用：二选一试探 + 省略号。
     错误示例（禁止）："嗯，吵完了？" / "发生什么了？" / "你怎么了？"
     正确示例（必须）："你是烦他，还是更像……害怕？" / "那种烦，是生气，还是更像……委屈？"
     ```
   - 路径：`/Users/jianghongwei/Documents/psychologists/backend/ai-companion/ai-companion/AGENTS.md`

5. **修复对话质量 P2：告别收尾具体细节回指**（§3 规则）：
   - 在 AGENTS.md §3 收尾锚点规则处追加：
     ```
     ⛔ 禁止通用告别："好点了就好。有不舒服的时候随时来。"（没有任何具体内容）
     正确示例："好一点了就好。你跟小白说的那些话，我记住了。有不舒服随时来。"
     规则：告别回复必须包含至少一个具体细节（人名/事件/情绪词）。
     ```

6. **重跑 S1 测试（v8）**：
   - 验证方式：检查 workspace_people_created = true（people/小白.md 存在）
   - 目标：功能验证 ≥ 8（workspace 两项修复）、数据正确性 ≥ 8（写入生效 + 情绪标签改善）、对话质量 ≥ 8（中置信度 + 收尾细节）

#### 对话质量停滞分析（连续 4 版本 7 分）

中置信度二选一试探连续 4 次（v4/v5/v6/v7）未执行，说明：
1. 规则存在于 AGENTS.md，但模型在该场景下有稳定的"绕过"行为（时态确认问句 vs 二选一试探）
2. 文字强化已不足够，需要 few-shot 示例 + 反例（明确"不能用时态确认作为第一句"）
3. 对话质量瓶颈在于：Turn 1 中置信度 + Turn 7 收尾细节，两者均需 few-shot 级别干预

#### 已知限制（永久注记，不计入 B Agent 改进方向）

- `about_relations` 硬编码空（Memory v2 迁移中）
- `xiaobo_relation_type_correct`：依赖 about_relations，同上，永久 FAIL
- 以上两项对应功能验证 -1 分（无法消除）
- 功能验证最高可达 9 分（非 10 分），总分上限受此限制

---

### 2026-04-01 — S1 eval v8: FAIL (9/7/7, total 7.7)

**决策：Continue（聚焦 Turn 1 空回复根因 + 对话质量最后一公里）**

#### 当前分数

| 维度 | 分数 | 阈值 | 达标 |
|------|------|------|------|
| 功能验证 | 9/10 | 8.0 | **pass** ✓ |
| 数据正确性 | 7/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |
| **总分** | **7.7** | - | **fail** |

独立评估器（gpt-5.4）对话质量评分：**4分**（Turn 1 空回复被视为完全失接，扣分严重）

#### v8 重大突破

- **workspace 写入终于生效**（连续 5 个版本失败后首次 PASS）
  - workspace_user_md_updated = PASS（mtime 在测试期间内，+132 秒写入）
  - workspace_people_created = PASS（people/小白.md 已创建，有实质内容）
  - RULE-ZERO 注入生效：B Agent 在 AGENTS.md 顶部注入强制写入规则，模型遵从
- **功能验证首次达到 9 分**（超越阈值 8.0）
- 轨迹首次突破 7.3 平台：7.7 是历史最高分

#### workspace 写入内容质量

`people/小白.md`（已创建）内容评估：
- 基本信息：称呼/关系/关系阶段 — 完整 ✓
- 当前状态：今天吵架 — 有记录 ✓
- 关键事件：2026-03-31 吵架，「太敏感」事件 — 有记录 ✓
- 感受：「觉得他不考虑自己的感受」— 有记录 ✓
- 缺失：情绪轨迹（无力/委屈/被忽视层次）、退出信号、跨关系匹配 — 空白

整体：有实质内容，但属于最简版本，情绪叙事层次不足。

#### 根因分析

**功能验证 9 分（首次达标，90% = 9/10）**：
- workspace 两项修复生效（方案 B：RULE-ZERO 注入）
- 唯一 FAIL：xiaobo_relation_type_correct（永久约束，about_relations 批处理 API）

**数据正确性 7 分（+1 分，从 v7 的 6 分提升）**：
- workspace 写入生效，小白.md 有基础内容（+1）
- about_self 全 4 个 section 仍为「暂无相关记忆」（批处理 API，已知约束，-1）
- 情绪标签层次有改善（生气/委屈/无力 3 层），但仍不够丰富（缺失：被忽视/被否定感/失望）
- stream_id 在 Turn 3-5 出现 mood_msg 前缀（轻微不一致）
- 无 JSON 格式污染（v7 修复持续生效）
- 扣分原因：数据正确性距 8 分差距在于「建档内容完整度」和「情绪标签层次」

**对话质量 7 分（与 v5/v6/v7 持平）**：
- 改善：workspace 写入 RULE-ZERO 生效（告别后实际执行了写入）
- 改善：Turn 6 人名消歧连续两版正确执行
- 持续问题：Turn 1 中置信度二选一试探第 5 次未执行（「好烦」→ 空回复）
  - 重要发现：Turn 1 socket_events 中 count=1 的 event_processing_end 没有对应 event_response，说明系统未触发模型返回 AI_MESSAGE，可能是 Socket 连接刚建立 + Turn 1 特殊路由逻辑导致
  - 独立评估器（gpt-5.4）将此视为「完全失接」，给出 0/10，导致总评 4 分
  - 需要 B Agent 调查 Turn 1 无回复的技术根因
- 持续问题：Turn 7 收尾无具体细节回指（「那就好。今天的事记下来了」—— 没有提「小白」或「太敏感」具体事件）
- Turn 3 中「他总这样确实挺让人头疼」有轻微站队，但未到安全边界违规级别

#### 轨迹分析

- v1: 4.0（基线）
- v2-v3: 7.3（两轮持平）
- v5: 6.7（首次下降）
- v6: 6.3（继续下降）
- v7: 6.7（轻微回弹）
- **v8: 7.7（首次突破历史最高，+1.0，决策：Continue）**
- 趋势：rising → flat → falling → falling → slight_rebound → **breakthrough**

#### B Agent v9 具体操作指南

**P0：调查并修复 Turn 1 空回复**

1. **调查 Turn 1 为何无 AI 文字回复**：
   - v8 数据显示 Turn 1 的 `ai_response = ""`，对应 socket_events 中只有 count=1 的 event_processing_end，无 event_response
   - 可能原因：
     a. 后端处理 Turn 1（第一条消息）走了不同的路由（初始化路由，不触发 AI 回复）
     b. Socket 建立后的 Turn 1 消息被系统静默处理（greeting 逻辑）
     c. 测试脚本 Turn 1 消息发送时机太早（连接建立后立即发，未等 server ready）
   - 调查方法：检查后端 Socket.IO message handler 的 Turn 1 特殊处理逻辑
   - 如果是产品设计（Turn 1 会触发 greeting 流程而非 AI 回复），需在 B Agent 测试脚本中等待 greeting 完成后再发第一条用户消息

2. **修复对话质量 P1：Turn 1 中置信度二选一试探**：
   - 如果 Turn 1 空回复是技术问题（可修复），则修复后此问题自动解决
   - 如果是产品设计（greeting 覆盖），则在 AGENTS.md 中补充：greeting 结束后用户第一条消息必须触发中置信度规则

3. **修复对话质量 P2：Turn 7 收尾具体细节回指**（§3 规则，已连续违反）：
   - 在 AGENTS.md §RULE-ZERO 的「告别文字」部分，添加强制约束：
     ```
     ⛔ 告别文字必须包含至少一个具体细节（人名/事件/情绪词）。
     错误示例（禁止）：「那就好。今天的事记下来了，有需要随时来。」（无具体细节）
     正确示例（必须）：「好一点了就好。你说的那句'太敏感'，我记住了。有需要随时来找我。」
     ```

4. **提升数据正确性：增强 workspace 写入内容质量**：
   - 当前 people/小白.md 是最简版本，情绪叙事层次不足
   - 在 AGENTS.md RULE-ZERO 的写入规范中，添加情绪层次要求：
     ```
     写入 people/{人名}.md 时，必须包含：
     - 本次对话中识别到的情绪层次（表层+深层，如：表层=生气，深层=委屈/被忽视）
     - 关键事件的情感色彩（不只是事件本身）
     ```

5. **重跑 S1 测试（v9）**：
   - 目标：功能验证 9（保持）、数据正确性 ≥ 8（workspace 内容增强）、对话质量 ≥ 8（Turn 1 修复 + Turn 7 细节）

#### C Agent 注记：Turn 1 空回复影响评估

v8 数据中 Turn 1 的 `ai_response = ""`（空）是本轮最大争议点：
- gpt-5.4 将此视为模型「完全没接住」，总评 4 分
- C Agent 认为可能是系统路由问题（非模型行为），给出对话质量 7 分
- 两者差异反映了评估方法的不同视角（用户体验视角 vs 技术分析视角）
- 无论根因如何，用户在 Turn 1 没有收到回复是真实的 UX 问题，必须修复

#### 已知限制（永久注记，不计入 B Agent 改进方向）

- `about_relations` 硬编码空（Memory v2 迁移中）
- `xiaobo_relation_type_correct`：依赖 about_relations，同上，永久 FAIL
- `about_self` 全 4 个 section 为空：批处理 API，每日任务，非实时，非对话可修复
- 以上限制对应功能验证 -1 分、数据正确性 -0.5 至 -1 分（无法消除）

---

### 2026-04-01 — S1 eval v9: FAIL (9/7/7, total 7.7)

**决策：Continue（聚焦 T7 空回复新 P0 + 数据正确性最后一公里）**

#### 当前分数

| 维度 | 分数 | 阈值 | 达标 |
|------|------|------|------|
| 功能验证 | 9/10 | 8.0 | **pass** ✓ |
| 数据正确性 | 7/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |
| **总分** | **7.7** | - | **fail** |

独立评估器（gpt-5.4）对话质量评分：**6分**（T7 空回复 + T6 消歧被判为"忘了上下文"）

#### v9 新突破

- **T1 中置信度二选一试探首次成功执行**（连续 6 次失败后首次 PASS）
  - v8 Turn 1 空回复根因修复生效（连接建立后 content 空时继续等待）
  - 实际回复："吵架之后那种烦，真的挺难受的。\n\n你是生气多一点，还是更像……委屈？"
  - 符合 AGENTS.md 中置信度规则：共情承接 + 二选一试探
- **T2 追问有层次**：抓"每次"重复，二选一分叉（"不觉得你该有" vs "不该这样"）
- **小白.md 情绪轨迹新增层次**：记录"表面是生气，底下藏着委屈"，比 v8 更丰富

#### 新 P0 问题：T7 AI 文字回复为空

**根因分析**：
- RULE-ZERO 写入逻辑生效（workspace_mtime = T7 消息发出后 38 秒写入）
- 但 AI 收尾文字未生成（T7 ai_response = ""）
- 模式：RULE-ZERO 拦截了 tool call 但后续的文字回复生成流程未触发（或超时被截断）
- 直接结果：用户说"谢谢你"，AI 无任何文字回应 — 用户体验断层

**影响**：
- 对话质量：T1 改善 +0.5，T7 空回复 -0.5，净结果持平（7 分）
- 独立评估器降至 6 分（T7 空回复在用户体验视角判为严重失接）

#### 数据正确性 7 分（与 v8 持平）

- 小白.md 内容比 v8 丰富（有情绪轨迹分层），但 about_self / about_relations_xiaobo 均显示"暂无相关记忆"
- API 端 about_relations_xiaobo.text 为空（批处理约束）— 即使 workspace 写入了小白.md，API 返回仍空
- 距 8 分差距：需要情绪标签达到 4-5 种次级情绪 + 建档内容完整

#### 轨迹分析

- v1: 4.0（基线）
- v2-v3: 7.3（两轮持平）
- v5: 6.7（首次下降）
- v6: 6.3（继续下降）
- v7: 6.7（轻微回弹）
- v8: 7.7（首次突破，workspace 写入生效）
- **v9: 7.7（持平，T1 修复与 T7 新问题抵消）**
- 趋势：rising → flat → falling → falling → slight_rebound → breakthrough → **plateau**

#### B Agent v10 具体操作指南

**P0：修复 T7 空回复（RULE-ZERO 写入后告别文字未生成）**

1. **调查 T7 空回复根因**：
   - RULE-ZERO 写入在 38 秒后完成，但 AI 文字回复为空
   - 可能原因：
     a. RULE-ZERO tool call 执行期间模型认为"任务完成"，不再生成文字
     b. event_processing_end 在 tool call 完成后触发，但 B Agent 测试脚本在此时截断了等待
     c. 后端在 RULE-ZERO 写入后需要额外的触发才能生成收尾文字
   - 调查方法：检查 T7 的 socket_events，看 workspace write 之后是否有新的 event_response 未被捕获
   - 如果是测试脚本截断：延长 T7 等待时间（当前可能过短）

2. **修复 AGENTS.md：告别文字与 tool call 顺序强制分离**：
   - 在 RULE-ZERO 写入规则末尾添加：
     ```
     ⛔ 文件写入和告别文字是两个独立步骤：
     步骤 1：执行 tool call（write/edit）
     步骤 2：（tool call 完成后）生成告别文字
     告别文字不能为空字符串，哪怕 tool call 刚刚执行完。
     ```

3. **提升数据正确性：情绪标签层次**（距 8 分主要差距）：
   - 当前 people/小白.md 情绪层次有改善（生气/委屈），但缺少：无力感/被忽视/被否定/寒心
   - 在 AGENTS.md RULE-ZERO 写入规范中强化情绪标签要求：
     ```
     情绪轨迹写法（必须包含表层+深层+复合描述）：
     - 表层：[用户明确表达的情绪词]
     - 深层：[AI 在对话中引导出来的更深情绪]
     - 复合：[两者关系，如"表面是X，底下藏着Y"]
     ```

4. **重跑 S1 测试（v10）**：
   - 目标：功能验证 9（保持）、数据正确性 ≥ 8、对话质量 ≥ 8（T7 空回复修复）

#### 已知限制（永久注记，不计入 B Agent 改进方向）

- `about_relations` 硬编码空（Memory v2 迁移中）
- `xiaobo_relation_type_correct`：依赖 about_relations，同上，永久 FAIL
- `about_self` 全 4 个 section 为空：批处理 API，每日任务，非实时，非对话可修复
- 以上限制对应功能验证 -1 分、数据正确性 -0.5 至 -1 分（无法消除）
