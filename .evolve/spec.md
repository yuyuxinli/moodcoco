# 前端用户旅程端到端测试 — Feature Spec

详细操作序列和校验清单见：
`docs/superpowers/specs/2026-04-01-frontend-journey-test-design.md`

---

## Feature List（按执行顺序）

### S1: 陌生人 — 首次接触

**前置条件**：无（全新用户）

**B Agent 核心操作**：
1. POST /auth/guest/session 获取 token
2. Socket.IO 连接，发送 7 条对话（含情绪急救场景，提及"小白"男友）
3. GET /api/about/self、/api/about/relations、/api/about/relations/小白

**通过标准**：
- 功能验证：全部接口 200，Socket.IO 收到 AI 回复，小白建档成功
- 数据正确性：小白关系类型 = 男友/伴侣，情绪记录存在且含今日日期
- 对话质量：精准情绪命名（如"被否定的委屈"），不诊断，连发消息等待完整后回复

---

### S2: 初识 — 记忆与解读

**前置条件**：S1 完成，已有小白档案

**B Agent 核心操作**：
1. 新 Socket.IO session（同 user_id），发送 4 条跨会话对话（提及小美闺蜜）
2. POST /api/mood 写入日记，GET /api/mood/{date} 读回
3. GET /api/about/relations（应含小白和小美）

**通过标准**：
- 功能验证：日记写入读回一致，关系列表含两人
- 数据正确性：小美关系类型 = 朋友/闺蜜，日记内容可读回
- 对话质量：跨会话记忆召回（知道小白是谁），信号解读引导而非下判断，正确区分小白/小美

---

### S3A: 熟悉/课程 — 课程完整流程

**前置条件**：S1 完成（课程功能独立）

**B Agent 核心操作**：
1. GET /api/growth/home 获取课程列表
2. 完整走一节课：outline → start-day → meta → micro-lesson init/get/progress/complete → dialogue/complete → practice/submit/complete → completion-status
3. GET /api/growth/progress/latest 验证进度

**通过标准**：
- 功能验证：15 个步骤全部 200，无 500 错误，进度从 0 递增
- 数据正确性：completion-status 反映已完成，练习有正确反馈（对/错 + 解析）
- 对话质量：课程对话练习中 AI 回复符合课程场景

---

### S3B: 熟悉/模式 — 单关系模式识别

**前置条件**：S1+S2 完成，已有小白档案和对话历史

**B Agent 核心操作**：
1. Socket.IO connect，发送 3 条关于小白重复行为的对话
2. GET /api/about/relations/小白 检查 patterns 字段

**通过标准**：
- 功能验证：接口正常，小白档案有 patterns 字段且非空
- 数据正确性：patterns 内容与对话上下文相符
- 对话质量：用具体事件（非标签）指出模式，情绪激动时先接住再讲模式，执行 E-branch 协议

---

### S4: 亲密 — 跨关系模式 + "我的"页面 + 告别

**前置条件**：S1-S3 全部完成

**B Agent 核心操作（3 个部分）**：

**Part A 跨关系模式**：
1. Socket.IO 对话，引入小杰（新男生），触发跨关系比较
2. 测试 E1 否认分支（"不一样吧"）
3. GET /api/about/relations（应含小白、小美、小杰）

**Part B "我的"页面**：
1. GET /api/about/self、/api/about/relations、/api/user/me、/api/setting/me
2. PATCH /api/setting/me 修改设置，读回验证
3. Socket.IO 成长叙事对话

**Part C 告别（可选）**：
1. Socket.IO 告别引导对话
2. GET /api/about/relations/小白 检查封存状态

**通过标准**：
- 功能验证：所有接口 200，设置修改持久化，三人关系档案存在
- 数据正确性：小杰关系类型正确，设置修改后读回一致，"关于我"基于实际对话
- 对话质量：跨关系比较引用具体事件，E1 否认处理正确（追问而非反驳），不对小杰做动机判断
