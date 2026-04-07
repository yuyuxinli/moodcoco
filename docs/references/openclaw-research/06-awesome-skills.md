# 调研报告：Awesome OpenClaw Skills 与心情可可的交集分析

> 调研日期：2026-04-05
> 数据来源：awesome-openclaw-skills（5,211 个 skill，30 个分类）

---

## 一、项目概览与分类体系

awesome-openclaw-skills 是社区维护的 OpenClaw Skill 精选列表，从 ClawHub 上 13,729 个 skill 中筛选出 5,211 个，过滤掉了垃圾（4,065）、重复（1,040）、低质量（851）、加密/区块链（886）、恶意（373）。

### 30 个分类及规模

| 分类 | Skill 数 | 与心情可可相关度 |
|------|---------|---------------|
| Coding Agents & IDEs | ~1,100 | 低（但藏了 emotion-detector、mindcore 等） |
| Web & Frontend | ~900 | 低（但藏了 buddhist-counsel、tarot 等） |
| DevOps & Cloud | ~370 | 无 |
| Search & Research | ~340 | 无 |
| Browser & Automation | ~310 | 无 |
| Productivity & Tasks | ~200 | 低 |
| CLI Utilities | ~170 | 低（intimate-wellbeing 在此） |
| Image & Video | ~170 | 低（但有 emotionwise、tarot） |
| AI & LLMs | ~160 | 低 |
| Git & GitHub | ~160 | 无 |
| Communication | ~140 | 低 |
| PDF & Documents | ~100 | 无 |
| Marketing & Sales | ~100 | 无 |
| Media & Streaming | ~90 | 无 |
| **Health & Fitness** | **84** | **高** |
| Notes & PKM | ~70 | 中（continuity、nova-letters） |
| Calendar & Scheduling | ~70 | 无 |
| Security | ~55 | 无 |
| **Personal Development** | **51** | **高** |
| Shopping | ~50 | 无 |
| Smart Home | ~45 | 无 |
| Speech & Transcription | ~45 | 低 |
| Apple Apps | ~45 | 无 |
| Self-hosted | ~35 | 无 |
| iOS/macOS Dev | ~35 | 无 |
| Transportation | ~110 | 无 |
| Gaming | ~30 | 低（clawtopia 桑拿放松） |
| Clawdbot Tools | ~40 | 低（claw-face 表情） |
| Data & Analytics | ~40 | 无 |
| Moltbook | ~40 | 无 |

**关键发现**：与情绪/心理健康直接相关的 skill 分布极度分散，并不集中在 Health & Fitness 或 Personal Development 两个看似对口的分类。需要全库搜索 emotion/mood/mental/therapy/mindful/journal 等关键词才能找全。

---

## 二、Health & Fitness 分类分析（84 个）

这个分类噪音极高。84 个 skill 中：

| 实际内容 | 数量 | 占比 |
|---------|------|------|
| 饮食/营养追踪 | ~18 | 21% |
| 健身/运动数据 | ~12 | 14% |
| 设备集成（Fitbit/Garmin/Oura） | ~8 | 10% |
| 加密/黑客马拉松（错分类） | ~15 | 18% |
| 安全/DevOps（错分类） | ~12 | 14% |
| **心理/情绪相关** | **~5** | **6%** |
| 其他杂项 | ~14 | 17% |

**与心情可可相关的仅 5 个**：
- `sauna-calm` — 检测挫败感 + 呼吸练习
- `detox-counter` — 戒断追踪（含情绪/睡眠日志）
- `soft-pillow` — 睡眠数据查询
- `fasting-tracker` — 间歇性断食追踪
- `health-summary` — 健康摘要（含情绪趋势）

---

## 三、Personal Development 分类分析（51 个）

质量明显高于 Health & Fitness，但也有约 40% 不相关（求职、理财、学习卡片、投票等）。

**与心情可可高度相关的 skill**：

| Skill | 作者 | 核心功能 | 下载量 |
|-------|------|---------|--------|
| anxiety-relief | @jhillin8 | 焦虑管理：4-7-8 呼吸、5-4-3-2-1 着陆、认知重构、发作日志 | ~1.6k |
| depression-support | @jhillin8 | 抑郁支持：1-10 情绪评分、微任务、行为激活、自我照顾清单 | ~1.5k |
| mindfulness-meditation | @jhillin8 | 冥想引导：5 种技术、时长选择、连续打卡、每日提醒 | ~1.6k |
| morning-routine | @jhillin8 | 晨间习惯：清单、计时、连续天数、自然语言交互 | ~2.1k |
| crucial-conversations-coach | @pors | 关键对话教练：STATE/CRIB 框架、Silence/Violence 模式识别 | ~1.8k |
| zenplus-health | @ollieparsley | 职场身心健康：正念、呼吸、情绪签到（需 Zen+ API） | - |
| daily-questions | @daijo-bu | 每日自省问卷：学习用户 + 调整 agent 行为（需 Telegram） | - |
| founder-coach | @goforu | 创始人心智教练：苏格拉底式提问、心智模型追踪 | - |
| adhd-body-doubling | @jankutschera | ADHD 陪伴：微步骤拆解、定时签到、阻碍识别 | - |
| fix-life-in-1-day | @evgyur | 10 个结构化心理 session，源自 Dan Koe 方法论 | - |

---

## 四、跨分类发现的情绪相关 Skill

| Skill | 分类 | 核心功能 |
|-------|------|---------|
| mindcore | Coding Agents | 仿生情绪引擎，CPU 守护进程生成情绪冲动 JSON |
| emotion-detector | Coding Agents | 文本情绪分析 API（强度/效价/置信度），含危机标记 |
| emotionwise | Image & Video | 28 标签情绪分析 + 讽刺检测 API（EN/ES） |
| enginemind-eft | Image & Video | Rust 物理引擎驱动的逐句情绪分析（10 类） |
| buddhist-counsel | Web & Frontend | 佛学智慧 + 循证疗法的付费咨询 API |
| tarot | Image & Video | 反思性塔罗（Major Arcana），非预测性情绪探索 |
| agent-wellness | Coding Agents | Agent 自身的日记/情绪追踪/好奇心日志 |
| continuity | Notes & PKM | 异步反思与记忆整合 |
| nova-letters | Notes & PKM | 给未来自己写信 |
| intimate-wellbeing | CLI Utilities | 亲密关系健康指导 |
| claw-face | Clawdbot Tools | 浮动表情头像，根据情绪显示不同表情 |
| tg-sticker-emoji-mood | Web & Frontend | 根据对话情绪自动发送匹配表情包 |
| voice-log | Coding Agents | 语音日记（Soniox 实时语音转文字） |

---

## 五、重点 Skill 的 SKILL.md 写法对比

### 社区 Skill 的典型写法（以 jhillin8 系列为代表）

jhillin8 是社区中心理健康方向最活跃的作者，发布了 anxiety-relief、depression-support、mindfulness-meditation、morning-routine、detox-counter、fasting-tracker、muscle-gain 共 7 个 skill。

**写法特征**：
1. **功能导向**：描述「能做什么」——追踪什么、记录什么、提醒什么
2. **工具列表式**：呼吸练习类型、评分量表、日志格式
3. **强调数据本地**：反复强调「all data stored locally on your device」
4. **有免责声明**：「Not a substitute for professional care」
5. **缺少心理学理论基础**：没有引用具体研究或理论
6. **缺少触发/退出逻辑**：没有定义何时启动、何时退出、与其他 skill 的边界
7. **缺少对话策略**：没有具体的话术指导（说什么/不说什么）

### 心情可可的写法

**以 `breathing-ground` 为例**：

| 维度 | 社区 Skill | 心情可可 |
|------|-----------|---------|
| **心理学引用** | 无 | Stanford 2023 RCT、多迷走神经理论、Porges、Kabat-Zinn、Jacobson |
| **触发条件** | 用户请求时 | 具体信号列表（身体症状描述词 + 失控感表达 + 语句碎片化） |
| **退出条件** | 无 | 明确定义，回归正常对话流 |
| **边界划分** | 无 | 与 listen/untangle/crisis 的明确边界表格 |
| **对话策略** | 通用描述 | 逐字呼吸引导文本 + 「不可以说」清单 |
| **步骤节奏** | 一次输出全套 | 「一次只给一个动作，等对方回应了再给下一个」 |
| **情感态度** | 功能性 | 「不解释为什么有用，除非对方问。现在不是上课的时候」 |
| **与其他 Skill 协作** | 独立运行 | 通过 AGENTS.md 路由层联动 |

**以 `pattern-mirror` 为例**：

社区没有任何对标 skill。pattern-mirror 的核心能力——跨关系模式觉察、情绪稳定性 5 信号检测、频率保护（同一模式 14 天冷却、被拒绝 30 天冷却）——在 5,211 个 skill 中完全没有对应物。

**以 `check-in` 为例**：

社区最接近的是 `daily-questions`（每日自省问卷），但 daily-questions 是固定问卷 + 选项按钮，check-in 是结合 memU 记忆系统的个性化情绪签到 + 周回顾，复杂度完全不在一个层级。

### 结论

**心情可可的 SKILL.md 比社区平均水平高出 2-3 个量级**。社区 skill 基本是「工具说明书」级别（做什么 + 怎么安装），心情可可的 skill 是「临床督导手册」级别（什么时候做 + 什么时候不做 + 做的时候说什么/不说什么 + 出意外走哪条路径）。

---

## 六、可用性评估：哪些能直接用/需要改造/不需要

### A. 可以参考但不推荐直接安装的（3 个）

| Skill | 原因 |
|-------|------|
| `anxiety-relief` | 功能已被 breathing-ground + calm-body 完全覆盖且更精细。但其「发作日志 + 触发器识别」功能可参考 |
| `depression-support` | 行为激活 + 微任务的理念有价值，可融入 check-in 的低情绪路径 |
| `crucial-conversations-coach` | STATE/CRIB 框架可融入 relationship-guide，但需要大量中文本土化 |

### B. 有参考价值的设计思路（4 个）

| Skill | 可借鉴之处 |
|-------|-----------|
| `daily-questions` | USER.md + SOUL.md 双文件学习用户偏好 + 调整 agent 行为的机制 |
| `adhd-body-doubling` | 微步骤拆解 + 定时签到 + 阻碍表面化的方法论，适合 face-decision 场景 |
| `founder-coach` | 苏格拉底式提问 + 心智模型追踪的持久化设计 |
| `tarot` | 非预测性「象征镜子」设计，可作为 know-myself 的隐喻工具参考 |

### C. 技术层工具可评估引入（2 个）

| Skill | 用途 | 风险 |
|-------|------|------|
| `emotion-detector` | 文本情绪分析 API，可辅助 scene-router 做情绪强度判断 | 付费（x402/USDC），安全评级 Suspicious |
| `emotionwise` | 28 标签情绪分类，比 emotion-detector 颗粒度更高 | 需要 API Key，仅支持 EN/ES |

### D. 不需要/不适用的

| Skill | 原因 |
|-------|------|
| `mindfulness-meditation` | 功能已被 calm-body 覆盖，且我们的引导更精细 |
| `morning-routine` | 习惯追踪，不在心情可可的核心场景内 |
| `zenplus-health` | 需要 Zen+ 外部服务，且功能泛泛 |
| `fix-life-in-1-day` | 10 session 结构过重，且安全评级 Suspicious |
| `mindcore` | 给 Agent 自身加情绪——概念有趣但安全评级 Suspicious，且不解决用户问题 |
| `agent-wellness` | 给 Agent 加日记——同上，不解决用户问题 |
| `buddhist-counsel` | 付费外部 API，零下载量 |
| `detox-counter` | 戒断追踪，偏健身领域 |

---

## 七、核心发现与建议

### 发现 1：社区几乎没有「真正的情绪陪伴」Skill

5,211 个 skill 中，与情绪/心理健康直接相关的不超过 20 个，且全部是「工具型」——追踪情绪评分、引导呼吸练习、记录日志。没有一个 skill 做到：
- 基于心理学理论设计对话策略
- 定义触发/退出条件和 skill 间边界
- 区分「什么时候该做」和「什么时候不该做」

**心情可可在这个方向上没有现成轮子可用。** 这印证了我们自建 skill 的必要性。

### 发现 2：jhillin8 系列值得关注但不值得安装

jhillin8 是社区最活跃的心理健康 skill 作者（7 个 skill），其设计思路——将情绪支持拆分为独立模块（焦虑/抑郁/冥想/习惯/戒断）——与心情可可的 skill 拆分思路有相似之处。但实现深度差距巨大。

### 发现 3：两个可行动的改进方向

1. **行为激活微任务**（来自 depression-support）：当 check-in 检测到持续低情绪（连续 3 天评分 ≤3），可借鉴「根据当前能量级别推荐微任务」的思路，融入现有流程
2. **关键对话框架**（来自 crucial-conversations-coach）：STATE 框架（Share facts → Tell your story → Ask → Talk tentatively → Encourage testing）可作为 relationship-guide 中「帮用户准备困难对话」的结构化工具

### 发现 4：情绪分析 API 暂不推荐引入

emotion-detector 和 emotionwise 提供情绪分析 API，但：
- 都需要外部付费服务
- 安全评级为 Suspicious
- 心情可可的 scene-router 已通过 LLM 内置能力做情绪判断，额外 API 层增加延迟和成本，收益不明确

### 发现 5：分类体系对情绪健康方向极不友好

情绪相关 skill 分布在 Health & Fitness、Personal Development、Coding Agents、Web & Frontend、Image & Video、Notes & PKM、CLI Utilities 等至少 7 个分类中。如果只看 Health & Fitness + Personal Development，会漏掉一半以上的相关 skill。

---

## 八、总结

| 维度 | 结论 |
|------|------|
| 可直接安装使用 | **0 个**——社区 skill 的深度不足以匹配心情可可的标准 |
| 可参考设计思路 | **4 个**：daily-questions、adhd-body-doubling、founder-coach、tarot |
| 可融入现有 skill 的具体功能 | **2 个**：depression-support 的行为激活微任务、crucial-conversations-coach 的 STATE 框架 |
| 技术工具可观望 | **2 个**：emotion-detector、emotionwise（暂不推荐引入） |

**底线结论**：5,211 个社区 Skill 中，没有任何一个可以替代心情可可的自建 Skill。这个方向的社区供给严重不足，心情可可的 20 个自建 Skill 在情绪陪伴领域属于远超社区水平的专业实现。继续自建是正确策略，同时可选择性吸收上述 2-4 个设计思路。
