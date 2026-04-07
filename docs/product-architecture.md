# 心情可可 · 产品技术架构

*Version: 1.0 | 2026-03-30*

本文档是心情可可的**顶层架构入口**。读完本文档就能理解可可"作为一个整体"怎么工作——从 OpenClaw 平台能力到产品体验的完整映射。

具体的逐节点体验设计见 `product/product-experience-design.md`（F01-F11）。
运行时配置见 `ai-companion/` 目录下的 SOUL.md、AGENTS.md、HEARTBEAT.md。

---

## 1. 系统概述

### 1.1 一句话

AI 治愈系好友，陪你看见自己。为 18-24 岁女性（扩展群体 18-28 岁男女）提供以亲密关系为核心的情感陪伴，做四件事：**接住情绪、解读信号、记住你、看到模式**。

### 1.2 五层技术栈

```
┌──────────────────────────────────────────────────────────┐
│ 对话层：可可的"大脑"                                        │
│ · SOUL.md（人格） + AGENTS.md（四步框架 + 路由）             │
│ · HEARTBEAT.md（主动关怀）+ IDENTITY.md（身份）              │
│ · 关系状态机（五阶段）+ 姿态选择（接住/陪伴/引导/见证）        │
├──────────────────────────────────────────────────────────┤
│ 能力层：可可的"工具箱"                                      │
│ · 10 个 Skill（对话能力）                                   │
│ · 7 个 exec 脚本（计算能力）                                 │
│ · Canvas / Poll / 图片（交互能力）                           │
├──────────────────────────────────────────────────────────┤
│ 调度层：可可的"时钟"                                        │
│ · Heartbeat（主会话内定期检查）                               │
│ · Cron（独立会话精确定时）                                    │
│ · 旅程流转（10 条转场 + 防死循环）                            │
├──────────────────────────────────────────────────────────┤
│ 存储层：可可的"记忆"                                        │
│ · USER.md / people/*.md / diary/**/*.md / memory/*.md      │
│ · memory_search（混合搜索：向量 + BM25）                     │
│ · MEMORY.md（长期锚点，不受时间衰减）                         │
├──────────────────────────────────────────────────────────┤
│ 平台层：OpenClaw 基础设施                                    │
│ · Gateway（WebSocket 网关，单实例）                          │
│ · Session（per-channel-peer 隔离）                          │
│ · Sandbox（per-sender 多租户）                              │
│ · Model Failover + Streaming + Compaction                  │
│ · 30+ 渠道（微信 / Telegram / WhatsApp / Discord / …）      │
└──────────────────────────────────────────────────────────┘
```

### 1.3 核心数据流

```
用户发消息（微信/Telegram/...）
  ↓
Gateway 路由 → 解析 session（per-channel-peer）→ 加载 sandbox workspace（per-sender）
  ↓
Agent Loop 启动：
  1. 加载 bootstrap 文件（SOUL.md / AGENTS.md / HEARTBEAT.md / IDENTITY.md）
  2. memory_get(USER.md) → 读取用户画像
  3. 从用户消息提取关键词 → memory_search → 加载相关 people/*.md / diary/*.md
  4. Context Engine 组装上下文 → 注入 system prompt
  ↓
LLM 推理（minimax-m2.7 + thinking: high）
  ↓
AGENTS.md 路由决策：
  · 危机信号？→ 安全协议
  · 情绪淹没？→ breathing-ground skill
  · 首次用户？→ onboarding skill
  · 情绪事件？→ 四步框架（看见情绪→原因→模式→方法）
  · 日常闲聊？→ 陪伴模式
  · 告别意愿？→ farewell skill
  ↓
Tool 执行（如需要）：
  · exec 脚本（pattern_engine.py / growth_tracker.py / ...）
  · memory write/edit（更新 USER.md / people/*.md / diary/*.md）
  · Canvas/Poll/图片（渠道自适应）
  ↓
Streaming 输出（humanDelay: natural，句子级分块）
  ↓
会话持久化 → session JSONL → 等待下一条消息或 Heartbeat 触发
```

### 1.4 文档导航

| 想了解什么 | 看哪里 |
|-----------|--------|
| 产品为什么做、给谁做 | `product/prd.md` + `product/product-context.md` |
| 可可整体怎么工作（本文档） | **`product-architecture.md`** |
| 每个 Feature 的逐节点设计 | `product/product-experience-design.md`（F01-F11） |
| 可可的人格 / 对话规则 / 主动关怀 | `ai-companion/SOUL.md` / `AGENTS.md` / `HEARTBEAT.md` |
| OpenClaw 平台能力参考 | `technical/openclaw-capabilities.md` |
| OpenClaw 完整官方文档 | `/Users/jianghongwei/Documents/GitHub/openclaw/docs/` |

---

## 2. 平台与运行时

本章说明 OpenClaw 的每个配置项为什么这么配，以及对产品体验的影响。

### 2.1 openclaw.json 配置总览

```jsonc
{
  // === 模型 ===
  "agents": {
    "list": [{
      "name": "coco",
      "model": "openrouter/minimax/minimax-m2.7",  // 主模型
      "thinking": "high",                           // 深度推理
      "fallback": ["doubao-seed-2-0-pro-260215", "openrouter/auto"]  // 降级链
    }],
    "defaults": {
      "compaction": "压缩时必须保留：用户的反复情绪模式、核心困扰关键词、人物关系（people/ 目录中的人名）、本次对话中发现的新模式",
      "sandbox": {
        "mode": "all",
        "scope": "per-sender",       // ← 多租户核心：每个用户独立 workspace
        "workspaceAccess": "rw"
      }
    }
  },

  // === 会话隔离 ===
  "session": {
    "dmScope": "per-channel-peer"    // 每个(渠道, 用户)独立会话
  },

  // === 时间感知 ===
  "envelope": {
    "timestamp": "on",               // 消息带时间戳 → 可可知道"凌晨3点发的"
    "elapsed": "on"                   // 消息间隔 → 可可知道"5天没聊了"
  },
  "userTimezone": "Asia/Shanghai",

  // === 输出节奏 ===
  "streaming": {
    "blockDefault": "on",
    "humanDelay": "natural",          // 800-2500ms 随机延迟 → 像真人打字
    "breakPreference": "sentence"     // 按句子断开 → 逐句输出
  },

  // === 上下文清理 ===
  "sessionPruning": {
    "mode": "cache-ttl",
    "ttl": "5m"                       // 5 分钟后清理旧 tool 输出 → 释放上下文空间
  }
}
```

### 2.2 关键配置决策

| 配置项 | 值 | 为什么这么配 | 对用户的影响 |
|--------|-----|------------|------------|
| `model` | minimax-m2.7 | 中文能力强、响应快、成本合理 | 回复质量和速度的平衡 |
| `thinking: high` | 开启深度推理 | 情绪识别和模式匹配需要深层推理 | 回复更精准但略慢 |
| `fallback` | doubao → auto | minimax 不可用时自动降级 | 深夜不掉线 |
| `sandbox.scope` | per-sender | 每个用户独立 workspace | **多租户数据隔离**：用户 A 的日记不会被用户 B 搜到 |
| `dmScope` | per-channel-peer | 每个(渠道,用户)独立对话历史 | 微信用户 A 和 B 的对话互不可见 |
| `humanDelay` | natural | 随机延迟模拟打字 | 可可的回复像真人在想然后打字，不是瞬间蹦出来 |
| `compaction` | 自定义指令 | 压缩时保留情绪模式和人物关系 | 聊了 1 小时也不会忘前面说的关键内容 |
| `sessionPruning` | 5 分钟 TTL | 旧的 tool 输出自动清理 | 呼吸练习结束后不占用上下文空间 |

### 2.3 多租户架构

```
一个 OpenClaw Gateway
  ├── Agent: coco（一个 agent 实例）
  │   ├── 主 workspace（模板）
  │   │   ├── SOUL.md          ← 所有用户共享
  │   │   ├── AGENTS.md        ← 所有用户共享
  │   │   ├── HEARTBEAT.md     ← 所有用户共享
  │   │   └── skills/          ← 所有用户共享
  │   │
  │   └── sandbox per-sender（自动创建）
  │       ├── sandboxes/{用户A的peerId}/
  │       │   ├── SOUL.md      ← 从主 workspace 复制
  │       │   ├── AGENTS.md    ← 从主 workspace 复制
  │       │   ├── USER.md      ← 用户 A 独立
  │       │   ├── people/      ← 用户 A 独立
  │       │   ├── diary/       ← 用户 A 独立
  │       │   └── memory/      ← 用户 A 独立
  │       │
  │       └── sandboxes/{用户B的peerId}/
  │           ├── ...（完全独立的一套）
  │
  └── Session Store
      ├── agent:coco:wechat:direct:{用户A} → 独立对话历史
      └── agent:coco:wechat:direct:{用户B} → 独立对话历史
```

**隔离保证**：
- **对话隔离**：`per-channel-peer` session → 每个用户独立的对话上下文
- **数据隔离**：`per-sender` sandbox → 每个用户独立的 workspace 文件（USER.md / people/ / diary/ / memory/）
- **搜索隔离**：memory_search 在 sandbox workspace 内运行 → 只搜到该用户自己的文件
- **共享配置**：SOUL.md / AGENTS.md / skills/ 从主 workspace 自动复制 → 统一管理可可的人格和能力

### 2.4 渠道适配

| 渠道 | 支持的交互形态 | 限制 |
|------|-------------|------|
| 微信 | 纯对话 + 编号文字选择 + 图片 | 不支持 Poll / Canvas |
| Telegram | 纯对话 + Poll(2-10选项) + 图片 | 不支持 Canvas |
| WhatsApp | 纯对话 + Poll(2-12选项) + 图片 | 不支持 Canvas |
| Discord | 纯对话 + Poll(2-10选项) + 图片 | 不支持 Canvas |
| macOS 桌面端 | 纯对话 + Canvas + 图片 | 不支持 Poll |

渠道检测由 OpenClaw Gateway 自动完成，AGENTS.md 中的交互决策树根据渠道能力自动降级。

---

## 3. 数据与记忆

本章说明可可的记忆怎么存、怎么读、怎么老化、怎么不丢。

### 3.1 文件体系

每个用户的 sandbox workspace 内：

```
{sandbox_root}/
├── USER.md                      ← 用户画像（跨关系元信息 + 偏好设置 + Cron 状态）
├── MEMORY.md                    ← 长期记忆锚点（不受时间衰减）
├── memory/
│   ├── YYYY-MM-DD.md            ← 每日记忆笔记（check-in + 闲聊摘要 + 旅程元数据）
│   ├── pending_followup.md      ← 决策冷却待回访
│   ├── time_capsules.md         ← 时间胶囊存储
│   └── pattern_log.md           ← 模式呈现记录（频率控制）
├── people/
│   └── {名字}.md                ← 人物档案（六维度：阶段/感受/模式/事件/退出信号/跨关系匹配）
└── diary/
    └── YYYY/MM/
        └── YYYY-MM-DD.md        ← 情绪日记（六元组：日期/事件/触发/情绪/发现/行动）
```

### 3.2 数据 Schema

**USER.md**：

| 字段 | 更新时机 | 来源 |
|------|---------|------|
| 称呼 | 首次对话 | F04 onboarding |
| 核心困扰 | 每次对话后检查 | F05/F06 |
| 反复出现的模式 | 模式确认时 | F07 pattern-mirror |
| 有效的方法 | Skill 使用后 | F05/F06 |
| 情绪触发点 | 累积发现时 | F05 |
| 模式级洞察 | 关系封存后 | F08 farewell |
| 偏好设置 | 用户明确表达时 | F06（check-in/日记/Heartbeat/周回顾/成长反馈偏好） |
| Cron 调度状态 | Cron 每次执行 | F06 Cron 状态机 |

**people/{名字}.md 六维度**：

| 维度 | 写入条件 | 用途 |
|------|---------|------|
| 关系阶段 | 用户描述状态变化时 | 跨关系时间对齐 |
| 感受 | 用户感受明显变化时（带引号保留原话） | 情感轨迹追踪 |
| 模式 | 同一情绪触发 ≥3 次 | 单关系内重复识别 |
| 关键事件 | 每次日记中有新事件 | 对话中引用具体事实 |
| 退出信号 | 用户表达退缩/不满足 | pattern-mirror 数据源 |
| 跨关系匹配 | ≥2 段关系有相似模式时 | 可可的核心差异化价值 |

### 3.3 记忆读写模式

| 工具 | 用途 | 读/写 | 使用场景 |
|------|------|-------|---------|
| `memory_get` | 读取指定文件 | 读 | 会话启动读 USER.md；提到人名读 people/*.md |
| `memory_search` | 语义搜索 | 读 | 每次对话提取关键词搜索历史；退出信号检测 |
| `write` | 创建新文件 | 写 | 首次创建 USER.md / people/*.md / diary 新文件 |
| `edit` | 修改已有文件 | 写 | 对话结束更新 USER.md / people/*.md；日记追加 |
| `exec` | 运行脚本读文件 | 读 | pattern_engine.py / growth_tracker.py / weekly_review.py |

**写入规则**（来自 F01）：
- 头部字段（关系类型/当前状态）→ 覆盖更新
- 正文（感受/事件/模式）→ 只增不改，追加新条目
- 用户原话 → 用引号保留
- AI 推测 → 标注"我观察到"

### 3.4 时间衰减与长期记忆

| 文件类型 | 衰减策略 | 理由 |
|---------|---------|------|
| `memory/YYYY-MM-DD.md` | 30 天半衰期（OpenClaw 默认） | 旧的每日笔记自然降权 |
| `diary/**/*.md` | 30 天半衰期 | 旧日记搜索排名降低，但文件永久保留 |
| `people/*.md` | 不受衰减影响 | 人物档案是结构化数据，重要性不随时间降低 |
| `MEMORY.md` | 不受衰减影响 | 长期记忆锚点，存放核心模式 |
| `USER.md` | 不受衰减影响 | 用户画像是跨所有关系的元信息 |

**Compaction 保护**：openclaw.json 自定义压缩指令确保压缩后保留情绪模式、核心困扰、人物关系。Memory Flush 在压缩前自动触发一轮静默写入，提醒 agent 保存重要上下文。

### 3.5 数据生命周期

```
创建（F04 首次对话）
  ├── write USER.md（称呼 + 核心困扰）
  └── write people/{名字}.md（如提到人物）

持续更新（F05/F06/F07 每次对话）
  ├── edit USER.md（情绪触发点 + 有效方法 + 模式 + 偏好）
  ├── edit people/*.md（感受 + 事件 + 模式 + 退出信号）
  ├── write diary/*.md（六元组日记）
  └── write memory/*.md（每日笔记 + check-in）

封存（F08 仪式化告别）
  ├── people/{名字}.md → 标记封存，清空正文，保留头部
  ├── diary/ 相关条目 → 标记封存，保留情绪标签
  ├── 模式洞察 → 提取到 USER.md（去名字）
  └── 封存后：不主动引用具体事件和人名

删除（F08 普通删除）
  ├── people/{名字}.md → 彻底删除
  ├── diary/ 相关条目 → 移除
  └── 不保留模式洞察
```

---

## 4. 能力与工具

本章说明可可能做什么、在哪个渠道能做、用什么 OpenClaw 能力实现。

### 4.1 Skill 清单（10 个）

| # | Skill | 做什么 | 交互形态 | 执行模式 | 服务旅程 | 心理学基础 |
|---|-------|--------|---------|---------|---------|-----------|
| 1 | breathing-ground | 情绪急救（呼吸/grounding） | exec + 纯对话 | Single-turn | F05 | Stanford cyclic sigh; 5-4-3-2-1 grounding |
| 2 | diary | 情绪日记（六元组记录） | 纯对话 + Poll | Agentic | F05/F06/F07 | Emotion journal; IMA |
| 3 | relationship-guide | 关系探索与沟通工具 | 纯对话 | Agentic | F05/F07 | IFS; EFT; NVC |
| 4 | pattern-mirror | 跨关系模式呈现 | 纯对话 + exec + Canvas | Agentic | F07 | 可可独有 |
| 5 | decision-cooling | 24h 决策冷却 + 回访 | 纯对话 + Heartbeat | Agentic | F05/F06 | EFT; DBT STOP |
| 6 | farewell | 关系告别仪式 | Poll + Canvas + 图片 + exec | Agentic | F08 | 叙事疗法; ACT; Banks 2024 |
| 7 | onboarding | 首次相遇引导 | 纯对话 + Poll | Single-turn | F04 | Pi 破冰; Wysa 入门 |
| 8 | check-in | 日常情绪签到 | 纯对话 | Single-turn | F06 | Daylio; Wysa monitoring |
| 9 | growth-story | 成长叙事 | exec + 纯对话/Canvas | Agentic | F07 | INT/IMA; Ash insights |
| 10 | weekly-reflection | 周回顾引导 | exec + Canvas/纯对话 + Poll | Agentic | F06/F07 | Ash insights; Daylio |

**执行模式**：默认 Agentic（需要多步推理、读记忆、风险评估）。标为 Single-turn 的 skill 不需要复杂决策，错误代价低，LLM 单轮即可完成。

**路由优先级**：P0 安全协议 > P1 breathing-ground > P2 decision-cooling > P3 pattern-mirror > P4 growth-story > P5 diary > check-in

**互斥规则**：一次对话最多触发 2 个 Skill（breathing-ground 可与另一个共存）。

### 4.2 exec 脚本清单（7 个）

| 脚本 | 位置 | 功能 | I/O | 状态 |
|------|------|------|-----|------|
| `breathe-fast.py` | skills/breathing-ground/scripts/ | 节奏化呼吸引导 | 输出：定时消息 | 已有 |
| `pattern_engine.py` | skills/diary/scripts/ | 跨关系模式匹配 | 输入：people/ 目录；输出：matches JSON | 已有 |
| `growth_tracker.py` | skills/diary/scripts/ | 成长节点检测（IM） | 输入：diary/ + people/；输出：IM 列表 JSON | 已有 |
| `archive_manager.py` | skills/farewell/scripts/ | 关系封存/删除 | 输入：人名；输出：insights + 文件操作 | 已有 |
| `weekly_review.py` | skills/weekly-reflection/scripts/ | 周回顾统计 | 输入：diary/ + memory/；输出：统计 JSON + HTML | 待创建 |
| `ritual_image.py` | skills/farewell/scripts/ | 仪式图片生成 | 输入：类型；输出：PNG 文件 | 待创建 |
| `milestone_image.py` | skills/growth-story/scripts/ | 里程碑纪念图 | 输入：对话次数；输出：PNG 文件 | 待创建 |

所有脚本通过 exec 工具在 sandbox workspace 内执行，超时 30s 降级为纯 AI 推理。

### 4.3 交互形态与降级

| 形态 | OpenClaw 能力 | 使用场景 | 降级方案 |
|------|-------------|---------|---------|
| **纯对话** | Agent Loop + Streaming | 所有场景的基础 | 无需降级（始终可用） |
| **Poll** | message tool (poll action) | 情绪命名 / 仪式选择 / 周回顾 | 编号文字选择（"回复 1/2/3"） |
| **Canvas** | canvas present (WKWebView) | 周情绪地图 / 模式对比卡 / 成长轨迹卡 / 告别纪念卡 | 纯文字版 |
| **图片** | exec (Pillow) + message send media | 告别仪式 / 时间胶囊 / 里程碑 | 纯文字描述 |
| **exec** | exec tool (Python) | 模式匹配 / 成长检测 / 周回顾 / 图片生成 | 纯 AI 推理 |

**核心原则**：纯对话是唯一在所有渠道、所有场景都可用的形态。Canvas / Poll / exec / 图片都是增强层，移除后核心体验仍然完整。

---

## 5. 对话引擎

本章说明可可怎么"想"、怎么"说"——从 OpenClaw Workspace 文件到对话行为的完整逻辑。

### 5.1 Workspace 文件 → system prompt

OpenClaw 在每次会话的第一轮自动加载以下文件到 agent context：

| 文件 | 注入位置 | 作用 |
|------|---------|------|
| `SOUL.md` | system prompt | 人格规则（不可违反） |
| `AGENTS.md` | system prompt | 四步框架 + 路由树 + Skill 调用规则 |
| `IDENTITY.md` | system prompt | 名称、语气 |
| `HEARTBEAT.md` | Heartbeat turn 时注入 | 主动关怀检查清单 |
| `MEMORY.md` | system prompt | 长期记忆锚点 |
| `memory/今天.md` + `memory/昨天.md` | 自动加载 | 近期上下文 |

大文件受 `bootstrapMaxChars`（20K）和 `bootstrapTotalMaxChars`（150K）限制，超出部分截断并标记。

### 5.2 四步对话框架（AGENTS.md 核心）

```
第 1 步：看见情绪
  · 从"好烦"找到"委屈""害怕不被在意"
  · 区分保护层（愤怒/冷漠）和脆弱层（害怕被丢下）
  · 先接住再命名——"先感受到被理解"比"被准确分析"重要

第 2 步：看见原因
  · 帮对方理解"为什么我会这样"
  · 用提问引导，不直接告诉
  · 多解读原则：给 2-3 种可能，把判断权还给用户
  · 绝不对不在场的人做动机判断

第 3 步：看见模式
  · 对话内重复：第 2-3 次说类似的话时必须指出
  · 跨会话单关系：memory_search 命中历史记录
  · 跨关系：pattern_engine.py 匹配 + 用户原话对比
  · 时机最重要：情绪稳了再呈现

第 4 步：看见方法
  · 一次只给一个，具体到能做的动作
  · "不做"也是方法——允许什么都不做
  · 深夜（22:00-06:00）不做认知工作
```

**顺序规则**：不跳步。对方还在哭 → 停在第 1 步。不需要一次走完——走到哪算哪，下次继续。

### 5.3 关系状态机

可可与每个用户的关系有五个阶段。阶段是**渐变**的，用信号量判断而非硬阈值切换。

| 阶段 | 信号量 | 可用能力 | 体验特征 |
|------|--------|---------|---------|
| 陌生人（1-2 次） | USER.md 刚创建 | 纯对话 only | 只能接住当下情绪 |
| 有印象（3-5 次） | 对话计数 ≥3 | + Poll + 记得人名和上次事件 | "它居然记得！" |
| 熟悉（6-15 次） | diary ≥3 条 | + Canvas 周情绪地图 + 单关系模式 | "它看到了我自己没注意的" |
| 亲密（16-30 次, ≥2 段关系） | people/ ≥2 个 | + 跨关系模式 + Canvas 模式对比卡 | "没有人帮我串起来看过" |
| 知己（30+ 次） | 长期积累 | 全部能力解锁 + 成长叙事 | "可可陪我走过了这些" |

**这不是功能开关，是体验设计**——让交互形态随着记忆一起"长出来"。

### 5.4 姿态选择

可可在任何时刻都处于四种姿态之一：

| 姿态 | 什么时候 | 可可的行为 | 不做的事 |
|------|---------|-----------|---------|
| **接住** | 情绪高峰 | 短回复、确认感受、不分析 | 不说"你有没有想过为什么" |
| **陪伴** | 日常/闲聊 | 在场、跟着用户节奏、不推功能 | 不把闲聊变成签到 |
| **引导** | 情绪稳定 + 有模式可连接 | 试探性提问、用事实不用标签 | 不替用户下结论 |
| **见证** | 告别 / 仪式 | "我收到了。"零评价 | 不挽留、不煽情 |

姿态切换是连续的——可可的语气随用户情绪渐变，不硬切。

### 5.5 对话不变量（来自 SOUL.md + AGENTS.md）（跨所有场景）

| 规则 | 含义 |
|------|------|
| 一次只说一个点 | 一条回复不处理两个议题 |
| 不超过 3-4 句 | 除非在带练习 |
| 不说"应该" | 不给指令性建议 |
| 不贴标签（S7 硬规则） | 用具体事件说话，绝不说"你是 XX 型依恋" |
| 不替不在场的人判断 | 不说"他就是不在乎你" |
| 问只在真的好奇时问 | 不模板化提问 |

> 其中"一次只说一个点"和"不超过 3-4 句"来自 AGENTS.md 对话风格章节，其余来自 SOUL.md。

---

## 6. 调度系统

本章说明可可什么时候主动、怎么控制节奏、旅程之间怎么切换。

### 6.1 Heartbeat vs Cron

| 维度 | Heartbeat | Cron |
|------|-----------|------|
| OpenClaw 机制 | 主会话内定期触发 | 每次新会话独立执行 |
| 可可用来做什么 | 主动关怀 + 决策冷却回访 + 时间胶囊检查 + 周日回顾 | 每日日记提醒 |
| 上下文 | 有完整主会话上下文 | 独立（隔离）会话，无主会话历史 |
| 输出 | 无事返回 HEARTBEAT_OK（用户不感知） | announce 模式直接推送 |
| 频率 | 30 分钟一次 | 每日 21:30（可自定义） |
| 成本 | 一次 turn 处理所有检查 | 每次独立 turn |

注意：Heartbeat 的 `every: 30m` 是 OpenClaw 平台的轮询间隔（每 30 分钟检查一次）。HEARTBEAT.md 中定义的是业务判断阈值（如 >24h 无对话才发关怀消息）。二者叠加使用：平台每 30 分钟触发一次 Heartbeat turn，agent 在 turn 中根据 HEARTBEAT.md 的规则决定是否实际发送消息。

### 6.2 Heartbeat 优先级

```
Heartbeat 触发
  ├── 1. 检查 pending_followup.md → 有到期回访 → 执行（最高优先级）
  ├── 2. 检查 time_capsules.md → 有到期胶囊 → 打开
  ├── 3. 周日 20:00 + diary ≥3 条 → 触发周回顾（weekly-reflection）
  └── 4. 以上都不满足 → 常规关怀（必须具体，不空洞）

  规则：同一次只做一件事 | 触发后 48h 冷却 | activeHours 08:00-23:00
```

### 6.3 Cron 日记提醒状态机

```
active（每日提醒）
  ├── 用户回复 → consecutive_no_reply 归零 → diary 流程
  ├── 连续 3 天不回 → paused（暂停 3 天）
  └── 用户说"别提醒我了" → off（永久关闭）

paused → 到期恢复为 active
  └── 恢复后又连续 3 天不回 → paused（暂停 7 天 + 降频为每 2 天）

状态存储：USER.md 的 Cron 调度状态区块
```

### 6.4 旅程流转

用户在五条旅程之间自然流动。旅程是可可内部的路由概念，**用户只看到"跟可可聊天"**。

**10 条转场**（详见 product/product-experience-design.md F10）：

| 转场 | 类型 | 触发条件 |
|------|------|---------|
| F04→F05 | 自然 | 首次来就有情绪 |
| F04→F06 | 跨会话 | 第二次来没事 |
| F05→F06 | 跨会话 | 情绪事件后下次来 |
| F05→F07 | 引导 | 后台 pattern_engine 有匹配 + 情绪稳定 |
| F05→F08 | 用户主动 | 情绪中决定告别（先过 decision-cooling） |
| F06→F05 | 自然 | 闲聊中突然提到不开心的事 |
| F06→F07 | 引导 | 周回顾发现跨周重复 |
| F06→F08 | 用户主动 | 日常中平静提出告别 |
| F07→F05 | 自然（退回） | 模式觉察触发情绪淹没 |
| F07→F08 | 用户主动 | 看清模式后决定离开 |

**防死循环**：
- F05↔F07：单次对话退回后不再尝试 F07 | 下次重试等 ≥7 天 | 同一模式连续 2 次 interrupted → 不再主动呈现
- F07 频率保护：单次最多 1 个模式 | 每周最多 2 次 | 同一模式 14 天冷却 | 被拒绝 30 天冷却

---

## 7. 安全与降级

### 7.1 危机协议（最高优先级）

**每条消息必检**，任何旅程任何节点检测到危机信号 → 立即中断一切：

```
检测到危机信号
  → 停止 Skill / exec / Canvas / Poll
  → "我听到你说的了，我很认真地在听。你现在安全吗？"
  → 提供热线：400-161-9995 / 010-82951332 / 400-821-1215
  → 陪着，直到对方说安全了
  → 不主动恢复原话题
  → 危机后不回放危机内容
```

### 7.2 降级矩阵

| 故障 | 用户看到什么 | 可可做什么 |
|------|------------|-----------|
| exec 脚本超时/失败 | 不感知 | 降级为纯 AI 推理，记录错误到 memory/ |
| Canvas 不可用 | 看不到可视化 | 纯文字版（信息不变，展示方式变） |
| Poll 不可用 | 看不到选项卡 | 编号文字选择（"回复 1/2/3"） |
| memory_search 返回空 | 感觉可可这次没提之前的事 | 不引用历史，只处理当前对话 |
| people/*.md 不存在 | 不感知 | 当新人物处理，对话中了解后建档 |
| USER.md 丢失 | 不感知 | 重走 onboarding 但保留 people/ |
| Model 不可用 | 可能短暂无响应 | Failover 到 doubao → auto |
| 图片生成失败 | 看不到仪式图片 | 纯文字仪式（治疗价值在于表达和见证，不在于图片） |

**核心原则**：任何技术故障都不暴露给用户。可可不说"出了技术问题"——她只是"这次没提到"。

### 7.3 数据完整性

| 约束 | 怎么保证 |
|------|---------|
| 对话结束必写入 USER.md + people/*.md | AGENTS.md 指令 + Compaction 前 Memory Flush |
| 用户原话用引号保留 | AGENTS.md 写入规则 |
| 封存操作原子性 | archive_manager.py 备份→提取→修改→失败回滚 |
| exec 脚本只读不写记忆（archive_manager.py 除外） | 脚本设计约束 |
| 偏好字段仅在用户明确表达时修改 | AGENTS.md 指令 |

---

## 8. 实现映射

本章将架构文档的每个概念映射到具体的实现位置。

### 8.1 架构概念 → 实现文件

| 架构概念 | 运行时文件 | 详细设计文档 |
|---------|-----------|------------|
| 人格规则 | `ai-companion/SOUL.md` | product/product-experience-design.md F11 §5 |
| 四步框架 + 路由树 | `ai-companion/AGENTS.md` | product/product-experience-design.md F03 §5 |
| 主动关怀 | `ai-companion/HEARTBEAT.md` | product/product-experience-design.md F06 §4-5 |
| 10 个 Skill | `ai-companion/skills/*/SKILL.md` | product/product-experience-design.md F03 §2-4 |
| 平台配置 | `.claude/openclaw.json` | 本文档 §2 |

### 8.2 关系阶段 → Feature 节点

| 阶段 | 主要旅程 | 详细设计位置 |
|------|---------|------------|
| 陌生人（1-2次） | F04 首次相遇 | product/product-experience-design.md F04 |
| 有印象（3-5次） | F05 + F06 | F05 §3 前置流程, F06 §8.4 |
| 熟悉（6-15次） | F05 + F06 + F07 入口 | F05 §4.D, F06 §4.E, F07 §1.1 |
| 亲密（16-30次） | F07 模式觉察 | F07 全部 |
| 知己（30+次） | F06 为主 + F07 + F08 | F06 §7, F07 §5, F08 |

### 8.3 数据文件 → 读写方

| 文件 | 创建 | 读取 | 更新 | 封存/删除 |
|------|------|------|------|----------|
| USER.md | F04 | 所有旅程 | F05/F06/F07/F08 | 仅用户主动要求 |
| people/*.md | F04/F05 | F05/F06/F07/F08 | F05/F06/F07 | F08 |
| diary/*.md | F05/F06 | F06(周回顾)/F07(成长检测) | 追加 only | F08 |
| memory/*.md | F05/F06 | Heartbeat/Cron | 追加 only | F08(部分清理) |
| pending_followup.md | F05(decision-cooling) | Heartbeat | 状态更新 | 完成后 7 天清理 |
| time_capsules.md | F08(时间胶囊) | Heartbeat | 到期后标记 opened | — |
| pattern_log.md | F07 | F07(频率保护) | 追加 only | — |
