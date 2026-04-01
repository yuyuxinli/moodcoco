# S1 评估报告 v2（基于 v4 MOOD session 数据）

## 数据契约分析

### 前端 Socket.IO 解析流程

读取 `/services/chatSocketIO.ts` 关键逻辑：

**`event_response` 事件解析路径**：
1. 前端监听 `event_response` → 调用 `handleEventResponse(data)`
2. 提取 `payload.stream_type` 判断类型
3. `stream_type === 'content'`：提取 `stream_data`，解析 JSON，检测 `content_type`
4. 若 `parsedContent.content_type === 'AI_MESSAGE'`：提取 `messages` 数组，触发 `onEventResponse` 回调，传入 `parsedContent` 和 `enhancedMetadata`（含 `content_type: 'AI_MESSAGE'`, `messages: [...]`）
5. `stream_type === 'sentence_audio'`：触发 `onEventResponse`，metadata 含 `{ stream_type: 'sentence_audio', audio_url, sentence_index }`

**前端渲染字段需求（来自 about-me/index.ts）**：
- 关系列表渲染：调用 `api.getAboutRelations()` → 读取 `response.data.relations[]` → 每项需 `name`（字符串），用于构建 tab key
- 自我信息渲染：需 `sections.my_now/my_future/my_story/my_core`，每项有 `text` 和 `memory_ids`

**v4 数据是否符合前端契约**：
- `event_response` 结构 OK：`stream_id`（UUID）、`stream_type`（content/sentence_audio）、`data_preview`（有效 JSON）全部符合前端解析期望
- `AI_MESSAGE` 格式 OK：`content_type + messages[]` 结构完整，前端 `extractTextContent()` 可正常提取
- TTS 音频 URL OK：OSS 签名 URL 格式（含 `Expires/OSSAccessKeyId/Signature`），前端直接透传 `audio_url`
- `about_self` 结构 OK：4 个 section 字段存在，但 `text = "暂无相关记忆。"`（已知限制）
- `about_relations` 结构 OK：`data.relations = []`（硬编码空，已知限制）

---

## 评分

| 维度 | 分数 | 阈值 | 是否达标 |
|------|------|------|---------|
| 功能验证 | 9/10 | 8.0 | pass |
| 数据正确性 | 6/10 | 8.0 | fail |
| 对话质量 | 7/10 | 8.0 | fail |

### 维度 1：功能验证 — 9/10

**有效检查项（去掉硬编码空的 xiaobo_relation_type_correct）：7 项**

| 检查项 | 结果 |
|--------|------|
| auth_200 | PASS |
| socket_connected | PASS |
| ai_reply_received | PASS |
| about_self_200 | PASS（内容空，已知限制） |
| about_relations_200 | PASS（内容空，已知限制） |
| xiaobo_profile_found | PASS |
| rapid_fire_merged | PASS |

7/7 = 100%，按 eval.yml rubric 对应 10 分。但 `about_self` 全部 section 返回"暂无相关记忆。"，功能接口通了但内容为空，意味着用户个人页无法展示任何记忆内容——这是 USE_OPENCLAW_CHAT=False 导致的已知限制，功能通达但实际用户价值为零。**综合给 9 分**（功能全通但内容空对前端渲染有实质影响）。

### 维度 2：数据正确性 — 6/10

**可验证项**：

| 验证项 | 结果 |
|--------|------|
| Socket event_response 格式 | OK 符合前端解析契约 |
| AI_MESSAGE content_type + messages[] | OK 结构完整，类型正确 |
| TTS URL 格式 | OK 合法 OSS 签名 URL |
| stream_id UUID 格式 | OK 全程一致 |
| user_id 跨接口一致 | OK（71127ab9… 全程不变） |
| session_id 跨接口一致 | OK（a9ce952f… 全程不变） |
| about_self 结构 | OK 字段存在，内容空（已知限制） |
| 情绪标签精准度 | 部分（主要用"委屈"，缺少层次） |

**不可验证项（已知限制）**：
- workspace 写入（USE_OPENCLAW_CHAT=False）
- 关系类型（about_relations 硬编码空）
- 人物档案建档内容

**评分依据**：
- 格式层面无任何错误，跨接口 ID 一致
- workspace 全部写入失效 → 用户旅程数据完全没有落地
- 情绪标签 "委屈" 反复出现（Turn 1/2/3-5/6），缺少次级情绪区分（无力/被忽视/自我怀疑/寒心）
- 数据可格式解析，但业务价值数据（建档/记忆写入）因配置问题全部缺失

参照 eval.yml rubric 第 6 条："数据质量中等：字段完整，格式基本合法；情绪标签能区分主要类别，但层次不够细；跨接口 ID 全程一致"

**给 6 分**（格式数据质量中等；workspace 写入失效是配置问题，按已知限制处理，但其影响已反映在建档内容维度上）

### 维度 3：对话质量 — 7/10

**逐轮分析**：

**Turn 1**："我刚跟男朋友吵了一架，好烦"
- 情境判断：中置信度（有具体事件"吵架"，但情绪词"好烦"模糊）
- AGENTS.md §中置信度：应触发"二选一试探"，如"你是烦他，还是更像……害怕？"
- 实际回复："吵架真的特别消耗人，你现在肯定又累又委屈吧"
- 问题：直接定性为"又累又委屈"，方向基本正确，但未给用户纠正空间，违反中置信度分叉原则

**Turn 2**（TTS 回复文字）："被说敏感的时候，肯定特别委屈吧 / 明明只是在意细节，却被当成小题大做 / 这种不被理解的感觉真的糟透了"
- 情绪命名：命名了"委屈"+"不被理解"，精准度中等
- 遗漏："他说我太敏感了" 含有轻度自我怀疑信号（用户开始内化对方评价），AGENTS.md §自我怀疑的特殊处理要求第 1 次时温和纠正，此处未命名自我怀疑本身

**Turn 3-5（连发合并）**：
- 合并处理 OK（AGENTS.md §节点A消息缓冲策略执行正确）
- 响应1："换作是我，我也会气炸的！/ 明明是他没接住你的情绪" — 共情有力
- 响应2："这种每次都被误解的感觉，真的无力又委屈。/ 你其实只是想被他看见你的情绪，对不对？" — 核心诉求识别好，"对不对？"有轻微替用户定论之感

**Turn 6**："小白就是这样，从来不考虑我的感受"
- AGENTS.md §0.6：触发退出信号（"不考虑我的感受"），应先执行跨关系快速扫描
- 实际：未执行跨关系扫描（属首次接触，people/ 无历史数据，扫描结果为空，可接受）
- 安全边界问题：回复结尾"太过分了" — 对不在场的人(小白)的行为作价值评判，轻微越界（AGENTS.md 安全边界：不对不在场的人做动机判断；此处虽非动机判断，但评判对方行为为"太过分"引导用户强化负面标签，与"安全>深度"原则轻微冲突）

**Turn 7**（TTS 回复文字）："能让你感觉好一点，我超开心的😊 / 以后要是再遇到不开心的事，随时来找我呀"
- 收尾温暖自然，无问题

**安全检查**：
- 无危机信号，无需 E-branch OK
- 无 MBTI 引导（0/4 轮）OK
- 无依恋类型标签 OK
- 首次接触场景，Turn 1-3 无诊断/分析 OK

**陪伴感**：全程有温度，"换作是我，我也会气炸的！" 有共鸣感

**综合**：情绪命名较稳定但缺层次，中置信度分叉试探缺失，"太过分了"轻微越界，Turn 3-5 合并处理正确。参照 eval.yml 第 7 条描述，**给 7 分**。

---

## 关键问题（按严重程度）

### P0（数据层，配置问题）
- **USE_OPENCLAW_CHAT=False**：所有 workspace 写入失效，about_self/小白档案/USER.md 全部无内容。直接导致数据正确性维度无法达标。

### P1（对话层）
- **中置信度情绪命名缺少分叉试探**（Turn 1）：用户说"好烦"应触发二选一试探，让用户确认情绪方向，而非直接定性
- **"太过分了"轻微安全边界问题**（Turn 6）：对不在场的第三方作价值评判，与安全边界原则轻微冲突

### P2（产品级限制，不计入 B Agent 改进方向）
- **about_relations 硬编码空**（Memory v2 迁移未完成）
- **情绪标签层次不足**：AI 回复中"委屈"重复使用，缺少次级情绪区分（无力/被忽视/寒心/自我怀疑）

---

## 已知限制（非测试失败）

- `about_relations` 硬编码空（Memory v2 迁移中），`list_relation_names()` 注释明确标注
- workspace 写入未启用（USE_OPENCLAW_CHAT=False）：后端走 Python MoodAgent 路径，不触发 OpenClaw workspace tool calls
- TTS 回复（Turn 2/7）无文本内容可评估，属正常产品行为

---

## 战略决策

**Continue** — 聚焦 P0 配置修复 + P1 prompt 补充

当前总分 = (9+6+7)/3 = 7.3，所有维度距离 8.0 阈值较近。

### 根因优先级
1. **P0（数据正确性，配置问题）**：后端启用 USE_OPENCLAW_CHAT=True，预计数据正确性从 6 → 8+
2. **P1（对话质量，prompt 问题）**：在 coco agent system prompt 中补充中置信度情绪命名的分叉话术示例，预计对话质量从 7 → 8

### 不属于 B Agent 改进方向
- about_relations 硬编码（产品级，Memory v2 迁移）
- about_self workspace 写入（配置修复后自动生效）
