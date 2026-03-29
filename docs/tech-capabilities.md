# OpenClaw 技术能力全景（心情可可视角）

## 已使用 ✅

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

## 遗漏的高价值技术点（按优先级排序）

### P0 — 配置即生效，立竿见影

| # | 技术点 | 能做什么 | 配置方式 | 对用户的价值 |
|---|--------|---------|---------|------------|
| 14 | **Timezone 时间感知** | 可可知道"凌晨3点发的"和"5天没聊了" | `envelopeTimestamp: "on"` + `envelopeElapsed: "on"` + `userTimezone: "Asia/Shanghai"` | 凌晨消息→更轻柔；久没聊→自然回溯 |
| 15 | **Streaming 逐句输出** | 回复一句一句出现，有停顿，像真人在想 | `blockStreamingDefault: "on"` + `humanDelay: "natural"` + `breakPreference: "sentence"` | 深夜安慰时逐句出现 = "我在认真想" |
| 16 | **Session Pruning** | 自动清理 sigh/journal 的 tool 输出，释放上下文 | `mode: "cache-ttl"` + `ttl: "5m"` | 对话不会被旧的呼吸练习文本撑满 |

### P1 — 需要一定开发，但价值极高

| # | 技术点 | 能做什么 | 配置复杂度 | 对用户的价值 |
|---|--------|---------|-----------|------------|
| 17 | **Presence 在线状态** | 知道用户多久没互动、当前是否在线 | 中（结合 Heartbeat） | 避免用户离线时发消息；"3天没见了"触发关怀 |
| 18 | **Poll 轻交互投票** | 发送"现在心情怎么样？"选项卡 | 低（一个 action） | 低能量用户点一下就行，比打字门槛低 |
| 19 | **Talk Mode 语音对话** | 实时语音：用户说话→可可用温暖声音回应 | 中（需 ElevenLabs API） | 深夜哭着打不了字→语音倾诉；呼吸引导用声音带节奏 |
| 20 | **Plugin 自定义工具** | 注册 emotion_detect、mood_journal_write 等工具 | 中（TypeScript） | before_tool_call hook 拦截危险回复；自定义情绪分析 |
| 21 | **Lossless Claw 插件** | DAG 式对话摘要，长期记忆不丢又省 token | 低（一行安装） | 聊了100轮还记得第1轮说的话 |
| 22 | **语音消息转文字** | 微信语音自动转文字后处理 | 低（内置，配 provider） | 用户发语音可可也能理解 |
| 23 | **图片接收+分析** | 用户发聊天截图，可可能"看图说话" | 低（内置） | 聊天截图解读场景直接可用 |

### P2 — 中期规划

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

### P3 — 长期探索

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

## 总计

- 已使用：13 个
- 遗漏：30 个
- 其中 P0（立即可用）：3 个
- 其中 P1（高价值）：7 个
