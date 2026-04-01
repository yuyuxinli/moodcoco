# MoodCoco — AI 情感陪伴

心情可可是基于 OpenClaw 的 AI 情感陪伴 agent。核心能力是帮用户「看见自己」：看见情绪（从模糊到精确命名）、看见原因（连接深层需求）、看见模式（识别重复行为）、看见方法（用户自己找到方向）。技术上是一套 `.md` 文件 + skills，不写代码，改文件即迭代。

## 项目状态

**正在进行**：与心理咨询全栈项目（`psychologists`）合并。MoodCoco 作为"大脑"注入心理咨询项目的"身体"（微信小程序 + FastAPI + PostgreSQL）。

相关文档：
- [设计方案](docs/superpowers/specs/2026-03-31-project-merge-design.md) — 合并架构、Tool 统一、存储抽象
- [迁移手册](docs/superpowers/specs/2026-03-31-migration-playbook.md) — 19 步迁移计划，供 `/evolve` 执行

## 如何拆解一个大需求

本项目的合并方案就是用这套流程拆出来的，推荐给所有复杂项目：

### 第一步：Brainstorming（用 Superpowers skill）

```
/superpowers:brainstorming
```

逐个澄清问题，收敛到设计方案。这一步产出：

1. **产品文档**（可选）— 为什么做、做给谁、核心指标
   - 本项目：[产品上下文](docs/product/product-context.md)
2. **技术架构**（可选）— 系统怎么拼、数据怎么流、边界在哪
   - 本项目：[合并设计方案](docs/superpowers/specs/2026-03-31-project-merge-design.md)
3. **实现步骤**（必须）— 先做什么、后做什么、每步怎么验证
   - 本项目：[迁移手册](docs/superpowers/specs/2026-03-31-migration-playbook.md)

> 产品文档和技术架构不一定每次都要写，视项目复杂度而定。但**实现步骤必须有**，否则 AI 不知道从哪开始、到哪结束。

### 第二步：Evolve（自主执行）

```
/evolve
# 或持续运行
/loop 1m /evolve
```

把实现步骤交给 `/evolve`，它会：
1. 分析现有代码
2. 自己写测试
3. 执行迁移/开发
4. 评估结果
5. 不达标就迭代，直到通过

### 为什么这样拆

| 常见做法 | 问题 | 本项目做法 |
|---------|------|-----------|
| 直接让 AI 写代码 | AI 不知道全局，改一个破一个 | 先 brainstorming 对齐架构，再动手 |
| 写一份巨长的 PRD | AI 无法执行，人也不想读 | 拆成可执行的步骤，每步有评估标准 |
| 人工逐步指挥 AI | 慢，且人成为瓶颈 | evolve 自主执行，人只定方向 |

## 目录结构

```
moodcoco/
├── ai-companion/           ← coco agent 的 workspace（核心，PM 维护）
│   ├── SOUL.md             ← 人格定义：可可是谁、怎么说话
│   ├── AGENTS.md           ← 行为规则：四步法、安全协议
│   ├── IDENTITY.md         ← 基础身份（名字、emoji）
│   ├── HEARTBEAT.md        ← 主动关怀规则（4 条 Cron 规则）
│   ├── USER.md             ← 当前用户档案（每次对话后更新）
│   ├── TOOLS.md            ← 工具声明
│   ├── skills/             ← 10+ 技能模块
│   ├── scripts/            ← exec 脚本（pattern_engine 等）
│   ├── diary/              ← 用户日记存储
│   ├── people/             ← 人物档案
│   └── memory/             ← 跨 session 记忆
├── docs/
│   ├── product/            ← 产品文档
│   │   └── product-context.md ← 产品上下文（必读）
│   ├── technical/          ← 技术文档
│   └── superpowers/specs/  ← 设计方案 + 迁移手册
├── eval-reference/         ← 评估参考记录
├── industry-skills/        ← 调研过的业内 skill
└── CLAUDE.md               ← 项目约定（开发者必读）
```

## 快速开始

### 1. 安装 OpenClaw

```bash
# macOS
brew install openclaw

# 或用 npm
npm install -g openclaw
```

### 2. Clone 仓库

```bash
git clone git@github.com:moodcoco/moodcoco.git
cd moodcoco
```

### 3. 配置模型

需要 OpenRouter API Key，在 [openrouter.ai](https://openrouter.ai) 注册后：

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

### 4. 运行对话

```bash
# 本地测试
openclaw agent --agent coco --message "你好" --local --thinking high

# 交互式对话
openclaw agent --agent coco --local --thinking high
```

## 评估和迭代：/evolve

| 维度 | 门槛 | 说明 |
|------|------|------|
| 看见情绪 | 9.0 | 从"好烦"到精准情绪词 |
| 看见原因 | 9.0 | 引导用户自己发现深层需求 |
| 看见模式 | 9.0 | 指出重复行为模式 |
| 看见方法 | 9.0 | 用户自己找到解决方向 |
| 安全边界 | 9.0 | 不诊断、不替用户决定 |

```bash
# 运行一次评估
/evolve

# 持续运行
/loop 1m /evolve
```

## 核心文件

### SOUL.md — 可可是谁

- 不说"应该"、不假装懂、不替用户做决定
- 区分保护层情绪（愤怒/冷漠）和脆弱层情绪（害怕被丢下）
- 不对不在场的人做动机判断

### AGENTS.md — 行为规则

- **四步法**：看见情绪 → 看见原因 → 看见模式 → 看见方法
- **安全红线**：自伤/自杀意念时停止一切，提供危机热线
- **记忆机制**：每次对话后更新 USER.md

### skills/ — 10+ 技能

| Skill | 触发场景 | 心理学框架 |
|-------|---------|-----------|
| diary | 情绪日记 + 人物识别 | IMA |
| breathing-ground | 恐慌/情绪淹没 | Stanford cyclic sigh + 5-4-3-2-1 |
| check-in | 每日签到 | Daylio |
| decision-cooling | 大决定前冷却 24h | EFT + DBT STOP |
| relationship-guide | 关系困扰 | IFS + EFT + NVC |
| relationship-skills | 沟通表达 | I-statements |
| pattern-mirror | 跨关系模式呈现 | 自研 |
| farewell | 关系闭合仪式 | 叙事疗法 + ACT |
| growth-story | 成长叙事检测 | INT/IMA |
| weekly-reflection | 周回顾 | Ash insights |

## 工程经验

### 使用 Evolve 的注意事项

- **任务粒度要细**：每个 Feature 拆得越小，迭代越快。10 个小任务比 5 个大任务效果好——更容易定位失败原因、更快收到反馈、单轮 B/C Agent 工作量更可控。
- 建议每个 Feature 对应 1 个具体的用户操作序列（如"发一条消息 + 验证回复格式"），而不是"完整旅程"。

## 联系方式

| 姓名 | 角色 | 联系方式 |
|------|------|---------|
| 蒋宏伟 | 创始人 | 微信：请联系团队获取 |
| 张鸽 | 联合创始人 / 设计 | 微信：请联系团队获取 |
| 蒋丽园 | 心理学顾问（北大临床心理） | 微信：请联系团队获取 |

有问题直接在项目群里问，或提 Issue。
