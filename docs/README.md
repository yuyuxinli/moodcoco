# 心情可可 · 文档索引

**核心定位：关系智能** — AI 治愈系好友，帮 18-24 岁女性在亲密关系中看见自己。

---

## 产品文档

| 文档 | 内容 |
|------|------|
| [产品技术架构](product-architecture.md) | 顶层入口：五层技术栈 + 关系状态机 + 决策引擎 |
| [产品需求 PRD](product/prd.md) | 问题定义、用户画像、Feature 清单 |
| [产品定位](product/product-context.md) | 一句话定位、差异化、技术栈概述 |
| [体验设计 F01-F11](product/product-experience-design.md) | 每个 Feature 的逐节点交互设计 |

## 需求文档

| 文档 | 内容 |
|------|------|
| [JTBD 新群体分析](需求/jtbd-new-segments.md) | 新用户群体的 Jobs-to-be-Done |
| [R0 · 初始需求](需求/R0-初始需求/) | 用户画像、产品方向、需求优先级、JTBD |
| [R1 · 群体 1 — 关系模式](需求/R1-群体1-关系模式/ost-segment1.md) | 频繁切换关系用户的机会-方案树 |
| [R2 · 群体 2 — 无关系](需求/R2-群体2-无关系/ost-segment2.md) | 无关系用户的机会-方案树 |

## 原则

| 文档 | 内容 |
|------|------|
| [产品设计原则](原则/产品设计原则.md) | 核心设计原则和约束 |

## 技术文档

| 文档 | 内容 |
|------|------|
| [技术设计](technical/technical-design.md) | 各 Feature 的技术实现方案 |
| [OpenClaw 平台能力](technical/openclaw-capabilities.md) | OpenClaw 能力参考 + 已用/未用清单 |
| [实施计划 v1](technical/implementation-plan.md) | 初版实施计划 |
| [实施计划 v2](technical/implementation-plan-v2.md) | 第二版实施计划 |
| [配置文档](technical/配置/) | model-config / session-isolation / compaction / cron / group-setup |

## AI Companion 运行时文档

从 `ai-companion/` 移入的文档，记录可可的运行时架构细节：

| 文档 | 内容 |
|------|------|
| [AGENTS 完整版](AGENTS-FULL.md) | 四步对话框架 + Skill 路由的完整版本 |
| [HEARTBEAT 说明](HEARTBEAT.md) | 主动关怀检查清单详细文档 |
| [Memory 配置](memory-setup.md) | 记忆系统的配置和使用说明 |
| [OpenClaw 解剖](openclaw-anatomy.md) | OpenClaw 平台架构解析 |
| [Skill 创建指南](pm-guide-skill-creation.md) | PM 视角的 Skill 创建流程 |

## 参考资料

| 文档 | 内容 |
|------|------|
| [竞品调研](references/理论/competitor-research-2026.md) | Woebot / Wysa / Ash / Replika / Pi 等竞品分析 |
| [心理学理论](references/理论/) | Atlas of the Heart / Emotional Agility / 情绪颗粒度等 |
| [情绪聚类](references/emotion_clusters.md) | 情绪分类和聚类模型 |
| [团队成员](references/团队成员.md) | 团队信息 |
| [Agents.md 最佳实践](references/agents-md-best-practices.md) | Agent 配置文件的写作规范 |
| [Anthropic 上下文工程](references/anthropic-context-engineering.md) | Anthropic 的 context engineering 方法论 |
| [ETH Zurich Agents.md 研究](references/eth-zurich-agents-md-study.md) | 学术研究：Agents.md 的效果分析 |
| [Prompt 工程最佳实践](references/prompt-engineering-best-practices.md) | Prompt 设计参考 |
| [心理学技术](references/psychology-techniques.md) | 心理学干预技术参考 |

## 公众号素材

| 文档 | 内容 |
|------|------|
| [v2 Evolve 数据报告](公众号/素材/v2-evolve-数据报告.md) | v2 版本 Evolve 测试数据 |
| [v2 Evolve 测试清单](公众号/素材/v2-evolve-测试清单.md) | v2 版本测试场景清单 |
| [v3 深度测试方案](公众号/素材/v3-深度测试方案.md) | v3 版本深度测试计划 |

## 运行时文件（可可自己读的）

位于 `ai-companion/` 目录：

| 文件 | 作用 |
|------|------|
| `SOUL.md` | 可可的人格规则 |
| `AGENTS.md` | 四步对话框架 + Skill 路由 |
| `HEARTBEAT.md` | 主动关怀检查清单 |
| `IDENTITY.md` | 名称和身份 |
| `TOOLS.md` | UI Tool 输出规则 |
| `skills/` | Skill 的具体指令 |
| `memu/` | memU 记忆引擎 |
