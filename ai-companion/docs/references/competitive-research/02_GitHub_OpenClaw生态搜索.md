# OpenClaw 生态心理健康应用调研

*2026-04-04 调研*

## 结论

**OpenClaw 生态在心理健康方向是空白市场。** 没有任何成熟的心理干预 skill 可以直接复用。

## OpenClaw 生态内的心理/情感相关项目

### 1. soul-companion (tiankong0101-byte, 1 star)
- 纯 prompt 级 skill，无代码逻辑，只有一个 `SKILL.md` 定义了虚拟人格"飞飞"
- 4 个模式：日常/安慰/倾听/撒娇，全靠 prompt 切换
- **评价：玩具级，无记忆、无情绪追踪、无循证疗法框架**

### 2. openclaw-companion-memory (fangligamedev, 3 stars)
- **唯一值得关注的项目**
- 三层记忆系统：语义知识(长期偏好/承诺)、情景快照(日记式摘要)、自主状态(后台 life tick)
- TypeScript 实现，有 15+ 配置项，支持定时触发(每小时)
- 关键能力：`record_dialogue` / `summarize_episodic` / `query_cognitive_fs` / `life_tick`（自主决定是否主动联系用户）
- **亮点：life_tick 机制** — 即使用户不说话，AI 也有"后台生活"，会根据时间(夜间休眠/清晨)自主决定行为
- **局限：纯记忆架构，不含任何心理干预逻辑**

## 开源心理健康 AI 项目（非 OpenClaw）

大量但全部低质。"AI therapy chatbot" 返回的项目全在 0-26 星之间，均为课程作业或 hackathon 原型。

略有参考价值的：
- **Zenify** (11 stars): RAG + MCP 架构，含日记、情绪追踪、危机警报
- **TherapyBot** (1 star): 离线 + 语音 + CBT + 情绪追踪 + 危机支持，功能列表最全但无法验证质量
- **cbt-group-chat** (韩国): 专注群聊场景的 CBT 框架，与训练营模式有一定相关性

## 对心情可可的意义

心理干预的核心逻辑（CBT/ACT/叙事疗法/动机式访谈）必须自己基于学术文献构建。companion-memory 的记忆架构思路（语义/情景/自主三层）对记忆系统设计有参考价值。
