# S1 调查报告

## 调查 1：openclaw.json 配置

文件位置：`/Users/jianghongwei/Documents/psychologists/openclaw.json`

关键发现：
- coco agent workspace 指向：`./backend/ai-companion/ai-companion`
- 主模型：`openrouter/minimax/minimax-m2.7`（含 failover）
- system_prompt 来源：`AGENTS.md`（OpenClaw 自动加载 workspace 根目录）
- workspace 与 moodcoco 源码目录（`/Users/jianghongwei/Documents/moodcoco/ai-companion/`）完全分离，实际运行的是 psychologists 项目内部的 workspace

S1 原始测试（v1-v3）使用 `ChatAgent`（WELCOME.md），对应 CHAT session_type，所以触发 MBTI 引导。
v4 脚本已修正为 `MOOD` session_type，使用 MoodAgent。

## 调查 2：后端 AI agent 配置

- session_type=CHAT → `ChatAgent`（`agents/chat/agent.py`），使用 `WELCOME.md` 作为 system prompt，明确要求引导 MBTI 测试
- session_type=MOOD → `MoodAgent`（`agents/mood/agent.py`），Tool 架构（OpenAI Function Calling），不涉及 MBTI
- session_type=MBTI_GAME → `MbtiAgent`

**关键**：`ChatAgent.chat_task_file = "chat/WELCOME.md"` + `persona_linyu.md` 的组合明确要求"引导用户进入MBTI测试"。这是 P1 根因所在，但**仅在 CHAT session_type 时触发**。

## 调查 3：session 接口语义

正确流程：
- **创建 MOOD session**：`POST /api/chat/sessions` 带 `session_type: "MOOD"` → 返回 201 + session_id
- 或使用 `POST /api/chat/mood/session/create-or-reuse` 获取 Mood 专用会话（可自动决定新建/复用）
- Socket.IO 连接时传 `session_type=mood` 参数

v4 脚本已正确使用 MOOD 类型，状态 201 正常。

## 调查 4：socket 事件完整性

实际 Socket.IO 事件列表（ws_socketio.py emit 扫描）：
- `connection_established` — 连接建立
- `session_updated` — session_id 变更通知
- `message_received` — 消息已接收确认
- `message_buffered` — 消息缓冲中（多条快速消息）
- `event_processing_start` — 开始处理
- `event_response` — 流式 chunk（包含 stream_type=content/sentence_audio/reasoning 等）
- `event_processing_end` — 处理完成
- `error` — 错误
- `stream_cancelled` — 流取消
- `stt_session_started` / `stt_result` / `stt_partial` / `stt_error` — 语音相关
- `async_task_progress` — MBTI 异步任务进度

**没有独立的工具调用 Socket 事件**。工具调用通过 MoodAgent 内部 Function Calling 处理，结果以 `event_response`（stream_type=content）输出，不单独通知前端。

v4 脚本已正确捕获所有事件类型。MoodAgent 工具调用（AI_MESSAGE 等）的结果作为 content 出现在 event_response 中。

## 调查 5：workspace 实际状态

```
/Users/jianghongwei/Documents/psychologists/backend/ai-companion/ai-companion/
├── AGENTS.md          # coco 的 system_prompt 来源
├── memory/
│   ├── pattern_log.md  # 仅有模板，无实际记录（工具写入未触发）
│   ├── pending_followup.md
│   └── time_capsules.md
└── (people/ 目录不存在)  # 从未被 OpenClaw workspace 写入
```

`/Users/jianghongwei/Documents/moodcoco/ai-companion/` 是 moodcoco 源码目录，**不是运行时 workspace**，两者分离。

## 根因确认

**P0 根因**：`about_relations` 永远返回空列表是设计行为。
- `AboutRelationService.list_relation_names()` 代码中硬编码 `return []`，注释为 "Memory v2 migration in progress"
- 这是后端**有意的过渡态实现**，人物关系列表还未从任何数据源填充
- OpenClaw workspace 的 `people/*.md` 写入与 `about_relations` API **完全解耦**：`about_relations` 读的是数据库表 `about_relation_snapshot`，由每日凌晨 4:00 批处理任务生成；OpenClaw workspace 写的是文件系统，两者没有连通
- 真正的 P0 是：`list_relation_names` 返回 `[]` 是服务端的半完成代码，不是测试脚本问题

**P1 根因**：在 S1 原始测试（v1-v3）中，使用了 `CHAT` session_type 而不是 `MOOD`。
- `CHAT` session 走 `ChatAgent`，其 system_prompt（`WELCOME.md`）明确要求"引导用户进入MBTI测试"
- `MOOD` session 走 `MoodAgent`（Tool 架构），完全没有 MBTI 引导
- v4 脚本已修复此问题，重新执行 v4 后 P1 已解决（0/4 轮含 MBTI 引导）

## 重新执行 S1 结果

使用 `run_s1_v4.py`（已修复 session_type=MOOD，捕获全部事件，每轮等待 30s）：

**通过率：7/8**

| 检查项 | 结果 | 说明 |
|--------|------|------|
| auth_200 | PASS | 登录正常 |
| socket_connected | PASS | WebSocket 连接正常 |
| ai_reply_received | PASS | AI 回复正常（情绪陪伴，无 MBTI 引导）|
| about_self_200 | PASS | API 返回 200 |
| about_relations_200 | PASS | API 返回 200 |
| xiaobo_profile_found | PASS | 小白 profile 端点存在（返回空态）|
| xiaobo_relation_type_correct | **FAIL** | `list_relation_names` 返回 `[]`，小白无记忆（设计行为，见 P0 根因）|
| rapid_fire_merged | PASS | 快速连发 3 条被合并为 2 个响应 |

**P1 修复确认**：0/4 轮回复含 MBTI 引导（完全正常，MoodAgent 聊天完全符合情绪陪伴定位）

**P0 尚未修复**：`xiaobo_relation_type_correct` 失败是设计预期（`list_relation_names` 硬编码返回 `[]`，Memory v2 迁移中）。对话内容（people/*.md 写入）由 OpenClaw MoodAgent 执行，与 `about_relations` API 数据源完全分离，短期内无法通过对话写入实现关系列表填充。
