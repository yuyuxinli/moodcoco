# 调研报告：openclaw-agents 多智能体对抗式协作系统

> 调研日期：2026-04-05
> 项目地址：github.com/shenhao-stu/openclaw-agents (v2.2.0)
> 调研目的：评估对抗式多 Agent 设计对心情可可「关系智能」场景的适用性

---

## 1. 项目概览

openclaw-agents 是一个面向 AI 学术科研的多 Agent 配置套件，提供 **9 个预配置 Agent**（1 个主 Agent + 8 个子 Agent），通过一条命令部署到 OpenClaw 实例。原始场景是协作产出顶会论文。

### 1.1 Agent 清单

| # | Agent ID | 角色 | 核心职责 |
|---|----------|------|----------|
| 0 | main | 系统仲裁者 | 审核全流程、跨 Agent 仲裁、最终决策 |
| 1 | planner | 统筹规划师 | 任务分解、进度追踪、跨 Agent 协调 |
| 2 | ideator | 创意研究员 | Idea 生成、新颖性评估、Contribution 精炼 |
| 3 | critic | 品鉴师 | SHARP 品味评估、反模式检测、品味否决权 |
| 4 | surveyor | 文献调研员 | 文献检索、Research Gap 识别 |
| 5 | coder | 代码工程师 | 算法实现、实验执行 |
| 6 | writer | 论文写作专家 | 论文撰写、LaTeX 排版 |
| 7 | reviewer | 内部审稿人 | 模拟顶会审稿、弱点诊断、一票否决权 |
| 8 | scout | 学术情报员 | 每日论文速递、趋势监控 |

### 1.2 两种部署模式

- **Channel Mode**：Agent 绑定到 Feishu/WhatsApp/Telegram/Discord 群组，通过 @mention 触发
- **Local Workflow Mode**：无需 Channel，Agent 之间通过 `agentToAgent` 工具直接通信

---

## 2. 核心机制深度分析

### 2.1 对抗式协作（Adversarial Collaboration）

系统的核心设计理念是 **productive tension（建设性张力）**，通过两对对抗轴实现质量跃升：

**轴 1：Ideator vs Critic（创意 vs 品味）**
- Ideator 负责"生成"，Critic 负责"淬炼"
- Critic 持有 **taste veto（品味否决权）**，优先级高于所有其他 Agent
- Critic 的 SHARP 评分框架（Sharpness/Horizon/Asymmetry/Resistance/Parsimony，每项 1-5 分）
  - Exquisite (23-25)：罕见好品味
  - Refined (18-22)：通过，值得投入
  - Raw (13-17)：需打磨，返回 Ideator
  - Bland (<13)：另起炉灶
- **硬性门槛**：SHARP >= 18 才能进入下一阶段，最多 3 轮迭代

**轴 2：Writer vs Reviewer（写作 vs 审稿）**
- Writer 产出论文，Reviewer 模拟顶会审稿
- Reviewer 持有 **quality veto（质量否决权）**
- 6 维度评分：Soundness/Novelty/Significance/Clarity/Reproducibility/Experiments

**关键设计原则**：
- Critic 的品味否决 > Reviewer 的技术否决 > 其他 Agent 的建议
- 超过 3 轮无共识 -> 上报 Main Agent 仲裁
- Critic 的苏格拉底式追问："如果只能用一句话解释你的方法为什么 work，那句话是什么？"

### 2.2 agentToAgent 通信机制

在 Local Workflow Mode 下，`openclaw.json` 配置了精确的通信权限矩阵：

```json
{
  "tools": {
    "agentToAgent": {
      "enabled": true,
      "allow": [
        { "from": "*", "to": "planner" },
        { "from": "planner", "to": "*" },
        { "from": "ideator", "to": "critic" },
        { "from": "critic", "to": "ideator" },
        { "from": "writer", "to": "reviewer" },
        { "from": "reviewer", "to": "writer" }
      ]
    }
  }
}
```

**通信拓扑**：
- Planner 是中枢 hub，可以与所有 Agent 双向通信
- 所有 Agent 都可以向 Planner 汇报
- Ideator <-> Critic 形成闭环对抗
- Writer <-> Reviewer 形成闭环对抗
- 其他 Agent（surveyor、coder、scout）只能通过 Planner 间接通信

这种设计确保了：
1. 信息流的可控性——避免 Agent 之间自由通信导致混乱
2. 对抗对的隔离性——让创意与批评在闭环中充分碰撞
3. 统筹者的全局视野——Planner 始终掌握全局状态

### 2.3 BOOTSTRAP.md 自合并机制

部署时，setup.sh 不直接写入 Agent 的 SOUL.md/USER.md，而是部署带 `_` 前缀的源文件：
- `_soul_source.md` — Agent 专属身份
- `_user_source.md` — Agent 专属用户上下文
- `_agent_source.md` — Agent 配置（模型已替换）
- `BOOTSTRAP.md` — 首次启动指令

Agent 首次启动时读取 BOOTSTRAP.md，自行将源文件合并到 SOUL.md 和 USER.md 中，然后清理临时文件。

**设计意图**：让 Agent 自己理解并整合自己的身份，而非机械拼接。这比 bash 脚本 cat 拼接更智能——Agent 可以根据上下文决定如何融合已有内容和新内容。

### 2.4 Group Routing 与 Session Isolation

**Group Routing**：
- 每个 Agent 通过 bindings 绑定到特定 channel + group
- 支持同一 group 内多个 Agent（通过 @mention 区分）
- 支持不同 Agent 绑定到不同 group（如 coder 绑定开发群，scout 绑定新闻群）
- `mentionPatterns` 支持多种匹配模式（@planner, planner, @Planner）

**Session Isolation**：
- Session Key 格式：`agent:<agentId>:<channel>:group:<groupId>`
- 每个 Agent 在每个 group 中有独立的 session
- 例如 `agent:planner:feishu:group:oc_xxx` 和 `agent:coder:feishu:group:oc_xxx` 是完全隔离的
- Telegram forum topics 还支持 `:topic:<threadId>` 进一步隔离
- 未被 @mention 的消息仍然存储为上下文，Agent 可以"被动跟随"对话

### 2.5 Tool Access Control

三层控制模型：

**层 1：Group 级别工具限制**
```json
{
  "groups": {
    "-1001234567890": {
      "tools": {
        "deny": ["exec", "write"]
      }
    }
  }
}
```

**层 2：Sender 级别覆盖**
```json
{
  "toolsBySender": {
    "id:123456789": { "alsoAllow": ["exec"] }
  }
}
```

**层 3：Agent 自身的 tools 配置**
- 每个 Agent 的 agent.md 声明自己的工具列表
- Planner 拥有 sessions_spawn（可以创建新 session）
- Ideator/Critic 没有 exec 权限，只有 read/write/edit
- 所有子 Agent 都有 sessions_send（可以发消息给其他 Agent）

这种分层控制实现了：
1. 生产环境安全——限制高风险工具
2. 信任分级——受信用户获得额外权限
3. Agent 能力边界——各 Agent 只拥有其角色所需的工具

---

## 3. 工作流设计

### 3.1 Paper Pipeline（9 阶段 + 4 个品鉴节点）

```
Phase 0: 项目初始化 (Planner)
Phase 1: 文献调研 (Surveyor, 1-2 周)
Phase 2: Idea 生成 (Ideator, 1 周)
Phase 2.5: Idea 品鉴 (Critic) ← SHARP >= 18 硬关卡
Phase 3: 方法设计 (Ideator + Coder)
Phase 4: 代码实现 (Coder, 2-4 周)
Phase 5: 实验执行 (Coder, 2-3 周)
Phase 6: 论文撰写 (Writer) ← Critic 检查记忆点
Phase 7: 内部审稿 (Reviewer + Critic) ← 双重审核
Phase 8: 提交准备 (Planner + Main Agent 最终审核)
```

4 个品鉴节点（Taste Gates）：
1. Idea 确认：SHARP >= 18
2. 方法设计：Parsimony >= 4
3. 论文初稿：至少 1 个明确记忆点
4. 提交前终审：Critic 确认"值得投"

### 3.2 Brainstorm 工作流

6 步快速流程：上下文准备 -> 自由发散（5-10 个粗略 Idea）-> 新颖性验证（Surveyor）-> ACE 评估 -> 深入讨论 Top 2 -> Critic 品鉴。注意 Critic 品鉴仍然是硬关卡。

### 3.3 异常处理机制

- Critic 和 Ideator 持续僵持（>3 轮）-> Main Agent 紧急介入
- Reviewer 一票否决后无改进方案 -> Main Agent 裁决方向
- DDL 风险（偏离 >20%）-> 触发计划调整
- 撞车预警（Scout 发现竞争论文）-> 紧急方向决策

---

## 4. 对心情可可「关系智能」场景的适用性分析

### 4.1 可借鉴的设计模式

**模式 A：对抗式多视角——适用于「看见模式」**

心情可可的「看见模式」需要从多个视角识别用户的重复行为模式。对抗式设计非常适合这个场景：

| 学术场景 | 心情可可映射 |
|----------|-------------|
| Ideator 生成 Idea | **模式发现者**：从对话历史中识别潜在的重复模式 |
| Critic 品鉴 Idea | **模式验证者**：验证这个模式是否真实存在、是否过度解读 |
| SHARP 评分门槛 | **模式置信度门槛**：只有足够确信的模式才呈现给用户 |

具体映射方案：
- **模式发现者（类 Ideator）**：积极寻找模式，倾向于"看到"模式（高召回）
- **模式验证者（类 Critic）**：苛刻验证，防止过度解读和虚假模式（高精确度）
- 两者对抗可以避免两种极端：一是模式识别不足（用户觉得 AI 不懂自己），二是过度解读（用户觉得 AI 在贴标签）

**模式 B：品味门槛——适用于安全边界**

Critic 的 SHARP 硬性门槛机制可以映射为安全边界检查：
- 不诊断：相当于 Critic 的"反模式检测"——检测到诊断倾向就否决
- 不替用户做决定：相当于 Parsimony 评估——方法是否过度干预
- 不对不在场的人做动机判断：可以设置为一个独立的安全检测维度

**模式 C：agentToAgent 通信拓扑——适用于多 Agent 架构**

openclaw-agents 的通信权限矩阵设计非常值得借鉴：
- 不是所有 Agent 都能自由通信，而是有明确的拓扑
- 对抗对形成闭环，其他 Agent 通过 Hub 间接通信
- 这避免了 Agent 数量增多后的通信爆炸问题

### 4.2 不适用的部分

**差异 1：目标函数不同**
- 学术场景：追求"卓越"（从 Accept 到 Oral），Critic 越严苛越好
- 情绪陪伴场景：追求"温暖与准确的平衡"，过于严苛的 Critic 可能导致 AI 过度保守、不敢表达共情

**差异 2：对抗的可见性**
- 学术场景：对抗过程可以对用户可见（用户是研究者，理解多视角讨论的价值）
- 情绪陪伴场景：对抗过程必须对用户不可见——用户不应该看到"一个 Agent 说你有焦虑倾向，另一个 Agent 说证据不足"

**差异 3：迭代轮次**
- 学术场景：Ideator 和 Critic 可以进行 3 轮甚至更多轮迭代
- 情绪陪伴场景：响应时间要求更高，对抗应该在 1-2 轮内收敛

**差异 4：9 Agent 太多**
- 心情可可 Skill 上限 15 个，9 个 Agent 的开销太大
- 情绪陪伴不需要 surveyor（文献调研）、coder（代码实现）、writer（论文写作）等角色
- 应该精简为 3-4 个角色

### 4.3 推荐的心情可可适配方案

基于调研结论，建议心情可可的「看见模式」场景采用精简版对抗式设计：

```
用户输入
  |
  v
[coco-main] ── 主陪伴 Agent（对用户可见）
  |
  v（内部调用，对用户不可见）
[pattern-finder] ←→ [pattern-critic]  （对抗对）
  |
  v
[safety-guard] ── 安全边界检查（硬否决权）
  |
  v
coco-main 综合输出 → 用户
```

- **coco-main**：面向用户的唯一 Agent，负责温暖共情的对话
- **pattern-finder**：从对话历史中积极识别行为/情绪模式
- **pattern-critic**：验证模式的真实性，防止过度解读、贴标签、虚假因果
- **safety-guard**：安全边界硬性检查（不诊断、不替用户做决定、不对不在场的人做动机判断）

通信拓扑（借鉴 agentToAgent 矩阵）：
```
coco-main -> pattern-finder  (请求模式识别)
pattern-finder <-> pattern-critic  (对抗闭环)
pattern-finder -> safety-guard  (安全检查)
safety-guard -> coco-main  (返回安全验证后的模式)
```

### 4.4 可直接复用的技术机制

| 机制 | openclaw-agents 中的实现 | 心情可可中的用法 |
|------|------------------------|----------------|
| agentToAgent 通信矩阵 | `tools.agentToAgent.allow` | 控制内部 Agent 的通信拓扑 |
| Session Isolation | `agent:<id>:<channel>:group:<groupId>` | 每个用户 session 隔离 |
| Tool Access Control | `tools.deny` + `toolsBySender.alsoAllow` | 安全 Agent 限制工具权限 |
| 品味门槛机制 | SHARP >= 18 硬关卡 | 模式置信度门槛 + 安全分数门槛 |
| BOOTSTRAP.md 自合并 | Agent 首次启动自行合并身份 | Agent 初始化时自行加载上下文 |
| 异常上报 | 3 轮僵持 -> Main Agent 仲裁 | 对抗超时 -> 保守回退（不提出不确定的模式） |

---

## 5. 结论

### 5.1 核心发现

1. **对抗式协作是经过验证的多 Agent 质量提升模式**。openclaw-agents 通过 Ideator-Critic 和 Writer-Reviewer 两对对抗轴，配合硬性品味门槛，系统性地将产出质量从"能接受"提升到"卓越"。

2. **agentToAgent 通信权限矩阵是关键设计**。不是让所有 Agent 自由通信，而是明确规定谁能和谁对话。这在 Agent 数量增长时保持了系统的可控性。

3. **BOOTSTRAP.md 自合并是优雅的初始化方案**。让 Agent 自己理解并整合身份，比脚本机械拼接更智能。

4. **Tool Access Control 的三层模型（Group/Sender/Agent）提供了精细的安全控制**。

### 5.2 对心情可可的建议

- **借鉴对抗式设计**用于「看见模式」和「安全边界」场景，但需精简为 3-4 个内部 Agent
- **对抗过程必须对用户不可见**——用户只与 coco-main 交互
- **品味门槛机制**映射为模式置信度 + 安全分数的硬性门槛
- **agentToAgent 通信矩阵**直接复用，控制内部 Agent 的通信拓扑
- **不要照搬 9 Agent 架构**——情绪陪伴场景不需要 surveyor/coder/writer/scout 等角色

### 5.3 后续行动项

- [ ] 验证 OpenClaw 的 agentToAgent 在心情可可当前配置下是否可用
- [ ] 设计 pattern-finder 和 pattern-critic 的 soul.md（借鉴 Ideator/Critic 的对抗关系定义）
- [ ] 定义模式置信度评分框架（类似 SHARP，但适配情绪陪伴场景）
- [ ] 评估对抗式设计对响应延迟的影响（情绪陪伴对延迟更敏感）
