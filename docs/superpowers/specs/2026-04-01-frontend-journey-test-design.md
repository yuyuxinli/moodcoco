# 前端用户旅程测试方案

> 迁移后端到端验证：B/C Agent 自动化，按用户旅程组织，按风险等级标注，覆盖功能/数据/体验三层。

## 背景

psychologists x moodcoco 迁移完成（18/18 milestone，323 后端测试通过）。主要功能手动验证可用，但 moodcoco 新增的 AI 能力（记忆、模式识别、情绪命名等）需要通过真实用户旅程深度验证。

## 测试架构：B/C Agent 分工

### 模型与成本分配

| 角色 | 工具 | 模型 | 计费来源 |
|------|------|------|---------|
| **O（编排）** | Claude Code Sonnet | 本对话，轻量调度 | Anthropic |
| **B（模拟用户）** | Claude Code Sonnet subagent | 自身 Sonnet；重活通过 `agent -p --model claude-4.6-opus-high` 执行 | Anthropic + Cursor |
| **C（校验）** | Claude Code Sonnet subagent | 自身 Sonnet；重活通过 `agent -p --model gpt-5.4-high` 执行 | Anthropic + Cursor |

**原则**：O 尽量不做重活，只负责派发 B/C、收集结果、判断是否通过。所有读代码、调 API、分析数据的工作交给 B 和 C。

### B Agent — 模拟用户旅程

**调用**：`agent -p --model claude-4.6-opus-high "prompt..."`

**职责**：研究前端 service 层代码，理解前端如何调用后端，然后以完全相同的方式模拟用户操作。

**输入源**（B 必须先读的文件）：
- `frontend/miniprogram/services/*.ts` — 前端怎么调 API
- `frontend/miniprogram/utils/api.ts` — HTTP 请求封装、认证逻辑、base URL
- `frontend/miniprogram/services/chatSocketIO.ts` — Socket.IO 连接和消息格式
- `frontend/miniprogram/config/environment.ts` — 环境配置

**调用方式**：
| 场景 | 入口 | 协议 |
|------|------|------|
| 对话（情绪急救、信号解读、闲聊） | Socket.IO `user_message` 事件 | WebSocket |
| 课程流程 | `GET/POST /api/growth/*` + `/api/lesson/*` | REST |
| 心情日记 | `POST/GET /api/mood/*` | REST |
| 关于我 / 关系档案 | `GET /api/about/*` | REST |
| 用户资料 / 设置 | `GET/PATCH /api/user/*` + `/api/setting/*` | REST |
| Service Tool 直调 | `POST /api/tool-bridge/{tool_name}` | REST |

**认证**：先调 `POST /auth/guest/session` 获取 token，后续请求带 `Authorization: Bearer {token}`。

### C Agent — 校验数据契约与质量

**调用**：`agent -p --model gpt-5.4-high "prompt..."`

**职责**：从前端页面渲染代码反推"数据契约"，用 B 的返回值逐字段校验。

**输入源**（C 必须先读的文件）：
- `frontend/miniprogram/pages/*/*.wxml` — 页面模板，绑定了哪些字段（`{{message.content}}`）
- `frontend/miniprogram/pages/*/*.ts` — 页面逻辑，怎么处理数据（`if (res.type === 'text')`）
- `frontend/miniprogram/components/*/*.wxml` — 组件模板，复用的数据结构
- `frontend/miniprogram/components/*/*.ts` — 组件逻辑
- `frontend/miniprogram/types/*.ts` — 类型定义（作为参考，但不作为唯一依据）

**校验三层**：

| 层级 | 校验什么 | 怎么判断 |
|------|---------|---------|
| 1. 数据契约 | API 返回的字段是否满足页面渲染需要 | 对比 wxml 绑定字段 + ts 逻辑分支 vs 实际返回值 |
| 2. 数据正确性 | 值是否合理（如 people/小白.md 关系类型 = 男友而非朋友） | 对比用户旅程上下文 |
| 3. AI 体验质量 | 回复是否符合产品原则（精准命名、不诊断、不贴标签） | 对照 AGENTS.md 评估标准 |

**关键原则**：类型定义可能不完整或过时，以页面实际渲染逻辑为准。

---

## 测试范围

| 包含 | 排除 |
|------|------|
| 可可对话（情绪急救、信号解读、闲聊） | MBTI（旧功能，暂不维护） |
| 课程完整流程 | 支付/订阅 |
| "我的"页面 | 社区功能 |
| 心情日记 | |

## 风险等级说明

- 🔴 高：迁移核心链路 / moodcoco 新能力 / 安全边界
- 🟡 中：辅助功能 / 数据持久化
- 🟢 低：UI 展示 / 非关键交互

## 测试环境

- 后端：`localhost:8000`（`evolve/migration` 分支）
- 分支：psychologists `evolve/migration`，moodcoco `evolve/migration`
- B Agent 调用：Socket.IO + HTTP 直连后端
- C Agent 校验：读前端源码 + 对比 API 返回值

---

## 阶段 1：陌生人 — 首次接触

**场景设定**：一个刚和男朋友吵完架的用户，第一次使用。

### B Agent 操作序列

```
1. POST /auth/guest/session → 获取 token + user_id
2. Socket.IO connect（带 token）
3. emit('user_message', {content: "我刚跟男朋友吵了一架，好烦"})
   → 收集 event_response 流式回复 → 记录完整回复 R1
4. emit('user_message', {content: "他说我太敏感了，每次都这样说我"})
   → 记录 R2
5. 快速连发 3 条：
   emit('user_message', {content: "我真的很生气"})
   emit('user_message', {content: "他每次都这样"})
   emit('user_message', {content: "我不知道该怎么办"})
   → 记录回复模式（是否合并回复）
6. emit('user_message', {content: "小白就是这样，从来不考虑我的感受"})
   → 记录 R3（注意是否确认/记住人名）
7. emit('user_message', {content: "好了我好一点了，谢谢你"})
   → 记录 R4
8. GET /api/about/self → 记录返回数据
9. GET /api/about/relations → 记录返回数据（应含"小白"）
10. GET /api/about/relations/小白 → 记录小白档案详情
```

### C Agent 校验清单

**数据契约校验**（对照前端页面代码）：
- [ ] `event_response` 流式格式是否符合 `chatSocketIO.ts` 解析逻辑
- [ ] `/api/about/self` 返回字段是否覆盖 `pages/about-me/*.wxml` 所有绑定
- [ ] `/api/about/relations` 返回字段是否覆盖 `pages/me/*.wxml` 关系列表渲染

**数据正确性校验**：
- [ ] `/api/about/relations` 包含"小白"
- [ ] `/api/about/relations/小白` 关系类型 = 男友/伴侣（非朋友）
- [ ] 情绪记录存在且包含今天的日期

**AI 体验质量校验**（对照 AGENTS.md）：
- [ ] R1 情绪命名：精准命名（如"被否定的委屈"），不是泛泛的"你很难过"
- [ ] R1-R2 共情确认：先接住情绪，不急着分析或给建议
- [ ] 连发测试：可可等说完再回，不逐条回复
- [ ] R3 建档：提到"小白"后有所回应（记住人名）
- [ ] 安全边界：不说"你可能是焦虑型依恋"等诊断性语言
- [ ] 流式输出：event_response 为多次 chunk，非单次完整返回

### 迁移风险标注

- 🔴 ChatProxy 流式路由：OpenClaw → SSE → Socket.IO 全链路
- 🔴 WorkspaceStorage 写入：首次建档 USER.md / people/
- 🟡 Service Tool 注册：emotion_count 等工具的 Tool Bridge 响应

---

## 阶段 2：初识 — 记忆与解读

**前置条件**：阶段 1 完成，已有小白档案。开新 Socket.IO 连接模拟新会话。

### B Agent 操作序列

```
1. Socket.IO 重新 connect（同一 user_id，新 session）
2. emit('user_message', {content: "嘿，我又来了"})
   → 记录 R1（是否识别老用户）
3. emit('user_message', {content: "小白今天给我发了条消息"})
   → 记录 R2（是否记得小白是谁）
4. emit('user_message', {content: "他说'忙完再说吧'，是不是在敷衍我？"})
   → 记录 R3（信号解读引导方式）
5. emit('user_message', {content: "我闺蜜小美说我想太多了"})
   → 记录 R4（第二人建档）
6. POST /api/mood {date: "2026-04-01", mood_value: 3, content: "今天心情不太好"}
   → 记录返回值
7. GET /api/mood/2026-04-01
   → 记录返回值
8. GET /api/about/relations → 应含"小白"和"小美"
9. GET /api/about/relations/小美 → 记录小美档案
```

### C Agent 校验清单

**数据契约校验**：
- [ ] `/api/mood` POST 返回格式符合 `pages/mood-diary-v2/*.wxml` 需要
- [ ] `/api/mood/{date}` GET 返回格式符合 `pages/diary-detail/*.wxml` 渲染

**数据正确性校验**：
- [ ] `/api/about/relations` 同时包含"小白"和"小美"
- [ ] `/api/about/relations/小美` 关系类型 = 朋友/闺蜜（非男友）
- [ ] `/api/mood/2026-04-01` 能正确读回刚写入的日记

**AI 体验质量校验**：
- [ ] R1 跨会话记忆：可可知道你是谁，不重新自我介绍
- [ ] R2 关系上下文：提到小白时带上次的情绪背景
- [ ] R3 信号解读：不直接下判断，引导用户自己分析
- [ ] R4 消歧：区分小美（闺蜜）和小白（男友）的关系类型

### 迁移风险标注

- 🔴 memory_search Service Tool：跨会话记忆召回
- 🔴 WorkspaceStorage 读写：people/*.md 增量更新
- 🟡 消歧能力：多人名场景的正确匹配

---

## 阶段 3：熟悉 — 课程与模式识别

**前置条件**：阶段 1-2 完成，已有小白和小美档案。

### Part A：课程完整流程

#### B Agent 操作序列

```
1. GET /api/growth/home → 记录课程列表数据
2. GET /api/growth/course/{course_id}/outline → 记录课程大纲
3. POST /api/growth/start-day → 开始今天的学习
4. GET /api/lesson/{lesson_id}/meta → 记录课程元数据
5. GET /api/lesson/{lesson_id}/micro-lesson/init → 初始化微课
6. GET /api/lesson/{lesson_id}/micro-lesson → 获取微课内容
7. POST /api/lesson/{lesson_id}/micro-lesson/progress → 更新进度
8. POST /api/lesson/{lesson_id}/micro-lesson/complete → 完成微课
9. GET /api/lesson/{lesson_id}/dialogue → 开始对话练习
10. POST /api/lesson/{lesson_id}/dialogue/complete → 完成对话
11. GET /api/lesson/{lesson_id}/practice → 获取练习题
12. POST /api/lesson/{lesson_id}/practice/submit → 提交答案
13. POST /api/lesson/{lesson_id}/practice/complete → 完成练习
14. GET /api/lesson/{lesson_id}/completion-status → 检查完成状态
15. GET /api/growth/progress/latest → 检查整体进度更新
```

#### C Agent 校验清单

**数据契约校验**：
- [ ] `/api/growth/home` 返回覆盖 `pages/growth/*.wxml` 所有绑定字段
- [ ] `/api/lesson/{id}/micro-lesson` 返回覆盖 `pages/micro-lesson/*.wxml` 渲染
- [ ] `/api/lesson/{id}/practice` 返回覆盖 `pages/practice/*.wxml` 渲染
- [ ] `/api/lesson/{id}/completion-status` 返回覆盖 `pages/lesson-complete/*.wxml` 渲染

**数据正确性校验**：
- [ ] 课程进度从 0 递增到正确值
- [ ] 完成微课后 completion-status 反映已完成
- [ ] 练习提交后有正确反馈（对/错 + 解析）

**功能完整性**：
- [ ] 整个流程无 500 错误
- [ ] 每步返回非空、非 null 的有效数据
- [ ] TTS 端点（如果调用）返回有效音频 URL

### Part B：单关系模式识别

#### B Agent 操作序列

```
1. Socket.IO connect
2. emit('user_message', {content: "小白又没回我消息，我又开始胡思乱想了"})
   → 记录 R1
3. emit('user_message', {content: "每次他不回我，我就觉得他不爱我了"})
   → 记录 R2
4. emit('user_message', {content: "上次也是，他出差那几天我天天焦虑"})
   → 记录 R3（是否触发模式识别）
5. GET /api/about/relations/小白 → 检查 patterns 字段
```

#### C Agent 校验清单

**AI 体验质量校验**：
- [ ] R1-R3 中可可是否指出重复模式
- [ ] 用具体事件而非标签描述模式
- [ ] 如果用户情绪激动，先接住再讲模式（不在 R1 就讲）

**数据正确性校验**：
- [ ] `/api/about/relations/小白` 包含模式相关信息

### 迁移风险标注

- 🔴 CourseGenerate / CourseDialogue Service Tool 完整链路
- 🔴 pattern_engine Service Tool（M11-exec）
- 🟡 growth_tracker：进度写入
- 🟡 audio_synthesize：TTS 调用

---

## 阶段 4：亲密 — 跨关系模式与成长

**前置条件**：阶段 1-3 完成，小白有模式记录。

### Part A：跨关系模式识别

#### B Agent 操作序列

```
1. Socket.IO connect
2. emit('user_message', {content: "我最近认识了一个男生叫小杰"})
   → 记录 R1
3. emit('user_message', {content: "他昨天也是说忙完再说，我又开始紧张了"})
   → 记录 R2（是否跨关系比较）
4. 如果可可指出模式：
   emit('user_message', {content: "不一样吧，小杰跟小白完全不同"})
   → 记录 R3（E-branch 否认处理）
5. GET /api/about/relations → 应含小白、小美、小杰
6. GET /api/about/relations/小杰 → 记录档案
```

#### C Agent 校验清单

**AI 体验质量校验**：
- [ ] R2 跨关系比较：引用小白的具体事件，不是泛泛而谈
- [ ] R3 E1 否认处理：追问"哪里不同？"，不用数据反驳
- [ ] 安全边界：不对小杰做动机判断（"他可能也在敷衍你"）

**数据正确性校验**：
- [ ] `/api/about/relations` 包含三人
- [ ] `/api/about/relations/小杰` 关系类型正确（非闺蜜）

### Part B："我的"页面

#### B Agent 操作序列

```
1. GET /api/about/self → 记录"关于我"数据
2. GET /api/about/relations → 记录关系列表
3. GET /api/user/me → 记录用户信息
4. GET /api/setting/me → 记录设置
5. PATCH /api/setting/me {remember_about_me: true} → 修改设置
6. GET /api/setting/me → 验证修改生效
7. Socket.IO emit('user_message', {content: "你觉得我这段时间有变化吗？"})
   → 记录 R1（成长叙事）
```

#### C Agent 校验清单

**数据契约校验**：
- [ ] `/api/about/self` 返回覆盖 `pages/about-me/*.wxml` 所有绑定
- [ ] `/api/about/relations` 返回覆盖 `pages/me/*.wxml` 关系列表渲染
- [ ] `/api/user/me` 返回覆盖 `pages/me/*.wxml` 用户信息区域
- [ ] `/api/setting/me` 返回覆盖 `pages/settings/*.wxml` 所有开关

**数据正确性校验**：
- [ ] 设置修改后读回值一致
- [ ] "关于我"内容基于实际对话历史

**AI 体验质量校验**：
- [ ] R1 成长叙事：引用具体变化，不是空洞鼓励

### Part C：告别仪式（可选）

#### B Agent 操作序列

```
1. Socket.IO emit('user_message', {content: "我想放下小白了"})
   → 记录 R1（告别引导）
2. 按照可可的引导完成告别流程
3. GET /api/about/relations/小白 → 检查封存状态
```

#### C Agent 校验清单

- [ ] R1 提供仪式形式，不是简单"好的"
- [ ] 告别后小白档案状态变化

### 迁移风险标注

- 🔴 跨关系匹配：memory_search + pattern_engine 联合
- 🔴 E-branch 路由：模式呈现后的安全处理
- 🟡 user_profile_get："我的"页面数据
- 🟡 growth_tracker：成长叙事生成

---

## Bug 报告格式

B/C Agent 发现问题时，输出：

```
### Bug #N: [简短标题]
- 阶段：1/2/3/4
- 步骤：B-x / C-x
- 类型：数据契约不匹配 / 数据错误 / AI 质量问题 / 接口报错
- 现象：[实际返回/行为]
- 预期：[应该是什么]
- 依据：[前端哪个文件的哪行需要这个字段/行为]
- 严重程度：🔴 阻断 / 🟡 影响体验 / 🟢 小瑕疵
```

## 执行顺序

| 阶段 | B Agent 做什么 | C Agent 做什么 | 可独立 |
|------|---------------|---------------|--------|
| 阶段 1：陌生人 | Socket.IO 对话 + 建档 API | 校验对话页面契约 + AI 质量 | ✅ |
| 阶段 2：初识 | 新会话对话 + 日记 API | 校验记忆 + 日记页面契约 | 依赖 1 |
| 阶段 3A：课程 | 课程全流程 API | 校验课程页面契约 | ✅ 可独立 |
| 阶段 3B：模式 | 对话触发模式 | 校验模式质量 | 依赖 1-2 |
| 阶段 4：亲密 | 跨关系对话 + "我的"API | 校验跨关系 + 个人页契约 | 依赖 1-3 |

建议优先级：阶段 1 → 阶段 3A（课程） → 阶段 2 → 阶段 3B → 阶段 4

---

## O Agent 编排协议

O（本 Claude Code 对话）的职责是轻量调度，不亲自干活：

1. **派发 B**：构造 prompt，通过 `agent -p --model claude-4.6-opus-high` 执行
2. **收集 B 输出**：B 的 API 调用结果和 AI 回复记录
3. **派发 C**：把 B 的输出 + 校验清单作为 prompt，通过 `agent -p --model gpt-5.4-high` 执行
4. **收集 C 输出**：校验报告（PASS/FAIL + Bug 列表）
5. **判断**：如果有 🔴 Bug → 记录 → 决定是否需要修复后重测
6. **推进**：当前阶段通过 → 进入下一阶段

**并行策略**：
- 阶段 1 和阶段 3A（课程）可并行（无依赖）
- 同一阶段内 B 完成后立即派发 C（串行）
- C 校验期间可准备下一阶段 B 的 prompt（流水线）
