下面调研的是你链接里的 **OpenAI Realtime Conversations / GPT-Realtime-2**。它不是一个普通“文本大模型”，而是面向**实时语音对话、语音 Agent、语音工具调用**的模型与 API 组合。

## 1. 总结：它到底是什么？

**GPT-Realtime-2 是 OpenAI 当前主推的实时语音对话模型**，通过 Realtime API 使用，核心能力是“speech-to-speech”：用户说话，模型直接理解语音并生成语音回复，中间不需要你自己串联 STT→LLM→TTS 三段式链路。OpenAI 文档明确说明，Realtime API 支持通过 **WebRTC 或 WebSocket** 连接，然后调用 `gpt-realtime-2` 进行语音到语音对话。([OpenAI 开发者][1])

它适合做：

| 场景                 | 是否适合                          |
| ------------------ | ----------------------------- |
| AI 语音陪伴、心理陪伴、口语陪练  | 很适合                           |
| 客服语音机器人            | 很适合                           |
| 实时语音助手，边说边调用工具     | 很适合                           |
| 实时翻译               | 更适合用 `gpt-realtime-translate` |
| 只做语音转文字            | 更适合用 `gpt-realtime-whisper`   |
| 强流程、强审核、必须保存完整文本链路 | 不一定，可能 STT+LLM+TTS 分段式更好      |

它的关键优势是：低延迟、可打断、自然轮次管理、直接语音输入输出、可调用工具、支持长上下文。OpenAI 介绍 GPT-Realtime-2 是其“最强实时语音模型”，支持可配置 reasoning effort、更强指令遵循、更可靠工具调用，适合复杂语音 Agent 工作流。([OpenAI 开发者][2])

---

## 2. 核心能力

### 2.1 直接语音到语音，延迟更低

传统语音 Agent 通常是：

> 用户语音 → STT 转文字 → LLM 生成文字 → TTS 合成语音

Realtime API 的优势是：

> 用户语音 → Realtime 模型直接理解并生成语音

OpenAI 文档明确说，Realtime API 的强点之一是**不经过中间文本转语音或语音转文本步骤的 voice-to-voice interaction**，这可以降低语音界面延迟，并让模型利用语气、语调等语音信息。([OpenAI 开发者][1])

### 2.2 支持 WebRTC / WebSocket

官方推荐：

| 连接方式      | 适合场景                    |
| --------- | ----------------------- |
| WebRTC    | 浏览器、移动端、实时语音 App，推荐优先使用 |
| WebSocket | 服务端到服务端、你想自己处理音频流和事件    |

OpenAI 文档说，WebRTC 适合实时应用，Realtime API 支持通过 WebRTC peer connection 连接实时模型；而 WebSocket 更适合 server-to-server 应用，浏览器和移动端更推荐 WebRTC。([OpenAI 开发者][3])

### 2.3 支持 VAD、打断和轮次管理

Realtime API 默认支持语音活动检测 VAD，可以自动判断用户开始说话和停止说话。VAD 有两种模式：`server_vad` 基于静音判断，`semantic_vad` 根据语义判断用户是否说完。`semantic_vad` 更适合自然对话，因为它能减少模型过早打断用户。([OpenAI 开发者][4])

这对你的 AI 心理陪伴/语音陪伴场景很重要，因为用户经常会停顿、犹豫、补充表达。如果只是简单静音判断，很容易误以为用户说完了；`semantic_vad` 会更自然。

### 2.4 支持工具调用

Realtime 语音 Agent 可以调用工具。OpenAI 文档区分了两类：

| 工具类型            | 谁执行                 | 适合场景                               |
| --------------- | ------------------- | ---------------------------------- |
| function tool   | 你的应用执行              | 查用户资料、查日记、查课程、调用内部 API             |
| MCP / connector | Realtime API 执行远程工具 | 接入 MCP Server、Google Calendar 等连接器 |

官方说明，Realtime session 可以挂载工具，让模型在实时对话中查数据、采取行动或调用服务；function tools 由你的应用执行并返回结果，MCP tools 或内置 connectors 可由 Realtime API 自己连接远程工具。([OpenAI 开发者][5])

这和你之前做的“用户画像、记忆、日记、课程工具、流式对话”非常契合。

---

## 3. 使用方法：怎么接入？

### 方案 A：前端/移动端直接 WebRTC 连接 OpenAI

这是做实时语音 App 最推荐的方式。基本流程是：

1. 你的后端用正式 OpenAI API Key 创建一个临时 ephemeral token；
2. 前端从你的后端拿这个临时 token；
3. 前端创建 `RTCPeerConnection`；
4. 前端接入麦克风音轨；
5. 前端通过 WebRTC 连接 OpenAI Realtime；
6. 通过 data channel 发送 `session.update`、工具调用、文本消息等事件；
7. 模型直接返回远端音频流。

OpenAI 文档明确要求：正式 API Key 只放在服务端，不要放浏览器；浏览器端使用 ephemeral token 连接 Realtime API。([OpenAI 开发者][3])

一个极简结构大概是：

```ts
// 前端
const token = await fetch("/token").then(r => r.json());

const pc = new RTCPeerConnection();

const audio = document.createElement("audio");
audio.autoplay = true;
pc.ontrack = (e) => {
  audio.srcObject = e.streams[0];
};

const mic = await navigator.mediaDevices.getUserMedia({ audio: true });
pc.addTrack(mic.getTracks()[0]);

const dc = pc.createDataChannel("oai-events");

dc.send(JSON.stringify({
  type: "session.update",
  session: {
    type: "realtime",
    model: "gpt-realtime-2",
    output_modalities: ["audio"],
    instructions: "你是一个温和、稳定、边界清晰的心理陪伴助手。",
    audio: {
      output: { voice: "marin" },
      input: {
        turn_detection: { type: "semantic_vad" }
      }
    }
  }
}));
```

### 方案 B：服务端 WebSocket 连接 OpenAI

如果你希望音频全部经过自己的服务端，或者要和现有 FastAPI / Socket.IO / Agent 管线深度整合，可以用 WebSocket。OpenAI 文档给出的连接方式是 `wss://api.openai.com/v1/realtime?model=gpt-realtime-2`，并通过 API Key 做服务端鉴权。([OpenAI 开发者][6])

这种方式的优点是后端可控性强，缺点是你要自己处理更多底层音频事件、base64 音频块、缓冲、播放、打断等逻辑。OpenAI 也明确说 WebSocket 是更底层的接口，开发者需要负责发送和处理 base64 音频块。([OpenAI 开发者][6])

### 方案 C：使用 Agents SDK 的 RealtimeAgent

OpenAI 也支持用 `@openai/agents/realtime` 快速创建语音 Agent。官方示例是用 `RealtimeAgent` + `RealtimeSession`，模型指定为 `gpt-realtime-2`，再用 ephemeral key 连接。([OpenAI 开发者][7])

这个方案适合你后面想把“语音对话、工具、handoff、guardrails、业务逻辑”统一放进 OpenAI Agents SDK 体系中。

---

## 4. 使用费用

截至官方最新价格页，`GPT-Realtime-2` 价格如下：

| 类型           |              输入 |              缓存输入 |              输出 |
| ------------ | --------------: | ----------------: | --------------: |
| Audio tokens | $32 / 1M tokens | $0.40 / 1M tokens | $64 / 1M tokens |
| Text tokens  |  $4 / 1M tokens | $0.40 / 1M tokens | $24 / 1M tokens |
| Image tokens |  $5 / 1M tokens | $0.50 / 1M tokens |         不支持图像输出 |

OpenAI 价格页和模型页都列出了这些价格。([OpenAI][8])

### 粗略折算成语音分钟

OpenAI 成本管理文档说明：用户音频是 **1 token / 100ms**，助手音频是 **1 token / 50ms**。也就是：

| 音频                  |           token 估算 |     成本估算 |
| ------------------- | -----------------: | -------: |
| 用户说 1 分钟            |   600 audio tokens |  $0.0192 |
| 模型说 1 分钟            |  1200 audio tokens |  $0.0768 |
| 用户说 30 秒 + 模型说 30 秒 | 约 900 audio tokens | 约 $0.048 |

这个只是**基础音频输入输出成本**，还没有算文本 token、系统 prompt、历史上下文、工具调用、转录成本等。Realtime 对话每一轮会把当前 conversation 作为下一轮输入，因此长会话后面会更贵；不过 OpenAI 支持自动 prompt caching，可以降低多轮会话中的输入成本。([OpenAI 开发者][9])

### 其他相关模型价格

| 模型                       | 计费方式 |          价格 |
| ------------------------ | ---: | ----------: |
| `gpt-realtime-translate` |  按时长 | $0.034 / 分钟 |
| `gpt-realtime-whisper`   |  按时长 | $0.017 / 分钟 |

这些适合实时翻译和实时转录，不是主语音 Agent 模型。([OpenAI][8])

### 成本控制建议

官方建议主要有三点：使用 prompt caching、控制上下文截断、必要时删除旧 conversation item 或用摘要替代旧消息。Realtime Playground 也可以查看样例会话的 token usage，用于估算真实成本。([OpenAI 开发者][9])

---

## 5. 效果评价

### 5.1 官方定位：强于上一代实时语音模型

OpenAI 2026 年 5 月 7 日发布说明中称，GPT-Realtime-2 是第一款具备 GPT-5 级 reasoning 的语音模型，可以处理更难请求，并更自然地推进对话。它支持 preambles、并行工具调用、工具透明化、更强恢复能力、128K 长上下文、更强术语保留、更可控的语气表达，以及可调 reasoning effort。([OpenAI][10])

### 5.2 官方评测数据

OpenAI 公布的语音评测结果是：

| 指标                   | 结果                                              |
| -------------------- | ----------------------------------------------- |
| Big Bench Audio      | GPT-Realtime-2 high 比 GPT-Realtime-1.5 高 15.2%  |
| Audio MultiChallenge | GPT-Realtime-2 xhigh 比 GPT-Realtime-1.5 高 13.8% |

官方解释这些评测更贴近生产语音 Agent，覆盖音频智能、指令遵循、多轮上下文、自一致性、自然语音纠错等能力。([OpenAI][10])

### 5.3 实际效果判断

从你的场景看，GPT-Realtime-2 的效果优势主要体现在：

| 维度    | 判断                           |
| ----- | ---------------------------- |
| 语音自然度 | 明显优于 STT+LLM+TTS 的拼接感        |
| 打断能力  | 更适合自然对话和陪伴场景                 |
| 情绪语气  | 可通过 prompt 和 voice 控制，适合心理陪伴 |
| 工具调用  | 适合接用户画像、记忆、日记、课程、情绪记录        |
| 长对话   | 128K 上下文比上一代更适合持续会话          |
| 成本    | 比普通文本模型贵，尤其模型语音输出贵           |
| 可控性   | 不如分段式 STT+LLM+TTS 完全可控       |
| 审核与记录 | 如果你必须保存每一步文本和审核链路，分段式更稳      |

官方也说明，实时 live audio 路径适合需要 conversational、immediate、barge-in、低首音频延迟、自然 turn-taking 和实时工具调用的 Agent；而 chained voice workflow 更适合需要强控制、可替换中间文本、保留 transcript、审批较重的流程。([OpenAI 开发者][7])

---

## 6. 它和 LiveKit 的关系

我的判断是：**GPT-Realtime-2 不完全替代 LiveKit。**

更准确地说：

| 组件                            | 作用                                       |
| ----------------------------- | ---------------------------------------- |
| GPT-Realtime-2 / Realtime API | 模型层 + 语音理解/生成 + 工具调用                     |
| LiveKit                       | 音视频传输层 + 房间管理 + 多端 SDK + 录制 + 复杂实时通信基础设施 |
| Pipecat                       | Pipeline 编排层                             |
| 你自己的 FastAPI / Socket.IO      | 业务后端、用户数据、工具、日志、状态管理                     |

如果你只是做一个“用户和 AI 一对一语音聊天”，可以先不用 LiveKit，直接 **前端 WebRTC → OpenAI Realtime API**，工程量最小。

但如果你要做更完整的产品，比如多人房间、录音、质检、坐席接管、SIP 电话、移动端复杂网络处理、会话监控、未来接多个模型供应商，那么 **LiveKit + GPT-Realtime-2** 会更稳。LiveKit 做 transport 和房间系统，OpenAI Realtime 做模型语音能力。

---

## 7. 对你当前 AI 心理陪伴平台的建议

我建议你优先采用这个架构：

```text
Expo / Web / RN 客户端
        ↓ WebRTC
OpenAI Realtime API / GPT-Realtime-2
        ↓ tool calls
你的 FastAPI 后端
        ↓
用户画像 / 记忆 / 日记 / 课程 / 情绪记录 / 安全策略
```

配置建议：

| 配置项              | 建议                                 |
| ---------------- | ---------------------------------- |
| 模型               | `gpt-realtime-2`                   |
| 连接方式             | Web / 移动端优先 WebRTC                 |
| VAD              | `semantic_vad`                     |
| reasoning effort | 默认 low；复杂情绪分析或工具链任务再升 medium       |
| voice            | 先试 `marin` 或 `cedar`，官方推荐这两个声音质量更好 |
| 输出               | 音频为主，必要时同时保留 transcript            |
| 工具               | 用户画像、记忆、日记、课程建议用 function tool     |
| 安全               | 心理陪伴必须加危机识别、免责声明、人工/热线转介策略         |

OpenAI 文档提到，Realtime session 可配置内置声音，当前包括 `alloy`、`ash`、`ballad`、`coral`、`echo`、`sage`、`shimmer`、`verse`、`marin`、`cedar`，并推荐 `marin` 或 `cedar` 获得较好质量。([OpenAI 开发者][1])

---

## 8. 结论

**GPT-Realtime-2 非常适合你要做的实时语音 AI 助手/心理陪伴 Agent。** 它的最大价值不是“回答更聪明”这么简单，而是把原来 STT、LLM、TTS、VAD、打断、语音事件、工具调用这些链路统一进一个实时语音模型里，能明显降低开发复杂度和语音延迟。

但它也有两个现实问题：第一，成本明显高于普通文本模型，尤其语音输出贵；第二，如果你的业务需要非常强的流程控制、完整 transcript、严格审核和可观测性，仍然需要你自己的后端 Agent 编排层，不能完全依赖 Realtime API 自己完成所有业务逻辑。

对你来说，最合理的路线是：**先用 GPT-Realtime-2 + WebRTC 做 MVP，验证语音延迟、打断、情绪陪伴体验；如果后续要做生产级房间管理、录音、质检、多端稳定性，再叠加 LiveKit。**

[1]: https://developers.openai.com/api/docs/guides/realtime-conversations "Realtime conversations | OpenAI API"
[2]: https://developers.openai.com/api/docs/models/gpt-realtime-2 "gpt-realtime-2 Model | OpenAI API"
[3]: https://developers.openai.com/api/docs/guides/realtime-webrtc "Realtime API with WebRTC | OpenAI API"
[4]: https://developers.openai.com/api/docs/guides/realtime-vad "Voice activity detection (VAD) | OpenAI API"
[5]: https://developers.openai.com/api/docs/guides/realtime-mcp "Realtime with tools | OpenAI API"
[6]: https://developers.openai.com/api/docs/guides/realtime-websocket "Realtime API with WebSocket | OpenAI API"
[7]: https://developers.openai.com/api/docs/guides/voice-agents "Voice agents | OpenAI API"
[8]: https://openai.com/api/pricing/ "OpenAI API Pricing | OpenAI"
[9]: https://developers.openai.com/api/docs/guides/realtime-costs "Managing costs | OpenAI API"
[10]: https://openai.com/index/advancing-voice-intelligence-with-new-models-in-the-api/ "Advancing voice intelligence with new models in the API | OpenAI"
