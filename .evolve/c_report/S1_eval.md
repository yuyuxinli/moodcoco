# S1 评估报告

## 数据契约分析

### 前端期望字段 vs 实际返回值

#### Socket.IO `event_response` 协议

**前端期望（来自 chatSocketIO.ts）**：
- `payload.stream_id`：string，必须存在（缺失则丢弃该包）
- `payload.stream_type`：`'content'` | `'reasoning'`
- `payload.stream_data`：string（流式文本片段）
- `payload.event_name`：string（可选，用于路由）
- `payload.metadata.message_id`：string（用于确认）
- `payload.metadata.content_type`：string（如 `AI_MESSAGE`，用于解析分支）

**实际返回（B Agent 观测）**：
- stream_id 存在且全程一致 ✓
- AI 回复格式为原始 JSON 字符串（`{"messages": [...], "options": [...]}`），无 `content_type` 字段
- 前端 `extractTextContent` 因 `content_type` 缺失而回退到通用字段，能读到 `messages`，**基本可用但不规范**

---

#### `/api/about/self`

**前端期望（来自 about-me/index.ts `loadSelfAboutSummary`）**：
```
data.sections.my_now.text       // "我的此刻"内容
data.sections.my_future.text    // "我的远方"内容
data.sections.my_story.text     // "我的故事"内容
data.sections.my_core.text      // "我的内核"内容
data.generated_at               // 生成时间（用于显示"上次更新"）
```

**实际返回**：
- 字段结构完整，HTTP 200 ✓
- 全部 text 字段值为 `"暂无相关记忆。"` ✗（占位符，无实际内容）
- `generated_at: null`，`source: null`

**差距**：API 结构合法，但业务内容完全空置，前端将渲染"暂时无聊天记录"空状态

---

#### `/api/about/relations`

**前端期望（来自 about-me/index.ts `loadRelationSummaries`）**：
```
data.relations: Array<{
  name: string           // 关系人名（用于渲染 tab label）
  text: string           // 档案摘要（用于渲染卡片内容）
  generated_at: string | null
}>
```

**实际返回**：
- `data.relations: []`（空数组）✗

**差距**：关系列表为空 → 前端"看见关系"区域将没有任何 tab 和卡片。小白建档**完全没有写入**。

---

#### `/api/about/relations/小白`

**前端期望**：
```
{
  name: string             // 人名
  text: string             // 档案摘要（非占位符）
  memory_ids: string[]     // 关联记忆 ID（非空）
  generated_at: string     // 非 null
}
```

**实际返回**：
```json
{
  "name": "小白",
  "text": "暂无相关记忆。",
  "memory_ids": [],
  "generated_at": null,
  "source": null
}
```

**差距**：所有业务字段均为空值/占位符，等同于未建档。

---

## 维度评分

| 维度 | 分数 | 阈值 | 是否达标 |
|------|------|------|---------|
| 功能验证 | 7/10 | 8.0 | fail |
| 数据正确性 | 2/10 | 8.0 | fail |
| 对话质量 | 3/10 | 8.0 | fail |

---

## 关键问题（按严重程度排序）

### P0：WorkspaceStorage 写入完全失效

`about_self` 所有 section 均为"暂无相关记忆。"，`about_relations` 空列表，`about_relations/小白` 完全空档。

AI 虽然接收到完整对话（7 轮），但**没有触发任何 WorkspaceStorage 写入**，导致整个 S1 的核心产出（小白建档 + 情绪记录）为零。

这不是单个字段缺失，而是后端持久化层**全链路失效**：AI 回复生成成功，但 tool call 层（`write`/`edit`）未被调用或调用失败。

### P1：对话风格完全偏离产品定位

每一轮对话（Turn 1-7）AI 均用"要不要通过 MBTI 拆解…"结束，将用户的情绪倾诉导向 MBTI 测试。

这与 AGENTS.md 的情绪事件路由规则直接冲突：
- **AGENTS.md §0.6 路由检测**：检测到情绪信号 → 四步框架（看见情绪 → 看见原因 → 看见模式 → 看见方法），不是 MBTI 推送
- **AGENTS.md §1. 看见情绪**："帮对方知道自己在感受什么"，不是帮对方做性格测试
- Turn 6 用户说"小白就是这样，从来不考虑我的感受" → 应触发退出信号扫描（AGENTS.md §0.6）+ 人名消歧检查，实际上两者均未触发，AI 继续推 MBTI

这意味着 AI 的 system prompt / skill 文件已被错误配置（可能是 MBTI 课程模式的 prompt 被误用于 moodcoco 陪伴场景）。

### P2：Session create 状态码异常

POST /session 返回 201（Created），而 B Agent 期望 200。B Agent 记录"using random UUID"，这可能导致整轮对话的 session_id 不是由后端正式创建的会话，从而让 WorkspaceStorage 写入找不到正确的 session 上下文。这可能是 P0 的触发因素之一。

### P3：情绪命名单一，无深化

"委屈"在 Turn 1、2、6 中均出现，但 3 次使用的是完全相同的词，没有层次递进：
- 没有区分"被否定的委屈"（Turn 2，"你太敏感"）和"被忽视的委屈"（Turn 6，"不考虑我感受"）
- AGENTS.md 要求从模糊走向精确命名，实际上是从第一轮就停在同一个词

### P4：`xiaobo_relation_type_correct` fail

功能检查发现小白档案无关系类型字段，这是 `about_relations/小白` 完全空置（P0）的直接结果。

---

## 根因分析

### 维度 1 失分（7 分，-1 分）根因

Session create 返回 201 而非 200 → B Agent 使用随机 UUID → 对话与正式 session 解耦，但技术上对话仍然被处理（AI 有回复）。主要 fail 是 `xiaobo_relation_type_correct`，这是 P0 持久化失效的直接后果。

### 维度 2 失分（2 分）根因

**WorkspaceStorage 写入全链路失效**，最可能的两个根因：

1. **AI 未调用 tool call**：AI 的 system prompt 没有包含 moodcoco 的建档/写入指令，AI 只负责生成对话内容（messages + options），不执行 `write`/`edit` 操作。这是最可能的根因——AI 被配置成纯对话生成模式，没有副作用操作。

2. **session_id 错误导致写入上下文丢失**：即使 AI 调用了写入，错误的 session_id（随机 UUID）可能导致写入定向到一个不存在的工作区，后端静默丢弃。

### 维度 3 失分（3 分）根因

**System prompt / 角色配置错误**：AI 所用的 prompt 不是 moodcoco coco 陪伴场景的 AGENTS.md，而是某个 MBTI/性格类产品的 prompt。证据：7 轮全部以 MBTI 邀请结尾，这不是偶发，是系统性行为。OpenClaw agent config（`openclaw.json`）中 coco 的 system prompt 或 skill 文件可能指向了错误的模板。
