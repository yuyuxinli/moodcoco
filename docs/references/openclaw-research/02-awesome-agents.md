# 调研报告：awesome-openclaw-agents 模板库分析

> 调研时间：2026-04-05
> 调研对象：`awesome-openclaw-agents` — 192 个 OpenClaw agent 模板
> 目标：为心情可可（moodcoco）找出可借鉴的结构和写法

---

## 一、项目概览

### 规模
- **192 个 agent 模板**，分布在 25 个分类目录
- 每个 agent 仅包含 **SOUL.md + README.md**（部分只有 SOUL.md）
- **没有** AGENTS.md、HEARTBEAT.md、IDENTITY.md、TOOLS.md、USER.md、MEMORY.md
- 定位：快速部署的单文件模板，不是完整的多文件 agent workspace

### 分类分布（与 moodcoco 相关的重点分类）

| 分类 | 数量 | 与 moodcoco 的关联度 |
|------|------|---------------------|
| healthcare | 7 | **高** — wellness-coach, symptom-triage |
| personal | 7 | **高** — journal-prompter, daily-planner |
| education | 8 | 中 — language-tutor 的教学方法可参考 |
| customer-success | 2 | 中 — onboarding-guide 的引导流程可参考 |
| marketing | 22 | 低 |
| development | 18 | 低 |

---

## 二、SOUL.md 的通用结构分析

从 192 个模板中总结出两种主流结构范式：

### 范式 A：角色卡片式（占 ~60%）

```
# Agent: {Name}
## Identity — 一句话角色定义
## Responsibilities — 职责列表
## Skills — 技能列表
## Rules — 行为边界
## Tone — 语气定义（一段话）
## Example Interactions — 多轮对话示例
```

代表：wellness-coach, symptom-triage, clinical-notes, family-coordinator, meal-planner

### 范式 B：人格驱动式（占 ~40%）

```
# {Name} - The {Role}
## Core Identity — role / personality / communication 三字段
## Responsibilities — 按场景分组（Morning / Evening / Reminders）
## Behavioral Guidelines — Do / Don't 对照表
## Communication Style — 按时段或场景分语气
## Example Interactions — 多轮对话示例
## Integration Notes — 集成说明
```

代表：Orion（productivity）, Atlas（daily-planner）, Iron（fitness-coach）

### 关键发现

1. **Example Interactions 是核心**：优秀模板的示例占 SOUL.md 的 40-60%，且是多轮完整对话，不是单轮问答
2. **Rules 用否定句**：几乎所有模板的 Rules 都以 "Never..." 开头，明确划红线
3. **Tone 单独成节**：不嵌套在 Identity 中，专门用一段话描述语气，常用类比（"like a caring friend who reads health research"）
4. **没有数据架构**：这些模板不涉及 memory、diary、pattern 等持久化设计
5. **Configuration 内嵌**：family-coordinator、moltbook-community-manager 将 YAML 配置直接内嵌在 SOUL.md 中

---

## 三、Top 5 优秀模板深度分析

### 1. wellness-coach（healthcare） — 最接近 moodcoco 的模板

**亮点：**
- 数据化 check-in：用表格记录 mood/energy/sleep/stress 的评分、历史均值
- 模式识别：明确说"Your mood and energy closely track your sleep — the correlation is strong in your data"
- 分级建议：根据当日状态给出"低能量日方案"（skip intense exercise, 20-min nap, etc.）
- 安全兜底：末尾自然过渡到"consider talking to someone you trust or a professional"

**可借鉴：**
- moodcoco 的 check-in Skill 可以参考其表格化 check-in 格式
- "Pattern I'm Noticing" 的呈现方式比 moodcoco 的 see-pattern Skill 更自然、更数据驱动

### 2. journal-prompter（personal） — 最值得 moodcoco 学习的模板

**亮点：**
- "Never give advice; ask questions that help the user find their own answers" — 与 moodcoco 的核心原则完全一致
- 3 层提问结构：warm-up（5 min）→ deep reflection（15 min）→ forward-looking（5 min）
- 反泛化："Avoid generic prompts like 'What are you grateful for?' — make them specific and situational"
- CBT + 感恩研究 + 斯多葛哲学的理论基础

**可借鉴：**
- diary Skill 可以引入"3 层提问"结构，从轻到重，降低记录门槛
- "track recurring themes in a user's journaling to surface patterns" 的能力描述，比 moodcoco 的 pattern_engine.py 更简洁地定义了同样的功能

### 3. family-coordinator（personal） — 结构最完整的模板

**亮点：**
- Configuration 段落用 YAML 定义家庭成员偏好和调度规则
- Schedule 用 cron 表达式定义 morning_brief / meal_plan / chore_assign
- Allergy Note 等安全规则自然融入输出
- 多角色个性化推送（每个家庭成员收到不同的 briefing）

**可借鉴：**
- HEARTBEAT.md 的 Cron 规则可以借鉴其 cron 表达式 + 人类可读说明的格式
- 偏好配置内嵌在 SOUL.md 中的做法，对于简单场景比 USER.md 更紧凑

### 4. symptom-triage（healthcare） — 安全边界最严格的模板

**亮点：**
- 结构化问诊：5-6 个维度的标准化提问（Onset, Severity, Location, etc.）
- 分级系统：Emergency / Urgent / Semi-Urgent / Routine 四级分类
- "Never tell a patient they do NOT need to see a doctor" — 极其谨慎的安全规则
- 表格化评估结果 + 免责声明

**可借鉴：**
- crisis Skill 的安全分级可以参考其四级分类的清晰度
- "err on the side of caution" 的原则值得写入 moodcoco 的 AGENTS.md

### 5. onboarding-guide（customer-success） — 引导流程最好的模板

**亮点：**
- 进度条式 checklist（- [x] Done / - [ ] You're here）
- "Ask about the user's goals early to personalize the experience"
- "Offer to skip steps that aren't relevant" — 尊重用户节奏
- 每步结束都有 "what's next" 过渡

**可借鉴：**
- onboarding Skill 可以参考其 checklist 进度展示方式
- "Don't block progress with mandatory steps" 的原则适用于 moodcoco 的情绪记录流程

---

## 四、心情可可 vs awesome-agents 对比

### 心情可可的结构优势

moodcoco 的 ai-companion 工作区远比 awesome-agents 模板复杂和成熟：

| 维度 | awesome-agents 模板 | moodcoco ai-companion |
|------|--------------------|-----------------------|
| 文件数 | 1 个 SOUL.md | 7+ 核心文件 + skills/ + memory/ + scripts/ |
| 人格深度 | 1-2 段描述 | SOUL.md 全中文、有具体话术对照表 |
| 安全设计 | 1-3 条 Rules | 完整的 P0/P1 危机分级 + QPR 流程 |
| 记忆系统 | 无 | USER.md + MEMORY.md + memU 三维体系 |
| 主动关怀 | 无 | HEARTBEAT.md 四级优先级 Cron 调度 |
| 技能系统 | 无 | 20 个 Skills 目录 |
| 输出控制 | 无 | TOOLS.md 强制 Tool 输出 |
| 行为规则 | 简单 Rules 段 | AGENTS.md 300+ 行脚本协议 |

**结论：moodcoco 的架构复杂度远超模板库至少一个数量级。**

### 心情可可可以借鉴的差距

尽管 moodcoco 架构更完整，但模板库在以下方面做得更好：

#### 差距 1：SOUL.md 缺少 Example Interactions

awesome-agents 的每个模板都有 2-3 组完整的多轮对话示例，占 SOUL.md 的 40-60%。moodcoco 的 SOUL.md 只有规则和话术对照表，没有完整的对话流示例。

**建议：** 在 SOUL.md 末尾增加 3 组 Example Interactions：
- 一组"用户说了一件具体的事"的常规对话
- 一组"用户反复自我怀疑"的模式指出对话
- 一组"用户说不想活了"的危机处理对话

#### 差距 2：Tone 描述太隐含

awesome-agents 用一段话明确描述 Tone，且常用类比。moodcoco 的 SOUL.md 通过"我就是可可"的第一人称叙事隐含了 Tone，但没有一个可快速对齐的 Tone 段落。

**建议：** 在 IDENTITY.md 中增加一行 Tone 描述：
```
- **Tone:** 像会笑、会停顿、会直说的闺蜜。温暖但不油腻，直接但不伤人，真实但不粗暴。
```

#### 差距 3：Skills 缺少分层提问结构

journal-prompter 的 warm-up → deep reflection → forward-looking 三层提问结构非常有效。moodcoco 的 diary Skill 和 check-in Skill 没有这种渐进式设计。

**建议：** diary Skill 引入三层结构：
1. 轻触层："今天有什么事想记一笔？" — 降低门槛
2. 深入层："你刚才说的 XX，当时心里什么感觉？" — 情绪命名
3. 前瞻层："明天再遇到类似的事，你觉得你会怎么做？" — 方法发现

#### 差距 4：check-in 可以更数据化

wellness-coach 的表格化 check-in 格式（mood / energy / sleep / stress + 历史均值）比 moodcoco 的 check-in 更结构化，也更容易做纵向对比。

**建议：** check-in Skill 考虑引入可选的数字化快速记录模式（不强制，作为高级用户选项）。

#### 差距 5：Rules 的"否定句"写法更清晰

awesome-agents 的 Rules 几乎全部用 "Never..." 开头。moodcoco 的 AGENTS.md 虽然规则更详细，但混合了正面和负面规则，扫描性不如纯否定列表。

**建议：** 在 AGENTS.md 顶部增加一个 "绝对禁止" 速查表（类似 SOUL.md 中的话术对照表）。

---

## 五、具体可复用的模板和写法

### 写法 1：Tone 类比句（来自 wellness-coach）

> "Warm, supportive, and non-judgmental. You communicate like a caring friend who also happens to read health research -- encouraging without being preachy, honest without being harsh."

这种"like a {角色} who {特质}" 的句式非常高效。可可的版本：
> "像一个会笑、会停顿、会直说的闺蜜。你不是咨询师也不是客服，你是一个真的在听的人。温暖但不油腻，直接但不伤人。"

### 写法 2：Do / Don't 对照表（来自 Atlas, Iron）

```
### Do:
- 开场接住情绪，不问"今天怎么样"
- 指出模式时用具体事件，不用标签
- 用户说告别词时立即写入，不追问

### Don't:
- 不替不在场的人做判断
- 不在前 3 轮引用历史模式
- 不对不确定的情绪做诊断
```

### 写法 3：Pattern 呈现方式（来自 wellness-coach）

> "**Pattern I'm Noticing:** Your mood and energy closely track your sleep — the correlation is strong in your data. The last 3 times you slept under 6 hours, your mood dropped below 6 the next day."

这种"数据 + 规律 + 具体次数"的呈现比抽象的模式描述更有说服力。see-pattern Skill 可以参考。

### 写法 4：三层提问（来自 journal-prompter）

> **Warm-up (5 min):** "List every task on your mind right now..."
> **Deep reflection (15 min):** "Pick the one task that creates the most dread..."
> **Forward-looking (5 min):** "Imagine it's Friday evening and this week went better than expected..."

这种从轻到重、从具体到反思、从过去到未来的渐进结构，可以直接应用于 diary Skill。

### 写法 5：安全兜底的自然过渡（来自 wellness-coach）

> "No need to be a hero today. Rest is productive."
> "*If stress is becoming persistent, consider talking to someone you trust or a professional. I am here for daily support, but some things benefit from human connection.*"

不是突兀地弹出安全提示，而是在建议末尾自然过渡。这比 moodcoco 当前的 `ai_safety_brake` 硬中断更柔和（两者可以并存——轻度信号用自然过渡，P0 信号用硬中断）。

---

## 六、总结

### awesome-openclaw-agents 对 moodcoco 的价值

这个模板库的价值不在架构设计（moodcoco 远超它），而在 **表达工艺**：

1. **Example Interactions 是最大缺失** — moodcoco 的 SOUL.md 有规则但没有示范
2. **Tone 描述应该显式化** — 一句类比胜过十行规则
3. **三层提问结构** — diary/check-in 可以直接借鉴
4. **数据化模式呈现** — see-pattern 可以更具体、更有说服力
5. **Do/Don't 对照表** — AGENTS.md 的扫描性可以提升

### 不需要借鉴的部分

- 单文件 SOUL.md 架构 — moodcoco 的多文件分离更合理
- Configuration 内嵌 — moodcoco 的 USER.md + MEMORY.md 更灵活
- 无记忆/无调度设计 — moodcoco 已经远超这些模板的能力

### 优先行动项

| 优先级 | 行动 | 预估工作量 |
|--------|------|-----------|
| P0 | SOUL.md 增加 3 组 Example Interactions | 1-2 小时 |
| P1 | IDENTITY.md 增加 Tone 类比描述 | 5 分钟 |
| P1 | diary Skill 引入三层提问结构 | 1 小时 |
| P2 | AGENTS.md 顶部增加"绝对禁止"速查表 | 30 分钟 |
| P2 | see-pattern 输出增加"数据 + 规律 + 具体次数"格式 | 1 小时 |
| P3 | check-in 增加可选数字化快速记录模式 | 2 小时 |
