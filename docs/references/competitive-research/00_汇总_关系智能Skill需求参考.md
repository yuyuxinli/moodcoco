# 关系智能 Skill 需求参考（汇总）

*2026-04-04 | 基于 4 路并行调研汇总*

## 行业格局

- OpenClaw 生态在心理健康方向是**空白市场**
- 中文开源心理大模型（EmoLLM、SoulChat、MindChat）比英文开源强很多
- Ash（$93M 融资）是行业中最接近"关系智能"方向的产品

## 从竞品中可抽象的能力（按关系智能优先级排）

| 能力 | 来源/参考 | 对关系智能的价值 |
|------|---------|---------------|
| **关系模式洞察** | Ash（周报洞察）、diary skill | 核心差异化 |
| **跨会话关系记忆** | a16z companion-app、companion-memory、memU | 全行业最大痛点 |
| **危机识别与转介** | Wysa SOS 模式、架构文档 0.6 层 QPR | 安全底线 |
| **场景化微干预工具库** | Wysa 150+ 练习、本地"接住方案穷举"50+ 方案 | 用户有事可做 |
| **每日签到/轻跟进** | Wysa 晨间签到（论文证实）、N.E.K.O 主动触达 | 留存关键 |
| **对话式心理评估** | PsyDI（多轮渐进评估）、SoulChat 2.0 | 替代问卷 |
| **情绪识别** | Hume EVI（语音）、EmoLLM（文本） | 驱动标签和洞察 |

## 给交大团队的需求建议

### 第一批（安全+核心）

1. **crisis-intervention** — 结构化 QPR 评估，分级标准，转介话术。参考 Wysa SOS
2. **relationship-insight** — 跨对话关系模式识别，基于"人×事件×自我"三维记忆。参考 Ash weekly insights
3. **base-communication** — 架构 2.4 层"承接组/澄清组/轻推动组"变成可执行 skill

### 第二批（留存+体验）

4. **daily-checkin** — 晨间情绪签到 + 轻跟进。参考 Wysa + N.E.K.O
5. **therapy-toolkit** — 按场景匹配微干预。参考 Wysa 150+ 练习 + 本地 50+ 接住方案
6. **progressive-assessment** — 对话式心理评估。参考 PsyDI

### 第三批（升级现有）

7. 升级 **diary** — 六元组对齐 SORC
8. 升级 **calm-down** — 明确适用边界
9. 废弃 **emotion-journal** + **relationship-skills**

## 详细调研文档

- [01 行业竞品调研](./01_行业竞品_AI情绪陪伴产品调研.md)
- [02 OpenClaw 生态搜索](./02_GitHub_OpenClaw生态搜索.md)
- [03 GitHub AI Companion Agent](./03_GitHub_AI_Companion_Agent调研.md)
- [04 本地竞品资料索引](./04_本地竞品资料索引.md)
