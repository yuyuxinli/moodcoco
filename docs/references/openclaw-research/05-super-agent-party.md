# Super Agent Party 调研报告

> 项目地址: https://github.com/heshengtao/super-agent-party
> 版本: v0.4.0 | 许可: AGPL-3.0
> 调研日期: 2026-04-05

---

## 1. 项目概述

Super Agent Party（超级智能体派对）是一个 **AI 桌面伴侣应用**，核心定位是「拥有无限可能的 AI 桌面伴侣」。它将 3D 虚拟形象（VRM 桌宠）、多模态对话、任务自动化、即时通讯机器人、直播机器人等能力整合在一个 Electron 桌面应用中。

**技术栈**: Electron (前端壳) + FastAPI (Python 后端) + Vue.js (前端框架) + Three.js/@pixiv/three-vrm (3D 渲染)

**硬件要求极低**: 2 核 2G 即可运行，所有模型调用均为云端 API，不依赖本地 GPU。

---

## 2. 多层架构详解

### 2.1 桌宠层 (VRM Desktop Pet)

**核心技术**:
- `@pixiv/three-vrm` + `@pixiv/three-vrm-animation` 加载和驱动 VRM 1.0 模型
- Three.js 渲染引擎，支持 WebGLRenderer、OrbitControls、TransformControls
- `@sparkjsdev/spark` SplatMesh 支持 3D Gaussian Splatting 场景
- VMC 协议（Virtual Motion Capture）通过 OSC/UDP 接收外部动捕数据

**功能清单**:
- 自定义 VRM 模型上传（内置 Alice.vrm、Bob.vrm 两个默认角色）
- 自定义动作（animations 目录）和 3D 场景
- 表情驱动（BlendShape）通过 `/VMC/Ext/Blend/Val` OSC 消息
- 骨骼驱动通过 `/VMC/Ext/Bone/Pos` OSC 消息
- 鼠标悬停自动隐藏模型（带渐变动画）
- 360 度全景渲染模式（CubeCamera + 全景 Shader）
- OBS 采集模式（`?mode=render` 参数）
- WebXR 支持（`renderer.xr.enabled = true`）

**架构亮点**: 桌宠层完全在 Electron 渲染进程中运行，通过 IPC 与主进程通信。VMC 数据通过 UDP 接收后由主进程转发给渲染进程。

### 2.2 任务层 (Task Center)

**核心组件**:
- `TaskCenter` (`py/task_center.py`): 任务管理器，支持创建、跟踪、取消任务
- `SubAgentExecutor` (`py/sub_agent.py`): 子智能体执行器，每个子任务独立对话上下文
- `BehaviorEngine` (`py/behavior_engine.py`): 行为引擎，支持定时、周期、无输入触发

**任务系统设计**:
- 任务持久化为 JSON 文件（`.agent/tasks/{task_id}.json`）
- 子任务通过调用自身的 `/v1/chat/completions` API 递归执行（model='super-model'）
- 最多 30 次迭代循环，每次迭代更新进度百分比
- 智能完成检测：工具调用 `finish_task` 或隐式对话分析

**行为引擎**:
- 三种触发器: `time`（定时）、`noInput`（用户无输入超时）、`cycle`（周期循环）
- 三种动作: `prompt`（发送提示词）、`random`（随机事件）、`topic`（随机话题）
- 跨平台支持: chat、feishu、dingtalk、all

### 2.3 通信层 (IM & Live)

**即时通讯机器人**（一键部署）:
| 平台 | 管理器文件 | 核心库 |
|------|-----------|--------|
| QQ | `py/qq_bot_manager.py` | QQ 官方 Bot SDK |
| 飞书 | `py/feishu_bot_manager.py` | 飞书开放平台 API |
| 钉钉 | `py/dingtalk_bot_manager.py` | 钉钉开放平台 API |
| Telegram | `py/telegram_bot_manager.py` + `py/telegram_client.py` | python-telegram-bot |
| Discord | `py/discord_bot_manager.py` | discord.py |
| Slack | `py/slack_bot_manager.py` | Slack SDK |

**直播机器人** (`py/live_router.py`):
- Bilibili: 通过 blivedm 库接收弹幕（Web 模式 + 开放平台模式）
- YouTube: 通过 `py/ytdm.py` YouTube Data API 接收评论
- Twitch: 通过 `py/twitch_service.py` Twitch IRC

**通信架构**: 每个平台有独立的 BotManager，管理连接生命周期。弹幕/消息统一通过 WebSocket `/ws/live/danmu` 推送给前端。所有机器人共享同一个 BehaviorEngine 实例。

### 2.4 API 层

**OpenAI 兼容 API**:
- `POST /v1/chat/completions` — 核心对话接口，支持流式/非流式
- `GET /v1/models` — 模型列表
- `GET /v1/agents` — 智能体列表
- `POST /simple_chat` — 简化对话接口

**MCP 接口** (`fastapi-mcp`):
- 通过 `FastApiMCP` 自动暴露 FastAPI 路由为 MCP 工具
- 支持 stdio、SSE、WebSocket、Streamable HTTP 四种传输协议
- MCP 客户端 (`py/mcp_clients.py`) 支持连接外部 MCP 服务

**任务 API**:
- `GET /v1/tasks/list` — 列出所有任务
- `POST /v1/tasks/create` — 创建任务
- `POST /v1/tasks/cancel/{task_id}` — 取消任务
- `DELETE /v1/tasks/{task_id}` — 删除任务

**A2A 协议** (`py/a2a_tool.py`):
- Agent-to-Agent 调用，通过 `python_a2a` 库实现
- 支持动态注册外部 A2A 智能体

---

## 3. 重点技术分析

### 3.1 VRM 3D 头像

**实现方式**:
- 前端使用 `@pixiv/three-vrm` v2.x 加载 VRM 1.0 格式模型
- 动画系统: Three.js AnimationMixer，支持 idle、breath、blink 等基础动画
- 通过 VRMAnimationLoaderPlugin 加载 `.vrma` 格式动画文件
- 表情系统: BlendShape 驱动，支持外部 VMC 协议输入

**与对话的联动**:
- AI 回复文本 -> TTS 语音合成 -> 口型同步（推测通过音频分析驱动 BlendShape）
- 情绪表达通过表情动画切换实现

### 3.2 语音交互

**ASR（语音识别）**:
- Sherpa-ONNX: 本地离线 ASR，支持 SenseVoice 模型（中英日韩粤）
- FunASR: WebSocket 模式连接远程 ASR 服务
- Web Speech API: 浏览器原生语音识别
- OpenAI Whisper: 云端 ASR
- VAD（Voice Activity Detection）: 使用 Silero VAD 模型（`silero_vad_v5.onnx`），前端 WASM 运行

**TTS（语音合成）**:
- Edge TTS（免费，微软语音）
- OpenAI TTS
- 火山引擎 TTS（字节跳动）
- GPT-SoVITS（本地部署）
- Azure Speech
- 百度 TTS
- MiniMax TTS
- 系统 TTS
- 自定义 TTS 服务器
- **多角色音色切换**: 通过 `<角色名></角色名>` XML 标签控制不同角色使用不同音色
- **静音标签**: `<silence></silence>` 包裹不需要语音合成的内容（如图片 markdown）

**交互模式**:
- 自动模式（VAD 检测说话开始/结束）
- 热键模式（按住 Alt 说话）
- 唤醒词模式（如 "小派"）

### 3.3 MCP 集成

**作为 MCP 客户端**:
- `py/mcp_clients.py` 中的 `McpClient` 类管理与外部 MCP 服务器的连接
- 支持 4 种传输: stdio、SSE、WebSocket、Streamable HTTP
- 自动重连和健康监控（`_connection_monitor` 协程）
- MCP 工具自动注册为 LLM function calling 的可用工具

**作为 MCP 服务端**:
- 通过 `fastapi-mcp` 将 FastAPI 路由自动暴露为 MCP 工具
- 外部应用可通过 MCP 协议调用 Super Agent Party 的能力

### 3.4 多模态模型支持

**视觉能力** (`vision` 配置):
- 支持图片上传和理解
- 桌面视觉（Desktop Vision）: 截取屏幕区域让 AI 分析
- 唤醒词触发视觉（"看"、"see"、"look"、"桌面"）

**图像生成** (`text2imgSettings`):
- Pollinations AI（免费，Flux 模型）
- OpenAI DALL-E
- ComfyUI 对接 (`py/comfyui_tool.py`)

**Computer Use** (`py/computer_use_tool.py`):
- 基于 pyautogui 的桌面自动化
- 千分比坐标系统，兼容不同分辨率
- 鼠标移动、点击、键盘输入、截屏

### 3.5 异步工具调用

**工具系统架构**:
- `dispatch_tool()` 函数统一分发所有工具调用
- 支持 `asyncTools` 模式: 工具可后台异步执行，不阻塞对话
- 工具类型包括: agent_tool_call、a2a_tool_call、custom_llm_tool、mcp 工具、内置工具等
- 项目级工具权限: `.party/config.json` 中的 `allowed_tools` 白名单

**异步工具特点**:
- 工具执行通过 `execute_async_tool()` 在后台运行
- 结果通过任务系统跟踪进度
- 前端 UI 自动显示进度和结果

---

## 4. 产品形式与用户交互设计

### 4.1 核心产品形式

**桌面伴侣 = 3D 形象 + 对话 + 工具 + 自动行为**

这是一个「全能 AI 助手」的产品定位，不是纯情感陪伴。核心交互循环:
1. 用户看到桌面上的 3D 虚拟形象（桌宠）
2. 通过文字/语音与 AI 对话
3. AI 可以使用工具完成任务（搜索、控制电脑、生成图片等）
4. AI 可以主动发起对话（行为引擎: 定时问候、无输入关怀）

### 4.2 值得学习的交互设计

**1. 好感度/羁绊系统 (`affection_system.py`)**
- AI 在回复中嵌入隐藏标签 `<user=小包 love=12 familiarity=15>`
- 后端自动提取并持久化到 JSON
- 好感度影响 AI 的对话风格和行为
- **启发**: 用结构化标签从 AI 输出中提取关系数据，而非依赖额外 API 调用

**2. 多角色群聊 + 角色卡**
- 支持 SillyTavern 格式角色卡
- 多角色同时参与对话，各自有独立人设
- 长期记忆系统（mem0 集成）
- **启发**: 在情绪陪伴场景中，可以引入"内在对话"或"多视角"机制

**3. 行为引擎 — 主动关怀**
- 无输入超时触发: 用户长时间不说话，AI 主动发消息
- 定时触发: 每天固定时间问候
- 随机话题: 从话题库获取随机话题发起对话
- **启发**: 对于情绪陪伴应用，这是极其重要的功能。被动等待用户开口 vs 主动关怀。

**4. 扩展系统**
- 支持安装第三方扩展（galgame、塔罗牌、AI 编辑器等）
- 扩展可在侧边栏或独立窗口打开
- 每个扩展可注入自己的 system prompt
- **启发**: 将不同的情绪工具（呼吸练习、情绪日记、认知重构）做成独立模块

**5. 记忆系统**
- `.agent/MEMORY.md` 工作区记忆（用户用 `#` 快捷命令保存）
- mem0 长期记忆集成
- 知识库 RAG（FAISS + BM25 混合检索）
- **启发**: 分层记忆 — 即时上下文 / 用户手动标记 / 自动长期记忆

### 4.3 产品弱点

1. **功能过于庞杂**: 桌宠 + 办公助手 + IM 机器人 + 直播机器人 + 代码编辑，定位不聚焦
2. **情感深度不足**: 好感度系统是简单的数值累加，缺乏真正的关系建模
3. **配置复杂**: settings_template.json 有数百个配置项，普通用户门槛高
4. **安全边界模糊**: computer_use 能力 + 文件读取 + 浏览器控制，权限管理较粗
5. **缺乏心理学理论支撑**: 行为引擎是工程化的触发器，不是基于心理学原理的干预

---

## 5. 对心情可可的借鉴价值

### 5.1 可直接借鉴的设计

| 设计 | SAP 实现 | 心情可可应用方式 | 优先级 |
|------|---------|-----------------|--------|
| **主动关怀引擎** | BehaviorEngine 定时/无输入触发 | 微信小程序：服务号模板消息定时推送、检测用户活跃度后主动关怀 | 高 |
| **好感度/羁绊系统** | AI 输出中嵌入结构化标签提取关系数据 | 改造为「关系亲密度」指标，用于个性化回复风格调整 | 高 |
| **分层记忆** | MEMORY.md + mem0 + 知识库 RAG | 情绪日记自动摘要 -> 短期记忆 -> 长期模式识别 | 高 |
| **多音色 TTS** | XML 标签切换角色音色 | 小程序场景不适用完整 TTS，但可用于语音消息生成 | 低 |
| **扩展系统思路** | 可插拔的功能模块 | 将呼吸练习、情绪轮盘、认知重构等做成独立 skill 模块 | 中 |

### 5.2 不适用微信小程序场景的设计

| 设计 | 不适用原因 |
|------|-----------|
| VRM 3D 头像 | 小程序 WebGL 性能有限，且 VRM 库体积大；但可考虑 2D 表情动画替代 |
| 桌面自动化 (Computer Use) | 小程序无桌面控制权 |
| MCP 客户端/服务端 | 小程序是封闭环境，无法直接运行 MCP 协议；但后端可对接 |
| 本地 ASR/VAD | 小程序有自带的录音+识别 API，无需自建 |
| Electron 桌宠 | 小程序无法做桌宠，但可做虚拟形象页面 |

### 5.3 心情可可可参考的具体策略

**1. 主动关怀时机设计**（改造 BehaviorEngine 思路）
- 早安/晚安问候（定时触发）
- 用户 3 天未使用时，发送服务号模板消息（无输入触发）
- 基于历史情绪模式，在用户通常情绪低落的时段提前触发（智能触发）

**2. 关系数据提取**（改造好感度系统思路）
- 让 AI 在每次回复中输出隐藏的关系标签（如情绪状态、亲密度变化、关键话题标记）
- 后端提取并持久化，用于纵向追踪用户情绪变化
- 这比单独调用一次 API 做情绪分析更高效

**3. 随机话题引擎**（改造 random_topic 思路）
- SAP 有一个话题 API 服务，按 mood/category/depth 获取话题
- 心情可可可以建立「情绪引导话题库」，根据当前情绪状态匹配合适的引导话题
- 例如：用户焦虑时 -> 获取「正念」类话题；用户低落时 -> 获取「自我关怀」类话题

---

## 6. 总结

Super Agent Party 是一个**功能极其全面但定位发散**的 AI 桌面伴侣。它的技术架构（FastAPI 后端 + Electron 前端 + 多协议通信）非常成熟，代码量庞大（server.py 超过 6000 行）。

对心情可可而言，最有价值的三个借鉴点是:

1. **BehaviorEngine 主动关怀机制** — 不要只被动等用户来，要主动在合适的时机触达用户
2. **结构化标签提取关系数据** — 在 AI 输出中嵌入隐藏标签，实现零额外 API 调用的关系追踪
3. **分层记忆架构** — 即时上下文 / 用户标记 / 自动长期记忆的三层结构

SAP 的弱点（缺乏心理学深度、好感度系统过于简单）恰好是心情可可的差异化机会。心情可可应该在「关系智能」这个维度上做到远超 SAP 的水平。
