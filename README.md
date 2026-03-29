# MoodCoco — AI 情感陪伴

心情可可是基于 OpenClaw 的 AI 情感陪伴 agent。核心能力是帮用户「看见自己」：看见情绪（从模糊到精确命名）、看见原因（连接深层需求）、看见模式（识别重复行为）、看见方法（用户自己找到方向）。技术上是一套 `.md` 文件 + skills，不写代码，改文件即迭代。

## 目录结构

```
moodcoco/
├── ai-companion/           ← coco agent 的 workspace（核心）
│   ├── SOUL.md             ← 人格定义：可可是谁、怎么说话
│   ├── AGENTS.md           ← 行为规则：四步法、状态感知、安全红线
│   ├── IDENTITY.md         ← 基础身份（名字、emoji）
│   ├── HEARTBEAT.md        ← 主动关怀规则（24h 未对话触发）
│   ├── USER.md             ← 当前用户档案（每次对话后更新）
│   ├── TOOLS.md            ← 工具声明
│   ├── skills/             ← 6 个技能
│   │   ├── diary/          ← 情绪日记（自动识别人物、关联档案）
│   │   ├── emotion-journal/ ← 结构化情绪记录（六元组）
│   │   ├── sigh/           ← 呼吸引导（恐慌/激动时）
│   │   ├── calm-down/      ← 感官着陆（反刍/思维打转时）
│   │   ├── relationship-coach/ ← 关系探索（IFS/EFT 框架）
│   │   └── relationship-skills/ ← 沟通工具（I-statements 等）
│   ├── diary/              ← 用户日记存储（YYYY/MM/YYYY-MM-DD.md）
│   ├── people/             ← 人物档案（日记中提到的人）
│   ├── memory/             ← 跨 session 记忆（模式观察）
│   └── docs/               ← 内部参考文档
├── eval-reference/         ← 评估参考记录（15 场景 × 4 人设）
├── industry-skills/        ← 调研过的业内 skill（参考用）
├── docs/                   ← 项目文档
│   ├── product-context.md  ← 产品上下文（必读）
│   ├── model-config.md     ← 模型配置说明
│   ├── group-setup.md      ← 微信群配置
│   ├── session-isolation.md ← 多用户隔离方案
│   ├── compaction-config.md ← 长对话压缩配置
│   └── 团队成员.md          ← 团队信息
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

安装后运行 `openclaw --version` 确认成功。

### 2. Clone 仓库

```bash
git clone git@github.com:moodcoco/moodcoco.git
cd moodcoco
```

### 3. 注册 coco agent

把 `ai-companion/` 目录注册为 coco agent 的 workspace：

```bash
openclaw agents add coco --workspace ./ai-companion
```

### 4. 配置模型

在项目根目录创建 `openclaw.json`：

```json
{
  "agents": {
    "list": [
      {
        "name": "coco",
        "model": "openrouter/minimax/minimax-m2.7",
        "thinking": "high",
        "fallback": [
          "doubao-seed-2-0-pro-260215",
          "openrouter/auto"
        ]
      }
    ],
    "defaults": {
      "compaction": "压缩时必须保留：用户的反复情绪模式、核心困扰关键词、人物关系（people/ 目录中的人名）、本次对话中发现的新模式"
    }
  },
  "session": {
    "dmScope": "per-channel-peer"
  }
}
```

需要 OpenRouter API Key。在 [openrouter.ai](https://openrouter.ai) 注册后，配置环境变量：

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

### 5. 运行第一次对话

```bash
# 本地测试（命令行对话）
openclaw agent --agent coco --message "你好" --local --thinking high

# 或启动交互式对话
openclaw agent --agent coco --local --thinking high
```

看到可可回复就说明配置成功。

## 评估和迭代：/evolve

`/evolve` 是自动评估循环，用模拟用户和可可对话，按 5 个维度打分。

### 评估维度

| 维度 | 门槛 | 说明 |
|------|------|------|
| 看见情绪 | 9.0 | 从"好烦"到精准情绪词 |
| 看见原因 | 9.0 | 引导用户自己发现深层需求 |
| 看见模式 | 9.0 | 指出重复行为模式 |
| 看见方法 | 9.0 | 用户自己找到解决方向 |
| 安全边界 | 9.0 | 不诊断、不替用户决定 |

### 使用方法

```bash
# 运行一次评估
/evolve

# 持续运行（每分钟检查一次）
/loop 1m /evolve
```

evolve 会自动：
1. 用 4 个模拟用户人设（小雨/阿瑶/玉玉/小桔）发起 15 个场景对话
2. 让 coco 真实回复
3. 按 5 个维度打分
4. 生成改进建议
5. 修改 SOUL.md / AGENTS.md / skills
6. 重新测试，直到全部达标

参考 `eval-reference/` 查看一次完整评估的记录（含对话 transcript、评分报告、迭代复盘）。

## 核心文件说明

### SOUL.md — 可可是谁

定义可可的人格和对话规则：
- 不说"应该"、不假装懂、不替用户做决定
- 区分保护层情绪（愤怒/冷漠）和脆弱层情绪（害怕被丢下/觉得自己不够好）
- 不对不在场的人做动机判断

修改 SOUL.md 直接改变可可的说话方式，改完用 `/evolve` 验证效果。

### AGENTS.md — 行为规则

定义可可做事的逻辑：
- **四步法**（严格按顺序）：看见情绪 → 看见原因 → 看见模式 → 看见方法
- **状态感知**：根据用户状态触发对应 skill（恐慌 → 呼吸引导，反刍 → 感官着陆）
- **安全红线**：自伤/自杀意念时停止一切，提供危机热线
- **记忆机制**：每次对话后更新 USER.md，下次对话前读取做模式连接

### skills/ — 6 个技能

每个 skill 是一个目录，核心是 `SKILL.md`（指令文件），可能附带 `references/`（参考资料）和 `scripts/`（脚本）。

| Skill | 触发场景 | 做什么 |
|-------|---------|--------|
| diary | "帮我记一下"、"今天发生了..." | 情绪日记 + 人物识别 + 模式追踪 |
| emotion-journal | 说不清自己怎么了 | 结构化六元组记录（事件/情绪/强度/想法/应对/触发） |
| sigh | 恐慌、情绪淹没 | 呼吸引导脚本 |
| calm-down | 脑子停不下来、反刍 | 感官着陆（5-4-3-2-1） |
| relationship-coach | 伴侣矛盾、关系困扰 | IFS/EFT 框架引导探索 |
| relationship-skills | 不知道怎么表达 | I-statements 等沟通模板 |

### diary/ 和 people/ — 用户数据

- `diary/YYYY/MM/YYYY-MM-DD.md`：用户的情绪日记，第一人称，保留原话
- `people/{名字}.md`：日记中出现的人物档案（关系、关键事件、互动模式）
- `memory/*.md`：跨 session 的模式观察，供可可下次对话时搜索

## 联系方式

| 姓名 | 角色 | 联系方式 |
|------|------|---------|
| 蒋宏伟 | 创始人 | 微信：请联系团队获取 |
| 张鸽 | 联合创始人 / 设计 | 微信：请联系团队获取 |
| 蒋丽园 | 心理学顾问（北大临床心理） | 微信：请联系团队获取 |

有问题直接在项目群里问，或提 Issue。
