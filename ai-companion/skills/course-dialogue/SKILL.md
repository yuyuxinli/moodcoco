---
name: course-dialogue
description: 课程对话 Agent——管理学一学（微课卡片）、练一练（练习题）、聊一聊（对话引导）三个学习阶段的完整流程。路由 7 种事件：init_dialogue / start_lesson / card_interaction / card_reply_tts / user_next_card / start_practice / submit_answer。触发条件：用户进入课程详情页，或 session_type 为 MICRO_LESSON / QUIZ_PRACTICE / COURSE_DIALOGUE。
---

# 课程对话流程

管理心理课程的三个学习阶段：学一学（微课卡片）、练一练（练习题）、聊一聊（课程对话）。每个阶段有独立的事件路由和完成逻辑。

## 触发条件

- session_type 为 MICRO_LESSON（学一学）
- session_type 为 QUIZ_PRACTICE（练一练）
- session_type 为 COURSE_DIALOGUE（聊一聊）
- 前端发送 7 种事件之一

## 7 种事件路由

| 事件 | 阶段 | 说明 |
|------|------|------|
| `start_lesson` | 学一学 | 开始微课，生成全部卡片 |
| `card_interaction` | 学一学 | 用户在卡片上选择互动选项 |
| `card_reply_tts` | 学一学 | 请求卡片回复的 TTS 音频 |
| `user_next_card` | 学一学/练一练 | 请求下一张卡片或题目 |
| `start_practice` | 练一练 | 开始练习，生成 5 道题 |
| `submit_answer` | 练一练 | 提交练习答案 |
| `init_dialogue` | 聊一聊 | 初始化课程对话 |

用户发送文本消息时，如果当前处于 COURSE_DIALOGUE session，按聊一聊流程处理。

## Phase 1：学一学（微课卡片）

### 事件 start_lesson

收到 `start_lesson` 事件后：

1. 调用 `course_dialogue_start_lesson` Service Tool 获取微课内容：
```
course_dialogue_start_lesson(lesson_id="<lesson_uuid>", current_card_index=0)
```

该 Service 返回完整卡片列表（含缓存命中逻辑）：
- 命中缓存：直接返回已生成的卡片
- 未命中：调用 LLM 生成，保存缓存后返回

每张卡片包含：
- `coco_narration`: 可可的讲解文字（数组，每元素一句话）
- `options`: 互动选项
- `image_url`: 卡片配图（如有）
- `coco_audio_url`: TTS 音频（异步生成）

2. 将返回的卡片内容通过 `ai_micro_lesson` UI Tool 推送到前端展示。

### 事件 card_interaction

用户在卡片上选择互动选项时：

1. 调用 `course_dialogue_card_interaction` 记录互动：
```
course_dialogue_card_interaction(card_index=0, selected_option="option1")
```

2. 返回确认。

### 事件 card_reply_tts

用户点击卡片的 reply 按钮请求 TTS 时：

1. 调用 `course_dialogue_card_reply_tts` 生成回复音频：
```
course_dialogue_card_reply_tts(card_index=0, reply_text="...", lesson_id="<uuid>")
```

2. 返回音频 URL。

### 事件 user_next_card（学一学模式）

请求下一张微课卡片：

1. 调用 `course_dialogue_next_card` 获取下一张卡片：
```
course_dialogue_next_card(
  lesson_id="<uuid>",
  current_step=1,
  lesson_type="micro_lesson"
)
```

2. Service 返回卡片内容 + 进度信息 + 是否阶段完成。
3. 如果 `stage_complete=true`，提示用户进入下一阶段。

## Phase 2：练一练（练习题）

### 事件 start_practice

收到 `start_practice` 事件后：

1. 调用 `course_dialogue_start_practice` 获取练习题：
```
course_dialogue_start_practice(lesson_id="<lesson_uuid>")
```

该 Service 返回 5 道练习题（缓存优先）。

每道题包含：
- `text`: 题目文本
- `question_type`: "true_false"（判断题）或 "single_choice"（选择题）
- `options`: 选项列表
- `correct_answer`: 正确答案 ID
- `feedback`: 答题反馈

2. 通过 `ai_quiz_practice` UI Tool 推送到前端。

### 事件 submit_answer

用户提交答案时：

1. 调用 `course_dialogue_submit_answer` 记录答案：
```
course_dialogue_submit_answer(question_index=0, answer_index=1)
```

2. 返回确认。

### 事件 user_next_card（练一练模式）

请求下一道题目：

1. 调用 `course_dialogue_next_card` 获取下一题：
```
course_dialogue_next_card(
  lesson_id="<uuid>",
  current_step=2,
  lesson_type="practice"
)
```

2. Service 生成并返回题目。

## Phase 3：聊一聊（课程对话）

### 事件 init_dialogue

初始化课程对话：

1. 调用 `course_dialogue_init` 获取对话上下文：
```
course_dialogue_init(session_id="<session_uuid>")
```

Service 返回：
- `system_prompt`: 完整的课程对话 Prompt（七层 Context）
- `lesson_title`: 课程标题
- `lesson_subtitle`: 课程副标题

2. 根据 system_prompt 生成开场白，引导用户分享真实经历。

### 用户文本消息（聊一聊模式）

用户发送文本消息时：

1. 调用 `course_dialogue_context` 获取对话上下文和历史：
```
course_dialogue_context(session_id="<session_uuid>")
```

2. 基于返回的 system_prompt + 对话历史 + 用户新消息进行回复。

3. 回复格式使用 AI_DIALOGUE_RESPONSE 结构：
   - `messages`: 回复消息数组（每个元素一句话/一个气泡），1-2 句为佳
   - `options`: 3 个参考回复选项（字符串，10-15 字，降低开口门槛）
   - `should_complete`: 对话目标已完成时设为 true
   - `complete_summary`: 收获总结（should_complete=true 时填写，10-20 字）

4. 调用 `message_persist` 保存对话消息。

### 对话风格规则

- 每句话简短口语化，8-20 字
- 不连续说教，不堆砌建议
- 多用提问引导，少说教
- 适时总结和鼓励
- 开场第一句必须直接扣住今天的知识点
- 引导用户结合自身经历理解知识点

### 对话收尾

当以下信号出现时，设置 `should_complete=true`：
- 用户表达感谢/收获/愿意尝试
- 技术应用讨论已完成
- 对话超过 10 轮
- 用户回复变短或敷衍

收尾时通过 `complete_summary` 提供一句收获总结。

## 完整流程：init -> card -> complete

```
学一学 → 练一练 → 聊一聊 → 完成
(start_lesson)  (start_practice)  (init_dialogue)
     │               │                │
     ▼               ▼                ▼
  卡片展示        题目展示          对话引导
     │               │                │
  user_next_card  user_next_card   用户消息
     │               │                │
  stage_complete  stage_complete   should_complete
     │               │                │
     └───────────────┴────────────────┘
                     │
               课程完成 ✓
```

每个阶段完成时，Service 自动更新 UserLessonProgress。

## 可用工具

### Service Tools

- `course_dialogue_start_lesson` — 开始微课，返回卡片列表（含缓存 + TTS）
- `course_dialogue_next_card` — 获取下一张卡片或题目（含进度更新）
- `course_dialogue_card_interaction` — 记录卡片互动
- `course_dialogue_card_reply_tts` — 生成卡片回复 TTS
- `course_dialogue_start_practice` — 开始练习，返回 5 道题
- `course_dialogue_submit_answer` — 记录答案提交
- `course_dialogue_init` — 初始化课程对话（获取 Prompt + 上下文）
- `course_dialogue_context` — 获取对话上下文（Prompt + 历史）
- `message_persist` — 消息持久化
- `conversation_history` — 获取对话历史
- `user_profile_get` — 获取用户画像
- `audio_synthesize` — TTS 语音合成

### UI Tools

- `ai_micro_lesson` — 推送微课卡片到前端
- `ai_quiz_practice` — 推送练习题到前端
- `ai_options` — 通用选项卡
- `ai_dialogue_response` — 推送对话回复 + 选项

## 硬规则

1. **事件路由必须正确**：7 种事件各有专属 Service Tool，不能混用
2. **缓存优先**：学一学/练一练首次加载走 LLM，二次进入走缓存
3. **进度自动更新**：每完成一张卡片/一道题/一段对话，Service 自动更新 Progress
4. **TTS 非阻塞**：音频异步生成，失败不影响内容展示
5. **阶段顺序**：学一学 → 练一练 → 聊一聊，但允许用户跳过
6. **安全前置**：任何阶段检测到危机信号 → 立即执行 AGENTS.md 安全协议
7. **聊一聊收尾不强制**：用户没有表达想结束，不主动推收尾
