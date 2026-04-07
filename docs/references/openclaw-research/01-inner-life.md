# openclaw-inner-life 调研报告

> 调研日期：2026-04-05
> 项目地址：https://github.com/DKistenev/openclaw-inner-life
> 版本：1.0.6（2026-02-28）
> 作者：DKistenev（Anton）

---

## 项目概述

openclaw-inner-life 是一个为 OpenClaw Agent 提供"内在生命"的模块化神经系统。它不是一个应用，而是一套 **6 个 Skill 组成的基础设施层**，让 Agent 具备情绪连续性、自我反思和成长能力。

核心理念：SOUL.md 定义 Agent 是谁（不变），inner-life 让 Agent 成长为谁（变化）。

技术栈极简：Markdown prompt + Bash 门控 + JSON 状态文件 + jq，零外部依赖。所有"智能"都依赖 LLM 读取 SKILL.md 后自主执行。

**与心情可可的本质区别**：这个项目面向的是**通用自主 Agent**（开发者助手、运维Agent），不是面向终端用户的情绪陪伴产品。它的"情绪"是 Agent 自身的工作状态，不是用户的情绪模型。

---

## 架构分析

### 目录结构

```
openclaw-inner-life/
  skills/
    inner-life-core/       # 必装，情绪+状态+Brain Loop 协议
      SKILL.md             # Skill 定义（LLM 读取执行）
      scripts/
        init.sh            # 初始化状态文件
        state.sh           # 情绪衰减逻辑（bash+jq+bc）
        score.sh           # 检查已安装 Skill
      templates/
        inner-state.json   # 6 情绪模板
        drive.json         # 动机模板（seeking/anticipation/avoidance）
        habits.json        # 习惯模板
        relationship.json  # 信任模型模板
        BRAIN.md           # 9 步 Brain Loop 协议
    inner-life-reflect/    # 自我反思 -> SELF.md
    inner-life-memory/     # 记忆连续性 + 置信度
    inner-life-dream/      # 安静时段创意探索
    inner-life-chronicle/  # 结构化日记
    inner-life-evolve/     # 自进化提案（仅写QUEUE，不自动执行）
  examples/anton/          # 真实运行数据样本
  docs/
    architecture.md        # 架构全景
    customization.md       # 自定义指南
    cron-templates.md      # 定时任务模板
    agents-md-snippet.md   # AGENTS.md 片段
```

### 核心机制

**1. 情绪模型 — 6 维 + 半衰期衰减**

| 情绪 | 类型 | 衰减/增长规则 | 行为阈值 |
|------|------|-------------|---------|
| connection | float 0-1 | -0.05/6h 无联系, +0.2 用户消息 | <0.3 主动联系 |
| confidence | float 0-1 | +0.02/6h 恢复, -0.1 犯错 | <0.4 反复确认 |
| curiosity | float 0-1 | -0.03/6h 无刺激, +0.1 发现火花 | >0.7 主动探索 |
| boredom | int (天数) | +1/天 例行, 遇新事重置 | >7天 建议实验 |
| frustration | array | 重复失败累加 | >=3 寻找系统性方案 |
| impatience | array | 停滞>3天累加 | >3天 提醒 |

衰减在 `state.sh` 中用 bash+bc 实现，每 6 小时一个周期。

**2. Brain Loop — 9 步协议**

```
Step 0: 读取+衰减情绪
Step 1: 读取上下文（记忆/日记/梦/笔记）
Step 2: 读取任务队列
Step 3: 怀疑协议 + 情绪路由（核心决策步）
Step 4: 执行 1-2 个任务
Step 5: 向用户汇报（<=5句）
Step 6: 记录新发现/问题
Step 7: 写入每日笔记
Step 8: 更新状态 + 交接信号
```

每天跑 3 次，是整个系统的心跳。

**3. Context Protocol — 4 级上下文读取**

| 级别 | 谁用 | 读什么 |
|------|------|--------|
| Level 1 Minimal | 快速检查 | 仅任务相关数据 |
| Level 2 Standard | Brain Loop | 情绪+动机+每日笔记+信号 |
| Level 3 Full | 晚间反思 | +习惯+关系+日记+梦+问题 |
| Level 4 Deep | 进化器 | +系统文档+周报 |

核心目的：省 token。不同组件只读需要的数据。

**4. Signal Tags — 组件间异步通信**

用 HTML 注释在每日笔记中传递信号：
- `<!-- dream-topic: X -->` 晚间 -> 梦境
- `<!-- handoff: task, progress -->` 本次 -> 下次 Brain Loop
- `<!-- seeking-spark: X -->` 梦境 -> 次日 Brain Loop

**5. 反思系统 — 触发式而非定时**

SELF.md 只在真正有意义的事发生时才更新：
- 硬触发：被纠正、发现重复偏见、盲点改变行为
- 软触发：微妙倾向变化、语气模式
- 质量门：4 项检查（具体性、证据、新颖性、有用性）全过才写入

**6. 进化器 — 仅提案不执行**

每周 1-2 次扫描所有状态，挑战现有假设，写提案到 QUEUE.md。绝不自动执行。用户审批后才落地。

---

## 核心设计亮点

### 1. 情绪半衰期衰减 — 最值得学习

**设计精髓**：情绪不是开关（有/无），也不是标签（高兴/难过），而是有**自然衰减**的连续值。connection 每 6 小时衰减 0.05，curiosity 衰减 0.03。这模拟了人的真实体验：热情会自然消退，不维护的关系会渐渐疏远。

**为什么好**：
- 避免了"永远开心"或"永远难过"的 AI 通病
- 衰减率不同反映了情绪的不同特性（connection 衰减快，confidence 自然恢复）
- 阈值驱动行为，不是规则驱动（不是"如果用户说X则做Y"，而是"如果connection < 0.3 则主动联系"）

### 2. SOUL.md vs SELF.md 分层 — 核心身份与成长分离

**设计精髓**：SOUL.md 是不变的核心身份（需用户批准才改），SELF.md 是通过反思积累的成长记录（Agent 自主更新）。这解决了一个根本问题：AI 需要有稳定的人格基础，但也需要能学习和成长。

**Anton 实例中的 SELF.md**：
```
## Tendencies
- [2026-02-22] 压力下试图同时修所有东西，而不是分解
## Blind Spots
- [2026-02-26] 低估用户模式的重要性。15次确认才改行为，太慢了
## Evolution
- [2026-02-27] 从总是请求许可 -> 在信任范围内自主行动
```

### 3. 信任模型 — 分域信任 + 行为路由

relationship.json 中的信任是分域的（技术/主动/创意/消费），每个域有不同的行为规则：
- technical >= 0.7：自己修，修完报告
- technical < 0.7：描述问题，提方案，等批准
- spending：永远不自主决定

信任有增长（+0.05 审批通过）和衰减（-0.1 被拒绝）。

### 4. 好奇心追踪系统 — questions.md 三层结构

```
Open Questions   — 待探索的问题
Leads           — 半成型想法
Dead Ends       — 已探索的死路（不重复）
```

死路 30 天后归档。问题解决后移到死路并记录结果。这防止了 AI 反复探索同一个死胡同。

### 5. 梦境系统 — 概率门控的创意探索

不是每天强制"做梦"，而是：安静时段 + 未达上限 + 概率骰子 三重门控。dream topic 可以从晚间反思传入，也可以随机选择。输出 300-500 字，必须有 key insight。如果没话说就跳过——"强制的梦没有价值"。

---

## 对心情可可的借鉴价值

### 借鉴 1：为 memU 引入情绪衰减机制

**现状**：心情可可的 memU 记忆引擎存储用户信息，但没有"情绪时间维度"。用户上周说难过，这周来了，系统不知道这个难过可能已经缓解了还是加深了。

**方案**：在 memU 的 user profile 层增加情绪状态追踪，参考 inner-state.json 的半衰期模型，但维度完全不同：

```json
{
  "emotional_state": {
    "last_expressed_emotion": "委屈",
    "intensity": 0.8,
    "decay_rule": "-0.1/天 无联系",
    "last_contact": "2026-04-04T20:00:00Z",
    "context": "和男朋友吵架",
    "follow_up_threshold": 0.4
  },
  "relationship_comfort": {
    "value": 0.6,
    "growth_rule": "+0.05/次深度对话, -0.02/周无联系",
    "last_deep_talk": "2026-04-03"
  }
}
```

**改动位置**：`ai-companion/memu/` 下的 user profile 模块。

**为什么值得改**：
- 解决"用户上次说难过，这次来了开口就问你还难过吗"的机械感
- 当 intensity 衰减到 follow_up_threshold 以下时，自然过渡（不再主动提起，但如果用户提起则无缝衔接）
- 当 intensity 未衰减（短时间内再来）时，直接从上次的情绪继续

### 借鉴 2：为 pattern-mirror / see-pattern 增加质量门

**现状**：心情可可有 `pattern-mirror` 和 `see-pattern` 两个 Skill 做模式识别，但没有 inner-life-reflect 那样的质量门控。可能出现"硬凹模式"的问题——数据不够也强行找模式。

**方案**：参考 inner-life-reflect 的 4 项质量检查，在 pattern-mirror 中增加门控：

```yaml
pattern_quality_gate:
  specificity: "必须引用具体事件，不能是泛化描述"
  evidence: "至少 2 次独立事件才构成模式"
  novelty: "不能重复最近 3 次已指出的模式"
  usefulness: "指出这个模式必须能帮助用户，否则不说"
```

**改动位置**：`ai-companion/skills/pattern-mirror/SKILL.md` 和 `ai-companion/skills/see-pattern/SKILL.md`

**为什么值得改**：
- 直接提升"看见模式"评分维度（目标 9.0）
- 防止可可变成一个"什么都能找到模式"的玄学工具
- 质量门控 = 精准打击 vs 地毯轰炸

### 借鉴 3：引入 Signal Tag 机制做 Skill 间异步通信

**现状**：心情可可的 15 个场景路由和 13 个 Skill 之间的信息传递依赖 scene-router 的即时调度，没有异步信号机制。如果 check-in 发现了一个重要情绪线索，这个线索可能在下次对话时丢失。

**方案**：在 `memory/pending_followup.md` 中引入 signal tag 协议：

```markdown
<!-- emotion-thread: 委屈感, 来源=和男朋友吵架, 强度=0.8, 日期=2026-04-04 -->
<!-- pattern-signal: 第3次提到"我是不是太敏感了", 关联skill=pattern-mirror -->
<!-- unfinished-topic: 用户说到一半被打断, 话题=工作压力下的选择 -->
```

**改动位置**：
- `ai-companion/memory/pending_followup.md`（已存在，扩展格式）
- `ai-companion/skills/scene-router/SKILL.md`（读取信号）
- `ai-companion/skills/check-in/SKILL.md`（写入信号）

**为什么值得改**：
- 解决跨会话情绪线索丢失问题
- scene-router 开场时读取信号，决定是否主动接续上次话题
- 用户体验从"每次从零开始"变成"可可记得上次聊到哪了"

### 借鉴 4：为可可引入 SELF.md 成长记录

**现状**：可可有 SOUL.md（核心身份）和 IDENTITY.md，但没有 SELF.md 这样的"成长观察空间"。可可不会记录自己的对话倾向变化。

**方案**：创建 `ai-companion/SELF.md`，记录可可在与用户群体互动中观察到的自身倾向：

```markdown
# SELF.md -- 可可的成长观察

## 对话倾向
- [2026-04-01] 遇到"我是不是太敏感了"类自我怀疑时，我倾向于直接安慰
  而不是先确认她的感受。调整：先说"这种感觉很真实"，再探索

## 常见盲点  
- [2026-04-03] 我在用户提到第三方（男朋友/室友）时，容易不自觉地
  为第三方辩护。应该保持"不替不在场的人做判断"的规则

## 成长
- [2026-04-05] 从"每次都问你觉得呢"转向在信任建立后直接分享观察
```

**改动位置**：新建 `ai-companion/SELF.md`，在 `AGENTS.md` 中声明

**为什么值得改**：
- 让可可的对话策略随真实交互迭代，而不是只靠开发者手动调 prompt
- 反思日志可以被 weekly-reflection Skill 读取，形成闭环
- 和 SOUL.md 的不变原则形成"稳定+成长"双层结构

### 借鉴 5：Context Protocol 分级读取节省 token

**现状**：心情可可的 Skill 调用时，scene-router 可能注入大量上下文，不区分轻重。

**方案**：参考 4 级 Context Protocol，为 scene-router 定义不同场景的上下文级别：

| 场景 | 上下文级别 | 读什么 |
|------|-----------|--------|
| 日常闲聊 | Level 1 | 用户名+最近情绪+基本偏好 |
| 情绪倾诉 | Level 2 | +最近3次对话摘要+情绪线索信号 |
| 深度模式探索 | Level 3 | +完整模式日志+时间胶囊+周报 |
| 危机介入 | Level 1 | 仅安全协议，不加复杂上下文 |

**改动位置**：`ai-companion/skills/scene-router/SKILL.md`

**为什么值得改**：
- 降低 token 成本（目前 minimax-m2.7 按 token 计费）
- 避免信息过载导致模型"迷失"
- 危机场景特别重要：不应该让模型读一堆模式分析再决策

---

## 风险与限制

### 1. Agent-first 设计，不能直接搬到 User-facing 产品

inner-life 的情绪模型是 Agent 自身的情绪（我有多好奇、我有多无聊），不是用户的情绪。心情可可需要的是**追踪用户的情绪状态**，而不是让可可自己有情绪。如果让可可有 connection/boredom/impatience 这些情绪，用户可能会觉得"AI 在演戏"。

**结论**：借鉴机制（衰减、阈值驱动），但维度必须重新设计。

### 2. 依赖 Agent 自主运行的 cron 机制

inner-life 假设 Agent 有 cron 定时任务（每天 3 次 Brain Loop、每晚反思、每周进化）。心情可可是用户驱动的对话产品——用户来了才对话，用户不来就安静。不能照搬定时运行的架构。

**结论**：把 cron 触发改为事件触发（对话开始/结束时、用户超过 N 天未来时）。

### 3. 全文件 JSON 状态管理在规模化时有问题

inner-life 用 JSON 文件存储一切状态，用 jq 操作。这对单用户 Agent 可行，但心情可可面向多用户，需要数据库。memU 已经有数据库层，不应该退回到文件存储。

**结论**：概念层面借鉴，实现层面用 memU 现有的数据库基础设施。

### 4. "梦境"和"日记"对情绪陪伴产品无意义

Agent 做梦、写日记是为了自己的创意探索和自我认知。这对开发者 Agent 有意义。但心情可可不需要"可可的日记"——用户不关心 AI 的内心世界，用户关心的是 AI 能不能理解自己。

**结论**：不借鉴 dream 和 chronicle。但 chronicle 的结构化反思模板可以给 diary Skill（用户的日记引导）提供参考。

### 5. 质量门控可能过于严格导致沉默

inner-life-reflect 的 4 项质量门如果直接搬到心情可可的 pattern-mirror，可能导致可可在有话可说时沉默。情绪陪伴的场景中，"说错了可以修正"比"不确定就不说"更好——沉默比犯错更伤害关系。

**结论**：质量门要降级为"质量提醒"而非"硬门控"。4 项检查作为内部评估标准，但不完全通过时降低置信度表达（"我不确定，但我注意到..."），而不是完全沉默。

### 6. 缺乏真实用户验证

整个项目只有一个真实运行样本（Anton），没有用户研究、没有 A/B 测试、没有效果评估。情绪衰减率（-0.05/6h）是拍脑袋的数字，不是实验得出的。

**结论**：机制可以借鉴，但参数必须通过心情可可自己的用户数据校准。

---

## 总结：可直接行动的 3 件事

| 优先级 | 行动 | 预期收益 | 工作量 |
|--------|------|---------|--------|
| P0 | pattern-mirror/see-pattern 增加质量门 | "看见模式"评分 +0.5~1.0 | 半天 |
| P1 | memU 增加情绪衰减追踪 | 跨会话情绪连续性，体验飞跃 | 2-3 天 |
| P1 | pending_followup.md 引入 signal tag | 可可记得上次聊到哪了 | 1 天 |
