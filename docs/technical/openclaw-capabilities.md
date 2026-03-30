# OpenClaw 平台能力参考

*编译自 docs.openclaw.ai，供产品设计使用*

## 文档索引

完整文档：
- 在线：https://docs.openclaw.ai
- 本地完整副本：`/Users/jianghongwei/Documents/GitHub/openclaw/docs/`（建议 clone [OpenClaw 仓库](https://github.com/nicroclaw/openclaw) 以便离线查阅）

---

## 1. 记忆系统

### 存储结构
- **`MEMORY.md`** — 长期记忆，会话启动时加载
- **`memory/YYYY-MM-DD.md`** — 每日笔记，今天和昨天的自动加载
- **自定义文件** — 如 `people/*.md`、`diary/*.md`、`USER.md` 等，通过 memory_search 索引

### 记忆工具
| 工具 | 功能 |
|------|------|
| `memory_search` | 语义搜索，即使措辞不同也能找到相关笔记 |
| `memory_get` | 读取特定文件或行范围 |

### 混合搜索
配置 embedding provider 后，搜索同时使用：
- **向量相似度**（语义匹配）
- **BM25 关键词**（精确匹配）

支持的 embedding provider：OpenAI、Gemini、Voyage、Mistral、Ollama、本地 GGUF

### 高级特性
- **时间衰减**：自动降权旧笔记（30 天半衰期），MEMORY.md 不受影响
- **MMR 去重**：消除冗余结果
- **多模态索引**：Gemini 支持图片和音频索引
- **会话记忆索引**（实验性）：索引对话记录供回忆
- **自动记忆刷新**：Compaction 前自动提醒 agent 保存重要上下文

---

## 2. Canvas（macOS 桌面端）

### 概述
Canvas 是 macOS 应用内嵌的 agent 控制面板（WKWebView），支持 HTML/CSS/JS 交互界面。

### 文件存储
```
~/Library/Application Support/OpenClaw/canvas/<session>/
```
通过自定义 URL scheme 访问：`openclaw-canvas://<session>/<path>`

### Agent API
```bash
openclaw nodes canvas present --node <id>          # 显示面板
openclaw nodes canvas navigate --node <id> --url "/" # 导航
openclaw nodes canvas eval --node <id> --js "..."    # 执行 JS
openclaw nodes canvas snapshot --node <id>           # 截图
```

### A2UI 集成
Gateway 托管 A2UI：`http://<gateway-host>:18789/__openclaw__/a2ui/`
支持消息类型：`beginRendering`、`surfaceUpdate`、`dataModelUpdate`、`deleteSurface`

### Deep Linking
Canvas 可通过 URL scheme 触发 agent：
```js
window.location.href = "openclaw://agent?message=Review%20this%20design";
```

### 限制
- 仅 macOS 桌面端支持
- 一次只显示一个面板
- 需要 Settings → "Allow Canvas" 开启

---

## 3. Poll（投票/选择）

### 支持渠道
Telegram、WhatsApp、Discord、Microsoft Teams

### Agent 工具调用
```json
{
  "tool": "message",
  "action": "poll",
  "pollQuestion": "你想怎么告别？",
  "pollOption": ["烧掉日记", "烧掉信念", "时间胶囊", "未寄出的信"],
  "pollMulti": false
}
```

### 平台限制
| 平台 | 选项数 | 特殊功能 |
|------|--------|----------|
| Telegram | 2-10 | 匿名/公开、秒级时长 |
| WhatsApp | 2-12 | maxSelections |
| Discord | 2-10 | 小时级时长（1-768h） |
| Teams | Adaptive Cards | 投票记录存 JSON |

---

## 4. Exec（脚本执行）

### 核心能力
在 workspace 内执行 shell 命令，支持前台/后台执行。

### 关键参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `command` | 必填 | Shell 命令 |
| `workdir` | cwd | 工作目录 |
| `yieldMs` | 10000 | 自动转后台阈值 |
| `timeout` | 1800s | 超时时间 |
| `host` | auto | 执行位置（sandbox/gateway/node） |

### 典型用法
```json
// 前台执行 Python 脚本
{ "tool": "exec", "command": "python3 scripts/pattern_engine.py" }

// 后台执行
{ "tool": "exec", "command": "python3 generate_chart.py", "background": true }
```

### 安全
- 拒绝 PATH 和 loader 覆盖（防二进制劫持）
- allowlist 模式控制可执行命令
- 沙箱隔离可选

---

## 5. 图片处理

### 发送图片
```bash
openclaw message send --media <path-or-url> --message <caption>
```
自动处理：调整大小 + JPEG 压缩，最大 2048px 边长

### 接收图片
- `{{MediaUrl}}` — 图片 URL
- `{{MediaPath}}` — 本地路径
- 支持自动分析（配置 `tools.media.image` 模型）

### 限制
- 出站最大 50MB
- 音频/视频最大 16MB
- 文档最大 100MB

---

## 6. Streaming（流式输出）

### 两层架构
1. **Block streaming**：完成的块作为消息发送（非 token 级）
2. **Preview streaming**：生成中更新预览消息（Telegram/Discord/Slack）

### 关键配置
```json
{
  "blockStreamingDefault": "on",
  "blockStreamingBreak": "text_end",
  "blockStreamingChunk": { "minChars": 50, "maxChars": 500, "breakPreference": "sentence" },
  "humanDelay": "natural"  // 800-2500ms 随机延迟，模拟人类打字
}
```

### 分块算法
断点优先级：段落 → 换行 → 句子 → 空格 → 硬断
代码块安全：不在代码块内断开

---

## 7. Heartbeat（主动关怀）

### 核心功能
定期触发 agent turn，让 agent 主动关心用户。

### 配置
```json
{
  "heartbeat": {
    "every": "30m",
    "target": "last",
    "lightContext": true,
    "isolatedSession": true,
    "activeHours": { "start": "08:00", "end": "23:00", "tz": "Asia/Shanghai" }
  }
}
```

### 响应协议
- 无事发生 → 返回 `HEARTBEAT_OK`（不发送给用户）
- 有事 → 发送消息给用户
- 通过 `HEARTBEAT.md` 定义检查清单

### 成本优化
`isolatedSession: true` + `lightContext: true` 可将 token 从 ~100K 降到 ~2-5K

---

## 8. Session（会话管理）

### 路由规则
| 来源 | 会话策略 |
|------|----------|
| DM | 共享/按发送者/按渠道+发送者 隔离 |
| 群聊 | 按群隔离 |
| Cron | 每次新会话 |
| Webhook | 按 hook 隔离 |

### DM 隔离模式
- `main`：所有 DM 共享（默认，不安全）
- `per-peer`：按发送者隔离
- `per-channel-peer`：按渠道+发送者隔离（推荐）
- 支持 `identityLinks` 跨渠道关联同一用户

### 生命周期
- 每日重置（默认凌晨 4 点）
- 空闲重置（可配置分钟数）
- 手动重置（`/new` 或 `/reset`）

---

## 9. Compaction（压缩）

### 机制
接近上下文窗口限制时自动触发：
1. 旧对话摘要化为紧凑条目
2. 摘要保存在会话记录中
3. 近期消息保持完整
4. **完整历史仍在磁盘上**

### Compaction 前自动保存
触发前自动提醒 agent 保存重要笔记到记忆文件，防止上下文丢失。

### 手动触发
`/compact` + 可选引导："Focus on the API design decisions"

---

## 10. Workspace（工作空间）

### 标准文件结构
| 文件 | 用途 |
|------|------|
| `AGENTS.md` | 操作指令和记忆指南 |
| `SOUL.md` | Agent 人格、语气、边界 |
| `USER.md` | 用户身份 |
| `IDENTITY.md` | Agent 名称、风格 |
| `HEARTBEAT.md` | Heartbeat 检查清单 |
| `BOOTSTRAP.md` | 首次运行仪式 |
| `memory/YYYY-MM-DD.md` | 每日记忆 |
| `MEMORY.md` | 长期记忆 |
| `skills/` | 技能目录 |
| `canvas/` | Canvas UI 文件 |

---

## 11. Skills（技能系统）

### 格式
每个 skill 是一个目录 + `SKILL.md`（含 YAML frontmatter）：
```yaml
---
name: skill-name
description: Brief description
---
```

### 加载优先级（高→低）
1. Workspace skills: `<workspace>/skills`
2. Project agent skills: `<workspace>/.agents/skills`
3. Personal agent skills: `~/.agents/skills`
4. Managed/local skills: `~/.openclaw/skills`
5. Bundled skills
6. Extra skill folders

### ClawHub
公共 skill 注册中心：https://clawhub.com
```bash
openclaw skills search <keyword>
openclaw skills install <skill-name>
```

---

## 12. Cron（定时任务）

### 与 Heartbeat 的区别
- **Heartbeat**：在主会话中运行，适合检查+可能回复
- **Cron**：每次新会话，适合独立任务

---

## 13. 其他能力

### 语音
- TTS 朗读回复（多 provider 支持）
- 语音笔记转文字
- Talk Mode（语音对话）

### 浏览器自动化
- 内置 browser 工具
- 网页抓取 + 交互

### 多 Agent 路由
- 每个 agent 独立 workspace
- 基于规则的消息路由
- 隔离的会话

### Model Failover
- 配置 failover chain
- 自动切换到备用模型

---

## 对产品设计的关键启示

### 可用于"超越纯 LLM"的能力
| 能力 | 纯 LLM 做不到 | 产品价值 |
|------|---------------|----------|
| **memory_search** | 跨会话语义搜索 | "你上次说..." 的个性化体验 |
| **people/*.md** | 持久化的人物档案 | 关于人的记忆贯穿所有对话 |
| **Heartbeat** | 主动触发对话 | 不用等用户来找，可可会主动关心 |
| **Canvas** | 对话内嵌入 HTML/JS UI | 可视化情绪图表、关系时间线 |
| **Poll** | 结构化选择 | 用户点选代替输入 |
| **exec** | 运行 Python 脚本 | 生成图片、计算模式匹配 |
| **Streaming** | 逐句输出 + 人类节奏 | 像真人打字的体感 |
| **Compaction** | 超长对话不丢关键信息 | 聊了 1 小时也不会忘前面说的 |
| **Cron** | 定时任务 | 每日日记提醒、周回顾 |
| **图片分析** | 看懂用户发的截图 | "你把聊天记录发我看看" |
| **identityLinks** | 跨渠道用户合并 | 微信+飞书同一用户 |

---

## 技术点使用全景

*合并自 tech-capabilities.md（已使用/遗漏的技术点清单）*

### 已使用 ✅

| # | 技术点 | 用在哪 |
|---|--------|--------|
| 1 | Agent workspace (.md + skills) | 核心产品架构 |
| 2 | Model selection + thinking high | minimax-m2.7 |
| 3 | Model failover | minimax → doubao → auto |
| 4 | Session 管理 (dmScope) | 多用户隔离 |
| 5 | Heartbeat | 主动关怀（HEARTBEAT.md） |
| 6 | Cron jobs | 每日情绪日记 |
| 7 | Memory (search/get) | 跨 session 记忆 |
| 8 | Compaction | 保留情绪模式 |
| 9 | Groups (mention-gating) | @可可触发 |
| 10 | Skills (6个) | calm-down, sigh, emotion-journal, relationship-coach, relationship-skills, diary |
| 11 | Exec tool | sigh 呼吸引导脚本 |
| 12 | ClawHub | 安装业内 skill |
| 13 | USER.md / people/ / diary/ | 用户档案+人物档案+日记 |

### 遗漏的高价值技术点（按优先级排序）

#### P0 — 配置即生效，立竿见影

| # | 技术点 | 能做什么 | 配置方式 | 对用户的价值 |
|---|--------|---------|---------|------------|
| 14 | **Timezone 时间感知** | 可可知道"凌晨3点发的"和"5天没聊了" | `envelopeTimestamp: "on"` + `envelopeElapsed: "on"` + `userTimezone: "Asia/Shanghai"` | 凌晨消息→更轻柔；久没聊→自然回溯 |
| 15 | **Streaming 逐句输出** | 回复一句一句出现，有停顿，像真人在想 | `blockStreamingDefault: "on"` + `humanDelay: "natural"` + `breakPreference: "sentence"` | 深夜安慰时逐句出现 = "我在认真想" |
| 16 | **Session Pruning** | 自动清理 sigh/journal 的 tool 输出，释放上下文 | `mode: "cache-ttl"` + `ttl: "5m"` | 对话不会被旧的呼吸练习文本撑满 |

#### P1 — 需要一定开发，但价值极高

| # | 技术点 | 能做什么 | 配置复杂度 | 对用户的价值 |
|---|--------|---------|-----------|------------|
| 17 | **Presence 在线状态** | 知道用户多久没互动、当前是否在线 | 中（结合 Heartbeat） | 避免用户离线时发消息；"3天没见了"触发关怀 |
| 18 | **Poll 轻交互投票** | 发送"现在心情怎么样？"选项卡 | 低（一个 action） | 低能量用户点一下就行，比打字门槛低 |
| 19 | **Talk Mode 语音对话** | 实时语音：用户说话→可可用温暖声音回应 | 中（需 ElevenLabs API） | 深夜哭着打不了字→语音倾诉；呼吸引导用声音带节奏 |
| 20 | **Plugin 自定义工具** | 注册 emotion_detect、mood_journal_write 等工具 | 中（TypeScript） | before_tool_call hook 拦截危险回复；自定义情绪分析 |
| 21 | **Lossless Claw 插件** | DAG 式对话摘要，长期记忆不丢又省 token | 低（一行安装） | 聊了100轮还记得第1轮说的话 |
| 22 | **语音消息转文字** | 微信语音自动转文字后处理 | 低（内置，配 provider） | 用户发语音可可也能理解 |
| 23 | **图片接收+分析** | 用户发聊天截图，可可能"看图说话" | 低（内置） | 聊天截图解读场景直接可用 |

#### P2 — 中期规划

| # | 技术点 | 能做什么 | 对用户的价值 |
|---|--------|---------|------------|
| 24 | **Control UI** | Web 管理面板（支持中文） | 运维监控、远程调试 |
| 25 | **Remote Access** | SSH/Tailscale 远程访问 Gateway | 生产部署基础 |
| 26 | **Canvas UI** | macOS 上渲染情绪可视化仪表盘 | 情绪趋势图、呼吸动画（仅桌面） |
| 27 | **OpenProse 工作流** | .prose 格式编排多 agent 协作 | 复杂流程：分析历史→识别模式→生成日记 |
| 28 | **identityLinks** | 跨渠道用户身份合并 | 微信+飞书同一用户记忆打通 |
| 29 | **Session idle reset** | 空闲超时重置 session | 长时间不聊后干净重新开始 |
| 30 | **Webhook 外部触发** | HTTP 端点接收小程序回调 | 小程序→触发可可回复 |
| 31 | **社区 Channel 插件** | QQbot / WeCom / DingTalk | 扩展到更多平台 |
| 32 | **Opik 监控** | 追踪 token、成本、异常 | 上线后质量监控 |
| 33 | **Agent Send CLI** | 命令行发送关怀消息 | 与 cron 联动：定时向指定用户发消息 |
| 34 | **Slash 命令** | /think /model /tts /btw | 运行时动态调节能力 |

#### P3 — 长期探索

| # | 技术点 | 说明 |
|---|--------|------|
| 35 | Camera 拍照 | 情绪图片日记（隐私敏感） |
| 36 | Location 位置 | 场景化建议（隐私敏感） |
| 37 | Voice Wake 语音唤醒 | "可可"唤醒词（仅 macOS/iOS） |
| 38 | Gmail Pub/Sub | 企业版(EAP)场景 |
| 39 | Elevated Mode | 沙箱提权调试 |
| 40 | RPC Adapters | 自定义小众 IM 接入 |
| 41 | OAuth 多 profile | 多模型认证路由优化 |
| 42 | before_prompt_build hook | 每轮注入动态上下文（当天情绪摘要） |
| 43 | message_sending hook | 发送前安全拦截 |

### 优先级总览（按用户感知排序）

#### P0 — 用户直接感知，配置即生效
- Streaming 逐句输出（"可可在认真想再回我"）
- Timezone 时间感知（"可可知道我是凌晨在难受"）
- 语音转文字（"发语音也行"）

#### P1 — 用户直接感知，需要一定开发
- 图片分析（"发截图可可能看"）
- Poll 轻交互（"点一下就行不用打字"）
- Presence + Heartbeat（"可可主动来找我了"）
- Lossless Claw（"聊很久了还记得"）

#### P2 — 用户间接感知，影响对话质量
- Session Pruning（长对话后期回复不跑偏）
- Lossless Claw（跨月记忆不丢失）
- Model Failover（深夜不掉线）
- before_prompt hook（可可知道"你今天记了3条日记"）
- Compaction 定制（压缩后还记得行为模式）

#### P3 — 用户感知不到，基础设施/长期探索
- Control UI / Remote Access / Plugins / RPC / OAuth
- OpenProse / identityLinks / Canvas UI
- Camera / Location / Voice Wake / Gmail
- Elevated Mode / message_sending hook

### 总计

- 已使用：13 个
- 遗漏：30 个
- 其中 P0（直接感知+立即可用）：3 个
- 其中 P1（直接感知+需开发）：4 个
- 其中 P2（间接感知+影响对话）：5 个
- 其中 P3（不感知/长期）：18 个
