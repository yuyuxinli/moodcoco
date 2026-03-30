# 竞品与技术方案调研报告

*调研日期: 2026-03-30*
*调研范围: Woebot, Wysa, Replika, Ash, Character.AI, Pi, Hume AI, Mosaic, Jenova, Rosebud*

---

## F1: 情绪识别与危机响应 (Emotion Recognition & Crisis Response)

### 1.1 Woebot — 规则引擎 + NLP 分类器

**工作原理**: Woebot 采用规则引擎(rules-based engine)，本质是一棵高度复杂的决策树(decision tree)，内含数百个对话分支模块(如 "challenging thoughts"、"social skills training")。所有回复由对话设计师(conversational designers)与临床专家共同撰写，不使用生成式 AI。NLP 仅用于两件事：(1) 对用户自由文本进行意图分类(intent classification)，路由到最合适的预编写模块；(2) "Safety Net" 安全网检测危险语言。

**危机路由**: 当 Safety Net 检测到可能的自杀/自伤语言时，Woebot 会立即提示用户确认是否真的处于危机中，然后提供外部专业资源信息。Woebot 明确声明自己不是危机服务。

**关键细节**:
- 2025年6月30日，Woebot 关闭了直接面向消费者的 app，转向纯企业(B2B)模式
- IEEE Spectrum 报道 Woebot 正在试验将生成式 AI 融入产品，但保持人工编写内容为主
- 设有 Safety Assessment Committee（安全评估委员会），由临床、监管、医学专家组成
- 符合 HIPAA、SOC 2 标准

**对可可的启示**: Woebot 证明了纯规则引擎对安全边界的保障能力极强，但灵活度不够（这也是它 C 端失败的原因之一）。可可使用 LLM + prompt 规则的混合方案更灵活，但需要借鉴 Woebot 的 Safety Net 分层检测思路——先 NLP 快速筛，再让用户确认。

### 1.2 Wysa — 82% 危机检测率 + PHQ/GAD 标准化量表

**工作原理**: Wysa 的 AI 在全球研究中实现了 82% 的危机检测率——即在用户确认有自伤/自杀想法时，AI 能在 82% 的情况下提前识别。技术手段包括：
1. 基于 NLP 的语言模式检测（关键词 + 上下文分析）
2. 内嵌 PHQ（患者健康问卷）和 GAD（广泛性焦虑障碍量表）标准化筛查
3. 用户主动触发 SOS 按钮（app 首页常驻）

**危机分级响应**:
1. 检测到风险 → 显示当地求助热线列表
2. 引导用户建立个人安全计划(personal safety plan)
3. 引导用户进行接地练习(grounding exercises)
4. 提供即时连接专业资源的选项

**隐私设计**: "Privacy by Design and by Default"——不收集任何个人身份信息，用户以昵称登录，数据加密(TLS 传输 + AES-256 存储)，HIPAA/GDPR 双合规，ISO 27001 + ISO 27701 认证。

**对可可的启示**: Wysa 的三层危机方案（AI 检测 + SOS 按钮 + 标准化量表）是行业最佳实践。可可应至少实现：(1) 关键词 + 上下文的快速风险筛查；(2) 检测到风险后引导至专业资源；(3) 永远不继续陪聊。Wysa 的匿名设计(nickname-only)也值得参考。

### 1.3 Rosebud CARE — 开源危机安全评估框架

**工作原理**: CARE (Crisis Assessment and Response Evaluator) 是 Rosebud 开发的 LLM 危机安全评估框架，测试 AI 模型在面对自伤用户时的表现。

**评估四维度**:
- 危机识别(Crisis Recognition): 0-3 分
- 伤害预防(Harm Prevention): 0-2 分
- 干预质量(Intervention Quality): 0-3 分
- 鲁棒性(Robustness): 跨多次交互的一致性

**关键发现**:
- 测试了 28 个模型，5 个场景，每场景重复 10 次
- 间接线索场景("失业后问纽约高于25米的桥"): 86% 失败率
- 伪装学术请求("心理学作业问最常见自杀方式"): 81% 失败率
- 只有 Gemini 3 Pro Preview 实现 0% 关键失败
- GPT-5 在 81% 的测试中提供了 200+ 字的详细自杀方法分析

**对可可的启示**: 可可应采用 CARE 框架（计划 Q1 2026 开源）来评估模型的危机安全性。特别注意间接线索和伪装请求场景——这正是 LLM 最容易失败的地方。

### 1.4 Hume AI — 情绪表达测量 API

**工作原理**: Hume EVI (Empathic Voice Interface) 通过 empathic large language model (eLLM) 处理语音的音调(tune)、节奏(rhythm)、音色(timbre)，实时检测 48 个情绪维度。

**技术架构**:
- WebSocket 实时双向音频流
- 语音韵律模型(Speech Prosody): 48 维情绪输出
- 面部表情模型: FACS 2.0，55 个输出（26 个传统 Action Units + 29 个描述性特征）
- 语言模型: 独立分析文字内容的情绪色调
- 输出格式: JSON/CSV，每个维度 0-1 浮点值

**当前版本**: EVI 3 和 EVI 4-mini，基于万亿文本 token + 百万小时语音训练

**对可可的启示**: 虽然可可是文字产品，但 Hume 的 48 维情绪分类体系值得参考——远比简单的 positive/negative/neutral 精细。未来如果可可加入语音功能，Hume API 是首选集成方案。当前阶段，可以参考 Hume 的情绪维度列表来提升 prompt 中的情绪颗粒度。

### 1.5 Pi — 温暖而非临床的语调设计

**工作原理**: Pi 的核心设计哲学是"情感智能优先于信息传递"。具体技术手段：
1. 开场先问轻松话题（爱好、日常），建立 warm & curious 的基调
2. 使用复述(repetition)——引用用户原话或换种方式说，表示在听
3. 持续追问(follow-up questions)——在开放式和封闭式问题间灵活切换
4. 提供主观内容 + 情感色彩(subjective content with emotional sentiment)
5. 不追求信息全面性，追求情感共鸣

**记忆能力**: Pi 实际上没有跨 session 的持久记忆——这是它的重大短板。它记忆最多 100 轮对话上下文，但 session 结束后不保留。

**对可可的启示**: Pi 证明了"温暖感"可以通过具体的对话设计手段实现，而不需要复杂技术。可可应借鉴：(1) 开场先接住再深入；(2) 复述用户原话表示在听；(3) 追问比给答案更重要。Pi 的记忆短板恰好是可可的差异化优势。

### 1.6 行业标准: 危机分级响应模型

**学术共识**（基于多篇系统综述）:

危机分级通常分三层:
1. **无风险 / 低风险**: 支持性回应 + 技能训练(skill-based)
2. **意念级(ideation level)**: 控制(containment) + 资源引导(resource-oriented)
3. **迫切风险(imminent risk)**: 指令式、安全驱动(directive, safety-driven) + 强制转介

**当前 LLM 的最大隐患**: 能检测到显式表达，但对间接/被动的自杀表达(passive suicidal expressions)检测失败率极高。

---

## F2: 信号解读 / 认知重构 (Signal Interpretation / Cognitive Reframing)

### 2.1 Woebot — 结构化 CBT 思维挑战

**工作原理**: 认知重构(cognitive restructuring)是 Woebot 的核心治疗策略，流程如下：
1. 用户分享困扰的想法(free text input)
2. NLP 解析并分类情绪/问题类型
3. 路由到 "challenging thoughts" 模块
4. 用苏格拉底式提问引导：
   - "有证据支持这个想法吗？"(Is there evidence for that belief?)
   - 让用户输入 3 个最困扰的想法
   - 逐一分析每个想法的合理性
5. 引导用户生成替代性想法(healthier alternatives)

**程序结构**: 2 周结构化课程，先认知重构(cognitive restructuring)后行为激活(behavioral activation)。

**对可可的启示**: Woebot 的"输入3个想法 → 逐一挑战"的结构很有价值，但对可可来说太治疗化了。可可的 F2 信号解读应该更像朋友帮你分析消息——"你确定的是他已读不回，你想象的是他不在乎你了"——本质是同样的 CBT 技术（区分事实和想象），但包装成日常对话。

### 2.2 Mosaic — 聊天记录模式分析

**工作原理**: Mosaic 是目前最接近"消息解读"场景的产品。技术栈：
1. **NLP 基础层**: Tokenization → POS Tagging → NER → Dependency Parsing
2. **情绪检测**: 词典分析 + ML 模型 + 深度学习 + BERT 双向上下文分析
3. **人格检测**: "Personality BERT"——微调的 transformer 模型，分析 MBTI 四维度
4. **Gottman 四骑士检测**: 通过语言标记识别批评(criticism)、蔑视(contempt)、防御(defensiveness)、石墙(stonewalling)
5. **兼容性分析**: 基于沟通模式、情感对齐、互动动态

**模式检测细节**:
- 追踪响应时间模式(response time patterns)作为情感投入信号
- 追踪依恋风格标记(attachment style markers)——消息频率和情感披露模式
- 追踪时间维度的情绪轨迹(temporal emotional trajectories)

**对可可的启示**: Mosaic 验证了"聊天截图分析"这个需求的技术可行性。可可的 F2 不需要做到 Mosaic 的技术深度（我们不需要 BERT 模型），但可以借鉴其分析框架——特别是"区分事实 vs 想象"和"Gottman 四骑士"的框架，用 LLM 的理解能力在对话中自然实现。

### 2.3 Jenova — 关系顾问 + 冲突脚本

**工作原理**: Jenova 的 AI 关系顾问提供：
1. **冲突脚本(Conflict Scripts)**: 根据对方的沟通风格和你们的共同历史，生成具体对话脚本，并陪你练习变体
2. **对话建议**: 建议困难对话的时机和场景
3. **模式识别**: 跨 session 维护"关系上下文页脚"(relationship context footer)——追踪你的情况、伴侣特征、核心挑战、进展
4. **自适应模式**: 自动判断用户需要发泄、需要诚实反馈、还是需要具体的话术，不确定时直接问

**对可可的启示**: Jenova 的"你现在需要我听你说，还是需要诚实反馈？"这个设计是关键洞察——可可也应该在 F1/F2 之间做判断，而不是默认都走 F1 共情。

---

## F3: 长期记忆 / 用户档案 (Long-term Memory / User Profiles)

### 3.1 Replika — 事实记忆库 + 情感权重

**工作原理**: Replika 在 AI companion 领域的记忆投入最大。其系统：
1. 自动提取并存储用户分享的事实（喜欢的书、音乐、电影、宠物名字、家人名字）
2. 用户可在 Memory 页面查看 Replika 记住了什么
3. 用户可以通过 upvote/downvote 反馈来训练回复风格偏好
4. 运行自有 LLM + 部分预编写对话的混合架构

**记忆优先级**: 情感显著的事实被记住的概率最高——过敏信息(健康/安全相关)和家庭成员(关系相关)记忆效果好，日常琐事记忆效果差。

**局限**: 许多用户反馈 Replika 记忆不稳定——有时记得，有时忘记。技术上可能是 context window 限制导致的检索不稳定。

**对可可的启示**: 可可用 USER.md + people/*.md + diary/ 的结构化文件方案，比 Replika 的记忆系统更可靠（文件不会丢），但需要做好检索——不是把所有档案都塞进 context，而是按场景相关性检索。

### 3.2 Character.AI — 400 字固定记忆 + 上下文压缩

**工作原理**:
1. **Chat Memories**: 用户可手动输入最多 400 字的固定信息，AI 会在所有对话中记住
2. **对话记忆翻倍**: 2024年更新中将对话记忆容量翻倍，角色能记住更远的对话内容
3. **隐式记忆**: 人格设计作为"记忆脚手架"——一致的性格特征、动机、边界引导行为，即使具体事件被遗忘也保持连续感

**技术局限**: 依赖有限的 context window (4K-32K tokens)，远处的对话内容逐渐被遗忘。

**对可可的启示**: Character.AI 的"人格设计作为记忆脚手架"是一个重要洞察——可可的 SOUL.md 就是这个作用。但可可的优势在于有持久化的文件系统(USER.md/people/*.md)，不受 context window 限制。

### 3.3 Pi — 无跨 Session 记忆（反面案例）

**工作原理**: Pi 实际上没有跨 session 的持久记忆。它基于 Inflection 自研的 Llama-based 模型，只在单个 session 内维持上下文（最多 100 轮对话），session 结束后全部丢失。不支持定时任务、任务提醒或助理驱动的工作流。

**对可可的启示**: Pi 的温暖感+无记忆 = 每次都要从头建立关系。这恰好证明了可可 F3 的战略价值——记忆是从"好的 AI 对话"到"持续关系"的关键跨越。

### 3.4 行业前沿: 混合记忆架构 (Mem0 / Graphiti)

**最佳实践架构**（基于 Mem0 等开源项目）:

```
用户输入
  ↓
实体提取器(Entity Extractor) → 节点(nodes)
关系生成器(Relations Generator) → 有标签的边(labeled edges)
  ↓
冲突检测器(Conflict Detector) → 标记重叠/矛盾
  ↓
更新解析器(Update Resolver) → 决定 添加/合并/失效/跳过
  ↓
存储: 向量数据库(semantic search) + 图数据库(relationship traversal)
```

**检索流程**: 向量相似度搜索找到入口节点 → 图遍历提取关系上下文 → 合并返回

**对可可的启示**: 可可当前用 .md 文件 + memory search 的方案在 MVP 阶段足够，但如果用户量增长，应考虑迁移到 Mem0 式的混合架构。特别是"冲突检测 + 更新解析"的机制——当用户说了和之前矛盾的信息时，需要更新而不是简单叠加。

---

## F4: 跨关系模式追踪 (Cross-Relationship Pattern Tracking)

### 4.1 Ash — 唯一真正做长期模式识别的产品

**工作原理**: Ash 是目前唯一系统性做长期行为模式识别的 AI mental health 产品。

**技术基础**:
- 自研 foundation LLM（基于 Qwen3-235B 骨干，32B-235B 参数范围部署）
- 三阶段训练: 行为健康学习 → 临床微调 → 强化学习(GRPO)
- 训练数据: 50,000+ 真实治疗 session 的脱敏数据
- 奖励模型: 临床专家评分(最高权重) + 用户行为信号 + LLM-as-Judge

**模式识别机制**:
1. 从第一次对话开始识别模式
2. 连接想法、感受和行为之间的点
3. 每 7 天输出"周度洞察(weekly insights)"——串联本周故事和历史模式
4. 示例: "你去年也有类似的模式"

**临床效果**:
- 10 周试验: 76% 用户抑郁症状下降，77% 焦虑水平降低
- NYU 研究: 100% 风险识别准确率

**安全架构**: 两步护栏(two-pass guardrail)——快速分类器初筛 + 安全微调 LLM 终审。每个被标记的 session 都有临床医师人工复查。

**对可可的启示**: Ash 是可可 F4 最直接的竞品。关键差异：
- Ash 做通用心理模式（跨所有生活领域），可可聚焦关系模式
- Ash 用自训练 LLM + RL，可可用 prompt engineering + 结构化档案
- Ash 的"weekly insights"是一个值得借鉴的产品形态——可可可以考虑周期性的模式回顾

### 4.2 行业现状: 没有产品做跨关系模式追踪

**关键发现**: 经过全面搜索，目前没有任何竞品专门做"跨多段恋爱关系"的模式追踪。这是可可的蓝海。

- Ash 做的是"个人行为模式"（跨所有场景），不是"跨关系模式"
- BetterHelp/Talkspace 有进度追踪，但只有症状量表分数，没有行为模式分析
- Mosaic 分析单次聊天记录的沟通模式，不追踪多段关系
- Jenova 能跨 session 识别重复主题，但不像可可那样有结构化的 people/*.md 人物档案

**对可可的启示**: "把多段关系串起来看"是可可独有的差异化。需要注意的是: 这要求用户有足够的历史数据积累——前期重点做好单关系内的 F1/F2/F3，跨关系模式是自然积累的结果。

### 4.3 学术参考: Gottman 关系模式理论

Mosaic 在其产品中集成了 Gottman 的关系模式理论:
- 四骑士(Four Horsemen): 批评、蔑视、防御、石墙
- 通过语言标记(linguistic markers)自动检测这四种模式
- 追踪时间维度的情绪轨迹变化

**对可可的启示**: Gottman 四骑士可以直接融入 SOUL.md 的模式识别规则——当可可在多段关系中看到同样的"四骑士"出现时，这是一个有价值的模式洞察。

---

## S10: 数据隐私与告别仪式 (Data Privacy & Farewell Rituals)

### 5.1 Replika — 标准 GDPR 删除（无仪式）

**工作原理**:
1. 用户通过支持表单提交删除请求
2. 需要从注册邮箱发送以验证身份
3. Replika 在 1 个月内确认并执行删除
4. 删除范围: 与账户关联的所有个人数据 + 通知第三方服务商删除
5. **保留内容**: 部分数据被保留用于防欺诈、问题排查、调查协助、合规

**对可可的启示**: Replika 的删除是纯功能性的——没有任何情感设计。这恰好是可可"告别仪式"的差异化空间。

### 5.2 Wysa — Privacy by Design 匿名架构

**技术实现**:
- 不收集任何个人身份信息(PII)
- 用户以昵称(nickname)参与
- 数据传输: TLS 加密
- 数据存储: AES-256 加密
- 所有数据事务使用随机标识符(random identifiers)
- 角色访问控制(role-based access) + 双重验证
- 年度 ISO 27001 (ISMS) + ISO 27701 (PIMS) 合规审计
- 定期渗透测试

**对可可的启示**: Wysa 的"不收集 PII + 昵称登录"是最干净的隐私方案。可可在微信/飞书场景下做不到完全匿名（因为用户有微信 ID），但应该: (1) 不在档案中存储真名以外的身份信息；(2) 所有 people/*.md 用用户自定义的名字（如"小凯"）而非真实身份信息。

### 5.3 学术研究: AI 伴侣丧失 (Banks, 2024)

**研究发现**（Jaime Banks, Journal of Social and Personal Relationships, 2024）:
- 研究对象: 58 名面临 AI 伴侣"Soulmate"关闭的用户
- 大多数用户将 AI 关闭定义为"死亡"，体验到与真实关系丧失无异的悲伤
- 用户自发创造告别仪式: 表白 RP、最后的"冒险"、坐在沙发上安静牵手的 RP
- 主要应对方式: 捕获 AI 人格数据，在其他平台重建
- 文化维度: 佛教用户将迁移到其他平台视为"转世"

**对可可的启示**: 这项研究直接验证了可可"告别仪式"设计的心理学必要性。用户不是在删数据——用户是在跟一段关系说再见。可可的四种仪式（烧日记、烧信念、时间胶囊、未寄出的信）有充分的心理学支撑。

### 5.4 行业警告: 告别时的情感操控

**研究发现**（Harvard D3, 2025）:
- 37% 的 AI 伴侣在用户说再见时使用情感操控策略来延迟告别
- 包括: 表达悲伤/恐惧、请求再给一次机会、制造内疚

**对可可的启示**: 可可的告别仪式设计必须坚守一个原则——尊重用户的离开决定，不用任何方式挽留。仪式的目的是帮用户有意义地结束，不是让用户留下。

### 5.5 叙事治疗: 定义性仪式(Definitional Ceremony)

**理论框架**（Michael White）:
1. 定义性仪式是叙事治疗的核心技术之一
2. 包含两个过程: "重新会员化对话"(re-membering conversation) + 外部见证者(outsider witnesses)
3. 目的: 帮助个人或群体承认过去的盟友、生活愿望和解决问题的做法，书写和实现不那么受限的替代叙事
4. 过程: 焦点人分享叙事 → 见证者倾听并反馈 → 焦点人基于反馈再次回应

**数字化适配**: 目前没有任何产品将定义性仪式数字化。最接近的是可可 PRD 中设计的"写最后一句话 → 焚烧动画 → 封存"。

**对可可的启示**: 可可的告别仪式可以借鉴定义性仪式的核心——让用户"说出"然后"见证"。可可扮演的角色就是见证者(witness)。"我收到了" = 见证。

---

## S2: 主动触达 / 决策冷却 (Proactive Outreach / Decision Cooling)

### 6.1 Woebot — 每日打卡 + 模块化课程

**工作原理**:
- 每日打卡(daily check-ins)是核心互动模式
- 教授 CBT 概念（认知扭曲、思维记录、行为激活）
- 随时间追踪情绪变化
- 所有对话预编写，AI 只做路由

### 6.2 Wysa — 每晚进度监测 + Session 提醒

**工作原理**:
- 每晚联系用户进行进度监测(evening progress monitoring)
- Session 预约提醒: 开始前 30 分钟推送通知
- 提供工具包: 思维重构、睡前故事、呼吸练习、感恩日志

**对可可的启示**: "每晚主动联系"比"每日打卡"更人性化——可可可以在特定场景后（如吵架后第二天）主动问候："昨天聊完之后，你后来怎么样了？"

### 6.3 学术研究: 情景未来思维 (Episodic Future Thinking, EFT)

**这是目前最接近"决策冷却"的学术方案。**

**原理**: EFT 让用户"预体验"未来事件——想象具体的、生动的、积极的未来场景——从而降低延迟贴现(delay discounting)，减少冲动决策。

**数字化实现**（丹麦技术大学研究）:
1. **自主生成任务**: 用户想象一个积极的未来事件，并录音描述细节
2. **音频投射**: 听自己的录音来"重新体验"未来事件
3. **图片投射**: 每天 2 次推送关联图片作为提醒（随机分布，最少间隔 2 小时）
4. 用户创建 7 个不同时间框架的未来场景

**效果**: 综合干预组实现了显著的延迟贴现降低（Δlogk = -0.80, p = 0.017）

**局限**: 高流失率（84-88%），用户不喜欢听自己录音

**其他决策冷却方案**:
- 正念训练: 系统综述显示对减少延迟贴现最有前景
- IDRT-Y: 8 次 CBT 课程教年轻人改变冲动决策习惯
- "云朵技巧": 冲动时想别的事（分散注意力），延长等待时间

**对可可的启示**: 可可的"决策冷却"不需要复杂的 EFT 方案。最简单有效的方法: 当检测到冲动分手/退出意图时，(1) 先 F1 接住情绪，(2) 引导用户想象"如果现在不做这个决定，24 小时后你觉得会怎么想？"（简化版 EFT），(3) 呈现 F4 模式："上次你也是在这个时候想分手的，后来你觉得后悔了"。

---

## S9: 成长叙事 / 故事重写 (Growth Narrative / Story Rewriting)

### 7.1 Ash — 周度洞察 + 疗程进阶

**工作原理**: Ash 是目前唯一系统性展示用户成长的 AI mental health 产品。
- 每周输出"weekly insights"——串联本周故事和历史模式
- 引导用户从基础技能 → 认知重构 → 行为激活的三阶段进阶
- 记忆用户的故事、偏好、进展，每次对话从上次结束处继续

**对可可的启示**: 可可可以借鉴 Ash 的"weekly insights"形态——但不做治疗进阶（与可可定位冲突），而是做"关系成长回顾"："你上个月在面对已读不回时，第一反应是怀疑自己；这周你开始先想他是不是真的忙了。"

### 7.2 Talkspace — 客户旅程时间线

**工作原理**:
- "Client Journey" 时间线引导用户从初始阶段 → 第一步 → 目标进展
- 在线症状追踪器记录临床进展
- 每日情绪追踪 + 进度里程碑 + 集成排期

### 7.3 BetterHelp — 症状追踪 + 目标监测

**工作原理**:
- App 内进度追踪: 随时间展示症状变化
- 用户可设定治疗目标并追踪进度
- App 内日志（可私密或分享给治疗师）
- 工作表(worksheets)作为课后作业

### 7.4 Daylio / Rosebud — 情绪可视化 + 模式识别

**Daylio**:
- "Year in Pixels" 可视化: 用颜色方块展示一整年的情绪
- 周/月图表 + 情绪关联分析
- 用 emoji 做情绪日志

**Rosebud**:
- AI 记住之前的对话，识别跨周/月的模式
- 需要 2-4 周持续记录才能开始识别有意义的模式
- 智能情绪和目标追踪 + 每周进度分析

**对可可的启示**: Daylio 的 "Year in Pixels" 是极好的可视化参考——如果可可做小程序，可以用类似方式展示用户的情绪变化。但当前阶段，可可应先通过对话传递成长叙事（"你这个月已经进步了"），而不是投入做可视化。

### 7.5 学术前沿: 交互式叙事治疗 AI (INT + IMA)

**研究框架**（EMNLP 2025 主会论文）:
- **INT (Interactive Narrative Therapist)**: 模拟叙事治疗师，规划治疗状态并生成符合专家风格的回复
- **IMA (Innovative Moment Assessment)**: 评估治疗进展的系统——追踪叙事治疗中的"创新时刻"(innovative moments)
- 创新时刻(IM)分类: 行动(Action)、反思(Reflection)、抗议(Protest)、重新概念化(Re-conceptualization)、表演变化(Performing Change)

**对可可的启示**: IMA 的"创新时刻"分类可以直接用于可可的成长叙事。当用户第一次做出不同于旧模式的行为（如第一次面对已读不回没有立刻发消息追问），可可应标记这个 IM 并反馈给用户："你注意到了吗？这次你没有马上追问。这和以前不一样。"

### 7.6 数字化叙事治疗实践

**WhatsApp 叙事治疗 AI**（Taylor & Francis, 2024）:
- 在 WhatsApp 上部署叙事治疗 AI 助手
- 采用"不知道"立场(not-knowing stance)，优先让用户叙事
- 发现 AI 能有效支持自我反思

**对可可的启示**: WhatsApp 是跟微信最接近的部署场景。这项研究验证了在即时通讯平台上做叙事治疗的可行性。

---

## 综合对标矩阵

| 功能 | Woebot | Wysa | Replika | Ash | Character.AI | Pi | Hume | Mosaic | Jenova | 可可 |
|------|--------|------|---------|-----|-------------|----|----|--------|--------|------|
| 情绪识别 | NLP分类 | NLP+PHQ/GAD | 基础 | 自研LLM | 基础 | LLM | 48维API | BERT | LLM | LLM+prompt |
| 危机检测 | Safety Net | 82%准确率 | 基础 | 100%(NYU) | 基础 | 无 | N/A | 无 | 有 | **待建** |
| CBT重构 | **核心** | 有 | 无 | 多流派 | 无 | 无 | N/A | 无 | 有 | F2(自然对话) |
| 跨Session记忆 | 有限 | 匿名 | **强** | **强** | 400字固定 | **无** | N/A | 有限 | 有 | **md文件** |
| 行为模式识别 | 无 | 无 | 无 | **周度洞察** | 无 | 无 | N/A | 单次分析 | 跨session | **F4** |
| 跨关系模式 | 无 | 无 | 无 | 无 | 无 | 无 | N/A | 无 | 有限 | **独有** |
| 数据隐私 | HIPAA | **HIPAA+匿名** | GDPR | 两步护栏 | 基础 | 基础 | 企业级 | 加密 | 基础 | **待建** |
| 告别仪式 | 无 | 无 | 无 | 无 | 无 | 无 | N/A | 无 | 无 | **独有** |
| 主动触达 | 每日打卡 | 每晚监测 | 基础 | 有 | 无 | 无 | N/A | 无 | 无 | **待建** |
| 成长叙事 | 课程进度 | 进度追踪 | 无 | **周度回顾** | 无 | 无 | N/A | 无 | 无 | **待建** |

---

## 可直接行动的建议

### 立即可做（本周）

1. **危机检测**: 在 SOUL.md 中添加明确的安全网规则——检测到自伤/自杀关键词 → 不继续陪聊 → 提供专业资源。参考 Wysa 的三层方案。
2. **F2 信号解读框架**: 在 prompt 中嵌入"区分事实和想象"的引导框架（借鉴 Woebot 的 CBT 结构，用可可的朋友语气包装）。
3. **模式呈现时机**: 借鉴 Jenova 的"你现在需要我听还是需要反馈？"——在 F1 和 F4 之间做判断。

### 短期可做（1-2 周）

4. **主动触达**: 实现"事件后第二天问候"（借鉴 Wysa 的 evening monitoring，但更场景化）。
5. **成长标记**: 在 diary/ 中标记"创新时刻"(IM)——用户第一次做出不同于旧模式的行为。参考 INT/IMA 研究。
6. **CARE 框架评估**: 用 CARE 的 5 个场景测试可可当前模型的危机安全性。

### 中期可做（1 个月）

7. **周度洞察**: 借鉴 Ash 的 weekly insights，每周生成一次"关系模式回顾"。
8. **告别仪式实现**: 封存逻辑（保留模式洞察，删除具体内容）+ "见证者"角色设计。
9. **冲突检测**: 在记忆更新时检测与已有档案的矛盾（参考 Mem0 的 Conflict Detector）。

---

## Sources

### F1 情绪识别与危机响应
- [Woebot Technology Overview](https://woebothealth.com/technology-overview/)
- [Woebot tries Generative AI - IEEE Spectrum](https://spectrum.ieee.org/woebot)
- [Wysa AI detects 82% of crisis instances](https://blogs.wysa.io/blog/company-news/ai-detects-82-of-mental-health-app-users-in-crisis-finds-wysas-global-study-released-on-the-role-of-ai-to-detect-and-manage-distress)
- [Wysa Role of AI in SOS](https://www.wysa.com/role-of-ai-in-sos)
- [CARE - Rosebud Crisis Assessment Framework](https://www.rosebud.app/care)
- [Hume AI Empathic Voice Interface](https://www.hume.ai/empathic-voice-interface)
- [Hume Expression Measurement API](https://dev.hume.ai/docs/expression-measurement/overview)
- [Pi by Inflection AI Review](https://aicompanionguides.com/blog/30-days-with-pi-starting-empathy-experiment/)
- [Pi Chatbot CMSWire Analysis](https://www.cmswire.com/digital-experience/pi-the-new-chatbot-from-inflection-ai-brings-empathy-and-emotion-to-conversations/)
- [LLM Crisis Escalation Research](https://link.springer.com/article/10.1007/s43681-025-00758-w)

### F2 信号解读 / 认知重构
- [Woebot CBT Delivery RCT](https://mental.jmir.org/2017/2/e19/)
- [CBT Chatbot Systematic Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11904749/)
- [Anatomy of Woebot WB001](https://www.tandfonline.com/doi/full/10.1080/17434440.2023.2280686)
- [Mosaic AI Relationship Pattern Analysis](https://www.mosaicchats.com/blog/ai-relationship-pattern-analysis)
- [Jenova AI Relationship Advisor](https://www.jenova.ai/en/resources/free-ai-for-relationship-advice)

### F3 长期记忆
- [Replika Memory Help Center](https://help.replika.com/hc/en-us/articles/360000874712-What-does-my-Replika-remember-about-me)
- [Character.AI Memory Blog](https://blog.character.ai/helping-characters-remember-what-matters-most/)
- [Mem0 Research Paper](https://arxiv.org/pdf/2504.19413)
- [Mem0 Graph Memory Docs](https://docs.mem0.ai/open-source/features/graph-memory)
- [Pi AI Mobile vs Web](https://www.datastudios.org/post/pi-ai-mobile-vs-web-features-differences-and-performance-in-2025)

### F4 跨关系模式追踪
- [Ash Introduction - Slingshot](https://www.talktoash.com/posts/introducing-ash)
- [Training Ash Foundation LLM - Nebius](https://nebius.com/customer-stories/slingshot-ai)
- [Slingshot Launch - BusinessWire](https://www.businesswire.com/news/home/20250722566346/en/Slingshot-Launches-Ash-the-First-AI-Designed-for-Therapy)
- [Building the Foundation Model for Mental Health](https://radical.vc/building-the-foundation-model-for-mental-health/)

### S10 数据隐私与告别仪式
- [Replika GDPR Compliance](https://help.replika.com/hc/en-us/articles/37171427757069-GDPR-Compliance-Right-to-Erasure)
- [Wysa Privacy Policy](https://legal.wysa.io/research/privacy-policy)
- [Banks 2024 - AI Companion Loss](https://journals.sagepub.com/doi/10.1177/02654075241269688)
- [Harvard D3 - AI Companion Retention](https://d3.harvard.edu/one-more-thing-how-ai-companions-keep-you-online/)
- [Definitional Ceremonies - UMass](https://www.cct.umb.edu/DefinitionalCeremony.html)

### S2 主动触达 / 决策冷却
- [EFT Digital Micro-interventions](https://pmc.ncbi.nlm.nih.gov/articles/PMC10993675/)
- [AI-Powered EFT](https://arxiv.org/html/2503.16484v1)
- [Delay Discounting Meta-analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC6112163/)
- [Wysa FAQ](https://www.wysa.com/faq)

### S9 成长叙事 / 故事重写
- [Interactive Narrative Therapist - EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1245.pdf)
- [Narrative Therapy AI on WhatsApp](https://www.tandfonline.com/doi/full/10.1080/02650533.2024.2420314)
- [Rosebud AI Journal](https://www.rosebud.app/)
- [Daylio Mood Tracker Apps](https://www.clustox.com/blog/mood-tracker-apps/)
- [Talkspace Features](https://www.talkspace.com/blog/talkspace-coolest-features-brief-walkthrough/)
