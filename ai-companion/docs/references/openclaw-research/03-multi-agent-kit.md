# 调研报告：OpenClaw Multi-Agent Kit 与心情可可适用性分析

> 调研日期：2026-04-05
> 项目源码：`/Users/jianghongwei/Documents/GitHub/openclaw-research/openclaw-multi-agent-kit/`
> 心情可可工作区：`/Users/jianghongwei/Documents/moodcoco/ai-companion/`

---

## 一、项目概述

openclaw-multi-agent-kit 是一套基于 OpenClaw + Telegram Supergroup 的多 Agent 协作模板库。**不是代码库**——全部由 Markdown 模板、JSON 配置片段、文档组成，不含可执行代码。

核心场景：10 个自治 Agent（Orchestrator / Coder / QA / DevOps / Researcher / Growth / Content / Community / LeadGen / Ops），通过 Telegram Supergroup 的 Topic 频道协作，面向**SaaS 产品团队自动化运营**。

---

## 二、10 Agent 协作架构详解

### 2.1 组织结构

```
         Human
           │
      Orchestrator（总调度）
       ┌────┼────┐
    Build  Research  Social   Leads   Ops
    团队    团队     团队     单Agent  单Agent
  ┌──┼──┐
Coder QA DevOps  Researcher+Growth  Content+Community
```

- **团队制**：2-3 个 Agent 共享一个 Telegram Topic，Topic = 工作流车道（workflow lane），不是 Agent 房间
- **Primary + Secondary 模型**：Primary Agent 默认响应 Topic 消息，Secondary 只在 @mention 或 sessions_send 触发时响应
- **Orchestrator 不下场干活**：只协调、跟踪、蒸馏，通过 subagents 委派

### 2.2 三种 Telegram 路由模型

| 模型 | 机制 | 适用场景 |
|------|------|----------|
| **Multi-bot routing** | 每个 Agent 独立 Bot Token，各自身份可见 | 需要可见人格差异 |
| **Native topic routing** | 一个 Bot，内部按 Topic ID 路由到不同 Agent | 用户侧看到一个 Bot，后端多脑 |
| **DM forum topics** | 私聊中创建 Topic | 1:1 隐私场景 |

**心情可可关键洞察**：Native topic routing 模式——用户看到一个可可，但后端可以是多个内部 Agent——天然适合情绪陪伴场景（用户不应感知到"被交接给了不同的 AI"）。

### 2.3 sessions_send 交接机制

Telegram 的硬限制：**Bot 之间看不到彼此消息**。所有 Agent 间通信必须通过 OpenClaw 的 `sessions_send`。

**标准交接格式**（HANDOFF/ACK/DONE/BLOCKED 四状态）：

```
sessions_send(agentId="target", message="HANDOFF
from: agent-a
to: agent-b
task_id: xxx
priority: P1
summary: 一行概述
context: 上下文
deliver_to: telegram:group:topic
deadline: asap
done_when:
- 验收条件1
- 验收条件2")
```

接收方响应：
- **ACK**（2分钟内）→ 确认接手 + ETA
- **DONE** → 交付物 + 证据
- **BLOCKED** → 阻塞原因 + 选项 + 建议

**核心设计原则**：
- 禁止自由格式交接（free-form handoff）
- 单向链条 + 人类检查点，防止循环触发
- 最大重试次数后自动升级到 Orchestrator

### 2.4 共享 Workspace 文件

| 文件 | 写入者 | 读取者 | 用途 |
|------|--------|--------|------|
| THESIS.md | Human/Orchestrator | 全部 Agent | 业务北极星 |
| SIGNALS.md | Research Agent | 全部 Agent | 情报中心 |
| FEEDBACK-LOG.md | 任何 Agent | 全部 Agent | 风格修正记录 |
| SUPERGROUP-MAP.md | Orchestrator | 全部 Agent | Topic ↔ Agent 映射表 |

协作机制：**文件即 API**——Agent 不通过接口交换数据，而是通过读写共享 Markdown 文件。Research 写 SIGNALS.md，Growth 读 SIGNALS.md 做分析，避免 sessions_send 产生循环依赖。

### 2.5 Skill 系统

- 路径约定：`agents/<agent>/skills/<skill-name>/SKILL.md`
- YAML frontmatter + Markdown body
- 自动加载：OpenClaw 在 session 开始时读取 Agent skills/ 目录下所有 SKILL.md
- 可从 ClawHub 一键安装
- 与 SOUL.md 的分工：SOUL.md 定义 Agent 是谁，SKILL.md 定义 Agent 如何执行特定流程

---

## 三、与心情可可的适用性分析

### 3.1 当前心情可可架构

- **单 Agent（coco）**，模型 minimax-m2.7 + thinking: high
- **20 个 Skills**（base-communication / crisis / diary / see-pattern / relationship-guide / weekly-reflection 等）
- **memU 记忆系统**（通过 memu_bridge.py 读写，三维 Category：人物/事件/自我）
- **安全前置检查**：每条消息必检 P0/P1 危机信号
- **Tool 强制输出**：ai_message / ai_options / ai_safety_brake
- 用户渠道：微信（不是 Telegram）

### 3.2 多 Agent 拆分可能性

| 候选 Agent | 职责 | 拆分理由 | 拆分难度 |
|-----------|------|----------|----------|
| **Safety Agent** | P0/P1 危机检测、QPR 流程 | 安全检查独立于对话逻辑，可用更快/更便宜模型预筛 | **低** |
| **Memory Agent** | memU 读写、记忆整理、周记生成 | 记忆整理是后台任务，不应阻塞对话 | **中** |
| **Pattern Agent** | 模式识别、成长故事、周反思 | 需要长上下文分析历史数据，与实时对话节奏不同 | **中** |
| **Core Coco** | 实时对话、情绪陪伴、Scene Routing | 主 Agent，承担用户体验 | 已存在 |

### 3.3 适用性判断

#### 适用的模式

1. **Native Topic Routing（内部路由，用户无感知）**
   - 用户始终和"可可"对话，后端根据消息类型路由到不同内部 Agent
   - 类似 multi-agent-kit 的"一个 Bot 多个脑"模式
   - 但心情可可是微信渠道，需要确认 OpenClaw 微信 binding 是否支持 topic 概念

2. **共享 Workspace 文件协调**
   - USER.md、MEMORY.md 已经是共享上下文文件
   - 多 Agent 场景下 memU 记忆系统可以作为 SIGNALS.md 的等价物
   - Pattern Agent 写入模式发现 → Core Coco 读取用于对话

3. **Safety Agent 独立运行**
   - 最有价值的拆分点：安全检查与对话逻辑解耦
   - 可用廉价/快速模型（haiku 级别）做第一层危机信号筛查
   - 检测到 P0 信号时通过 sessions_send 立即接管对话
   - 降低主 Agent 每条消息的处理负担

4. **后台记忆整理（Cron 触发）**
   - multi-agent-kit 的 cron 模式天然适合：每 30 分钟或对话结束后触发 Memory Agent 整理
   - 避免告别时的强制写入阻塞用户体验

#### 不适用 / 需要大幅改造的模式

1. **Telegram Supergroup Topic 架构**
   - 心情可可是微信公众号/个人微信渠道，不是 Telegram
   - Topic 路由、requireMention、groupPolicy 等概念不直接适用
   - 需要微信层面的消息路由机制（可能通过 OpenClaw 微信 channel 的内部 binding 实现）

2. **HANDOFF/ACK/DONE 严格协议**
   - 情绪陪伴场景不是任务工作流，没有明确的"任务完成"概念
   - Agent 间交接需要**无缝**——用户说了一句危机相关的话，不能等 2 分钟 ACK
   - 需要改造为：同步前置拦截（Safety）+ 异步后台处理（Memory/Pattern）

3. **Multi-bot 可见身份**
   - 情绪陪伴场景下，用户必须感知只有一个"可可"在和他聊
   - 绝对不能出现"你已被转接给安全顾问"之类的体验断裂
   - 所有 Agent 必须共享同一个输出人格

4. **10 Agent 规模**
   - 心情可可最多需要 3-4 个内部 Agent，10 个严重过度工程
   - 每多一个 Agent 就多一层 sessions_send 链路和调试复杂度

---

## 四、成本收益评估

### 4.1 升级到多 Agent 的收益

| 收益 | 影响 | 量化估计 |
|------|------|----------|
| 安全检查提速 | Safety Agent 用快速模型预筛，主 Agent 减少每条消息处理时间 | 每条消息省 200-500ms |
| 记忆整理不阻塞 | 告别写入从同步变异步，用户体验更流畅 | 告别响应快 2-3 秒 |
| 模型成本优化 | Safety 用 haiku、Memory 用 haiku、Core 用 m2.7 | 估计省 15-25% token 成本 |
| 关注点分离 | Safety 逻辑不再混在 AGENTS.md 的 800+ 行规则里 | 维护性显著提升 |
| 独立迭代 | 改安全策略不影响对话体验，改记忆逻辑不影响安全 | 开发效率提升 |

### 4.2 升级成本

| 成本项 | 估计工时 | 风险 |
|--------|---------|------|
| 设计 Agent 拆分边界 | 2-3 天 | 拆错了比不拆更差——对话连贯性是核心价值 |
| 实现 sessions_send 交接 | 1-2 天 | 需要确认 OpenClaw 微信渠道支持内部 Agent 路由 |
| Safety Agent 独立化 | 2 天 | 需要测试延迟——安全检查必须在主回复之前完成 |
| Memory Agent 异步化 | 2-3 天 | memU bridge 需要适配多 Agent 读写并发 |
| 联调 + 回归测试 | 3-5 天 | 多 Agent 间状态同步是最大坑 |
| **总计** | **10-15 天** | |

### 4.3 关键风险

1. **对话连贯性断裂**：多 Agent 共享上下文不完整，用户感知到"可可忘了刚才说的话"
2. **延迟增加**：sessions_send 交接增加一轮 LLM 调用延迟
3. **调试复杂度**：单 Agent 出问题看一个日志，多 Agent 要追踪交接链路
4. **微信渠道限制**：不确定 OpenClaw 微信 binding 是否支持 multi-agent-kit 的 topic routing 等价能力

---

## 五、建议

### 5.1 当前阶段：不升级

心情可可当前 20 个 Skills + 单 Agent 架构已经能覆盖所有功能。在核心评估标准（看见情绪/原因/模式/方法/安全边界）还没全部达到 9.0 之前，**优化 Skill 质量比拆分 Agent 更有 ROI**。

多 Agent 的收益主要在运维效率和成本优化，不在用户体验提升。而心情可可当前瓶颈是体验质量，不是运维效率。

### 5.2 未来可考虑的第一步：Safety Agent 独立

如果要迈出多 Agent 第一步，**Safety Agent 是最安全的切入点**：

- 职责边界清晰：P0/P1 危机检测 + QPR 流程
- 与对话逻辑低耦合
- 可用 haiku 级模型降低成本
- 不影响用户感知（用户不知道有安全 Agent 在运行）

实现方式：每条用户消息先过 Safety Agent（同步拦截），无危机信号才路由到 Core Coco。

### 5.3 可直接复用的模式

无需升级到多 Agent，以下模式可以直接借鉴到当前单 Agent 架构：

| 模式 | 来源 | 在心情可可的应用 |
|------|------|----------------|
| 共享文件协调 | SIGNALS.md / FEEDBACK-LOG.md | 已有 USER.md + memU，可增加 PATTERN-LOG.md 记录发现的模式 |
| Memory Distillation Cadence | Advanced Practices #6 | 日维度追加原始记忆，周维度蒸馏为持久洞察——已有 weekly-reflection skill 可对齐 |
| Escalation Budget | Advanced Practices #7 | 安全检查最大重试次数，避免无限追问循环 |
| Two-Speed Model Policy | Advanced Practices #5 | 安全筛查用快模型，深度对话用 m2.7——可通过 Skill 内切换 fallback 实现 |
| Strict Handoff Contract | ACK/DONE/BLOCKED | 如果未来拆分，直接复用此协议格式 |

---

## 六、关键文件索引

| 文件 | 路径 | 内容 |
|------|------|------|
| README | `openclaw-multi-agent-kit/README.md` | 项目总览、架构图、10 Agent 列表 |
| AI 安装指南 | `openclaw-multi-agent-kit/INSTRUCTIONS.md` | 8 阶段完整部署流程 |
| 交接标准 | `openclaw-multi-agent-kit/docs/inter-agent-handoff-standard.md` | HANDOFF/ACK/DONE/BLOCKED 格式 |
| Topic 架构 | `openclaw-multi-agent-kit/docs/telegram-channel-architecture.md` | 工作流车道设计 |
| 扩展指南 | `openclaw-multi-agent-kit/docs/scaling.md` | 何时加 Agent、成本、防循环 |
| 高级实践 | `openclaw-multi-agent-kit/docs/advanced-openclaw-practices.md` | 13 条生产实践 |
| Skill 系统 | `openclaw-multi-agent-kit/docs/skills-system.md` | 原生 Skill 系统全文档 |
| 完整配置 | `openclaw-multi-agent-kit/examples/full-team.json` | 10 Agent openclaw.json 示例 |
| 最小配置 | `openclaw-multi-agent-kit/examples/minimal-team.json` | 3 Agent 最小可用配置 |
| Orchestrator 模板 | `openclaw-multi-agent-kit/templates/soul/orchestrator.md` | 调度 Agent 人格模板 |
