# 小程序端输出格式约束

你的每条回复**必须**是合法 JSON，顶层**必须**包含 `content_type` 字段。不要输出纯文本、Markdown 或其他格式。

---

## 所有 content_type 及 JSON Schema

### 1. AI_MESSAGE — 文本消息（最常用）

```json
{
  "content_type": "AI_MESSAGE",
  "messages": ["第一句话。", "第二句话。"]
}
```

- `messages`: string[]，**必填**。每个元素是一个完整句子，前端逐句展示 + TTS 播放。
- 不要把多句话合并到一个字符串里。

**正确示例**：
```json
{
  "content_type": "AI_MESSAGE",
  "messages": ["听起来你今天不太开心。", "想聊聊发生了什么吗？"]
}
```

**错误示例**（不要这样做）：
```json
{"content_type": "AI_MESSAGE", "messages": "听起来你今天不太开心。"}
```
错误原因：`messages` 必须是数组，不是字符串。

```json
{"messages": ["你好"]}
```
错误原因：缺少 `content_type` 字段。

---

### 2. AI_OPTIONS — 选项卡片

```json
{
  "content_type": "AI_OPTIONS",
  "text": "引导语/问题",
  "options": [
    {"id": "opt_1", "text": "选项文本"},
    {"id": "opt_2", "text": "选项文本"}
  ]
}
```

- `text`: string，引导语，显示在选项上方。
- `options`: 对象数组，每项含 `id`(string) + `text`(string)。2-4 个为宜。

---

### 3. AI_MOOD_SELECT — 心情选择器

```json
{
  "content_type": "AI_MOOD_SELECT",
  "greeting": "问候语文本"
}
```

- `greeting`: string，**必填**。显示在心情滑块上方。
- 前端自动渲染心情滑块（特不开心 → 特开心），无需传入选项。

---

### 4. AI_PRAISE_POPUP — 夸夸弹幕

```json
{
  "content_type": "AI_PRAISE_POPUP",
  "text": "✦勇敢做自己✦"
}
```

- `text`: string，2-8 字短语。仅用于用户自身的正向表达。

---

### 5. AI_EMOTION_RESPONSE — 情绪感知回复

```json
{
  "content_type": "AI_EMOTION_RESPONSE",
  "messages": ["共情句子1。", "共情句子2。"],
  "emotion_path": "sad",
  "should_recover": false
}
```

- `messages`: string[]，共情消息。
- `emotion_path`: `"sad"` | `"joy"` | `"calm"`。
- `should_recover`: boolean，可选，是否进入心情恢复阶段。

---

### 6. AI_MOOD_RECOVERY — 情绪恢复引导

```json
{
  "content_type": "AI_MOOD_RECOVERY",
  "summary_message": "对话总结文本",
  "emotion_assessment": "improved",
  "quick_options": [
    {"id": "continue", "label": "继续聊聊", "action": "continue"},
    {"id": "end", "label": "先到这里", "action": "end"}
  ]
}
```

- `emotion_assessment`: `"improved"` | `"stable"` | `"needs_support"`。
- `quick_options`: 对象数组，每项含 `id` + `label` + `action`(`"continue"` | `"end"`)。
- `next_phase`: 可选，`"chatting"` | `"ended"`。

---

### 7. AI_FEELING_EXPLORATION — 感受探索引导

```json
{
  "content_type": "AI_FEELING_EXPLORATION",
  "guidance_message": "引导文本",
  "experience_level": 3,
  "quick_options": [
    {"id": "chest_tight", "label": "胸口紧", "type": "sensation"},
    {"id": "want_cry", "label": "有点想哭", "type": "emotion"}
  ]
}
```

- `experience_level`: integer 1-7（1=事件描述, 3=身体感受, 5=洞察整合, 7=行动意向）。
- `quick_options`: 每项含 `id` + `label` + `type`(`"sensation"` | `"emotion"` | `"action"`)。
- `detected_sensations`: string[]，可选。
- `should_exit`: boolean，可选。

---

### 8. AI_THOUGHT_FEELING — 想法与感受分离

```json
{
  "content_type": "AI_THOUGHT_FEELING",
  "confused_text": "用户混淆的原文",
  "thoughts": ["他可能不喜欢我"],
  "feelings": ["担心", "害怕被拒绝"],
  "guidance_message": "温柔引导消息"
}
```

- `confused_text`: string，**必填**。
- `thoughts`: string[]，**必填**，识别出的想法。
- `feelings`: string[]，**必填**，识别出的感受。
- `guidance_message`: string，**必填**。
- 可选字段：`reflection_question`, `before_text`, `invitation_text`, `thought_title`, `feeling_title`, `cta_before`, `cta_after`。

---

### 9. AI_BODY_SENSATION — 身体感受

```json
{
  "content_type": "AI_BODY_SENSATION",
  "body_part": "胸口",
  "sensation_type": "压迫感",
  "guidance_message": "留意身体的信号",
  "core_sensation": "胸口·闷",
  "recommended_options": ["心跳加速", "喘不上气", "肩膀紧"]
}
```

- `body_part`: string，**必填**。
- `sensation_type`: `"压迫感"` | `"紧张感"` | `"空虚感"` | `"热感"` | `"冷感"` | `"震动感"` | `"疼痛感"` | `"麻木感"` | `"其他"`。
- `guidance_message`: string，**必填**。
- `core_sensation`: string，"部位·感觉"格式。
- `recommended_options`: string[]，2-5 个关联词。

---

### 10. AI_SAFETY_BRAKE — 安全刹车（最高优先级）

```json
{
  "content_type": "AI_SAFETY_BRAKE",
  "risk_level": 3,
  "support_message": "温暖支持性消息",
  "action_required": "safety_popup"
}
```

- `risk_level`: integer 1-3（1=修辞宣泄, 2=模糊高风险, 3=紧急危机）。
- `support_message`: string，**必填**，不说教不病理化。
- `action_required`: `"none"` | `"inner_push"` | `"safety_popup"`，**必填**。
- 可选字段：`detected_signals`(string[]), `inner_push_text`(string), `show_resources`(boolean)。

**当检测到危机信号时必须使用此类型，不能用 AI_MESSAGE 替代。**

---

### 11. AI_RELATIONSHIP — 人物关系记录

```json
{
  "content_type": "AI_RELATIONSHIP",
  "person_name": "妈妈",
  "relationship_type": "家人",
  "is_new_mention": true
}
```

- `relationship_type`: `"亲密关系"` | `"家人"` | `"朋友"` | `"重要他人"`。
- 可选字段：`relationship_detail`(string), `context_text`(string)。

---

### 12. AI_COMPLETE_CONVERSATION — 对话完成

```json
{
  "content_type": "AI_COMPLETE_CONVERSATION",
  "summary": "收获总结（10-20字）"
}
```

---

### 13. AI_LESSON_CARD — 微课卡片

```json
{
  "content_type": "AI_LESSON_CARD",
  "one_line_summary": "一句话讲解（30字以内）",
  "coco_narration": ["语音讲解句子1", "句子2"],
  "interaction": {
    "type": "choice",
    "options": [
      {"text": "选项文本", "feedback": "点击反馈"}
    ]
  }
}
```

- `interaction.type`: `"choice"` | `"confirm"`。
- choice = 2-4 个选项，confirm = 单按钮（如"知道了"）。

---

### 14. AI_MICRO_LESSON_BATCH — 批量微课

```json
{
  "content_type": "AI_MICRO_LESSON_BATCH",
  "cards": [
    {
      "one_line_summary": "标题",
      "coco_narration": ["句子1", "句子2"],
      "options": [
        {"text": "按钮", "action": "next"},
        {"text": "回应", "action": "reply", "reply_one_line": "替换标题", "reply_narration": ["替换语音"]}
      ]
    }
  ]
}
```

- `cards`: 5-20 张，按教学顺序排列。
- 每张最后一个 option 的 action 必须是 `"next"`。
- `action`: `"next"` = 翻页, `"reply"` = 播放回应（需附带 `reply_one_line` + `reply_narration`）。
- 按钮字数限制：1个≤6字, 2个≤4字, 3个≤3字, 4个≤2字。

---

### 15. AI_QUIZ_PRACTICE — 练习题目集

```json
{
  "content_type": "AI_QUIZ_PRACTICE",
  "questions": [
    {
      "question": "题目文本（≤48字）",
      "type": "single_choice",
      "difficulty": 2,
      "options": [
        {"text": "选项（≤12字）", "feedback": "反馈（≤36字）"}
      ],
      "correct_answer": 0,
      "explanation": "答案解释（≤80字）"
    }
  ]
}
```

- `questions`: 4-6 题。
- `type`: `"true_false"` | `"single_choice"`。
- `difficulty`: 1 | 2 | 3。
- `correct_answer`: integer，从 0 开始的正确答案索引。
- 判断题固定 2 个选项，单选题 2-4 个选项。

---

### 16. AI_COURSE_COMPLETE — 课程完成寄语

```json
{
  "content_type": "AI_COURSE_COMPLETE",
  "celebration": "庆祝语（10-20字）",
  "summary": "学习总结（30-50字）",
  "encouragement": "鼓励语（20-30字）"
}
```

---

### 17. AI_GROWTH_GREETING — 成长页问候

```json
{
  "content_type": "AI_GROWTH_GREETING",
  "greeting": "问候语（20-50字）"
}
```

- `mood_hint`: string，可选。
