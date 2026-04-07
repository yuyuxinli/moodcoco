# GitHub AI 陪伴/心理/情感 Agent 调研报告

*2026-04-04 调研*

## 8 个值得关注的开源项目

### 1. SillyTavern/SillyTavern — 25,228 stars
https://github.com/SillyTavern/SillyTavern

角色扮演前端的事实标准。核心能力是**角色卡系统**（World Info/Lorebook 知识注入）、多轮记忆摘要、群聊多角色、TTS/STT。本身不做心理学，但记忆管理和角色一致性机制是行业最成熟的开源实现。Tech: JavaScript/Node.js。

### 2. Shaunwei/RealChar — 6,209 stars
https://github.com/Shaunwei/RealChar

实时语音 AI 角色引擎。全链路：Whisper STT + LLM + ElevenLabs TTS + Chroma 向量记忆。亮点是**端到端实时语音对话**延迟优化和角色人格定制。Tech: JavaScript + Python。

### 3. a16z-infra/companion-app — 5,942 stars
https://github.com/a16z-infra/companion-app

a16z 出品的 AI 伴侣框架。核心亮点：**长期记忆系统**（向量数据库存储对话历史 + 相似度检索）、人格描述文件驱动角色、一键部署。代码精简，适合二次开发。Tech: TypeScript/Next.js + Pinecone/Supabase。

### 4. SmartFlowAI/EmoLLM — 1,721 stars
https://github.com/SmartFlowAI/EmoLLM

**最完整的中文心理健康大模型项目**。覆盖全流程：预训练数据集构建、SFT 微调（InternLM/Qwen/DeepSeek 等 6+ 模型）、RAG 增强、专业评估体系、部署方案。有专门的心理咨询多轮对话数据集。**对心情可可最有直接参考价值。** Tech: Python。

### 5. Project-N-E-K-O/N.E.K.O — 912 stars
https://github.com/Project-N-E-K-O/N.E.K.O

最有野心的 AI 伴侣项目。核心差异化：**24/7 环境感知**（屏幕/麦克风持续监听）、**情感引擎**（内置情绪状态机）、**主动触达**（不等用户开口，主动发起对话）、Agent 工具调用能力。开源中最接近"有生命感"的方案。Tech: JavaScript。

### 6. scutcyr/SoulChat + SoulChat2.0 — 724 + 237 stars
https://github.com/scutcyr/SoulChat
https://github.com/scutcyr/SoulChat2.0

华南理工出品。1.0 是中文心理健康对话模型，2.0 升级为**心理咨询师数字孪生框架**——可以克隆真实咨询师的对话风格。学术论文支撑，有专业心理咨询数据集。Tech: Python。

### 7. X-D-Lab/MindChat — 707 stars
https://github.com/X-D-Lab/MindChat

中文心理大模型，基于 Qwen/InternLM 微调。特色是**多场景覆盖**（情绪疏导、心理咨询、日常陪聊），有 QLoRA 训练方案，部署门槛低。Tech: Python。

### 8. opendilab/PsyDI — 204 stars
https://github.com/opendilab/PsyDI

**心理测量 Agent**（如 MBTI）。独特之处：不是简单问卷，而是通过多轮渐进式对话做心理评估，结合强化学习优化对话策略。对"用户画像建模"有参考价值。Tech: TypeScript + RL。

## 关键发现

- **心理/治疗类**：中文生态远强于英文开源。EmoLLM、SoulChat、MindChat 形成完整梯队
- **伴侣/角色类**：SillyTavern 是绝对霸主，记忆和角色系统最成熟。N.E.K.O 的主动触达 + 情感引擎值得重点研究
- **心情可可最应关注**：EmoLLM（数据集+训练方法）、N.E.K.O（主动触达+情感状态机）、a16z companion-app（记忆架构）、PsyDI（对话式心理评估）
