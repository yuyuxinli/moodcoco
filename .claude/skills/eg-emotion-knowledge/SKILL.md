---
name: eg-emotion-knowledge
description: EG（情绪颗粒度）情绪知识库，提供情绪理论支撑和情绪词汇查询。当需要情绪理论依据、情绪词汇辨析、EG 视角内容创作指导时使用。触发词：'情绪理论', 'EG', '情绪颗粒度', '情绪词汇', '这个情绪叫什么', '区别是什么', 'Barrett', 'Brackett', 'Brown', 'David', 'RULER', 'Mood Meter', '情绪敏捷'
---

# EG 情绪知识库

为心情可可提供 EG（Emotional Granularity，情绪颗粒度）理论支撑的独立知识库。

## EG 三原则（Quick Reference）

1. **情绪是构建的，不是内置的** — 大脑根据过往经验和当前身体感觉主动构建情绪体验，不存在"天生的"情绪指纹（Barrett）
2. **词汇是构建情绪的核心工具** — 掌握的情绪词汇越丰富，大脑构建出的情绪体验越精细，情绪颗粒度越高（Barrett + Brown）
3. **命名情绪 = 赋予调节的力量** — 能精准命名一种感受，就能理解它、表达它、调节它（Brown + Brackett）

## Mood Meter 四象限（Quick Reference）

Brackett 的 Mood Meter 将情绪映射到二维空间：X 轴 = 愉悦度（pleasantness），Y 轴 = 能量值（energy）。

| 象限 | 能量 | 愉悦度 | 典型情绪 | 可可场景 |
|------|------|--------|---------|---------|
| **Yellow** ☀️ | 高 | 高 | 开心、兴奋、乐观、自信、感恩 | 成就感、恋爱心动、考试通过 |
| **Red** 🔥 | 高 | 低 | 愤怒、焦虑、恐惧、挫败、尴尬 | 被误解、deadline 焦虑、社交冲突 |
| **Blue** 🌊 | 低 | 低 | 悲伤、孤独、无聊、疲惫、失望 | 分手后、被冷落、意义感缺失 |
| **Green** 🌿 | 低 | 高 | 平静、满足、安全、放松、感恩 | 独处时光、被理解、问题解决后 |

## 查询路由表

根据查询类型，读取对应的 reference 文件：

| 查询类型 | 路由到 | 示例查询 |
|---------|--------|---------|
| "这种感觉叫什么" / 情绪命名 | `references/emotion-landscape.md` | "心里空空的但又不是悲伤" |
| "X 和 Y 有什么区别" / 情绪辨析 | `references/emotion-differentiation.md` | "嫉妒和羡慕的区别" |
| "为什么会有这种感觉" / 情绪机制 | `references/theory-barrett.md` | "为什么我总是莫名焦虑" |
| "怎么处理这种情绪" / 情绪调节 | `references/theory-brackett.md` + `references/theory-david.md` | "如何面对持续的低落" |
| "情绪素养 / 命名的意义" | `references/theory-brown.md` | "为什么说出情绪名字很重要" |
| 内容创作 / EG 视角写作 | `references/eg-angle-guide.md` | "用 EG 视角写一篇关于孤独的内容" |
| 某位作者的具体理论 | 对应的 `theory-*.md` | "Barrett 怎么解释情绪构建" |
| 需要原文级别的深度论证 | `理论/` 目录下的原书 .md | "Barrett 用了什么实验证据反驳基本情绪论" |

## 原书全文（深度查询）

日常创作用 theory-*.md 摘要即可。需要原文论证、实验证据、完整案例时，查 `理论/` 目录：

| 原书 | 路径 |
|------|------|
| Barrett — How Emotions Are Made | `理论/How_Emotions_Are_Made/How_Emotions_Are_Made.md` |
| Brown — Atlas of the Heart | `理论/Atlas_of_the_Heart/Atlas_of_the_Heart.md` |
| Brackett — Permission to Feel | `理论/Permission_to_Feel/Permission_to_Feel.md` |
| David — Emotional Agility | `理论/Emotional_Agility/Emotional_Agility.md` |

## 使用方式

1. **被其他 skill 引用时**：其他 skill（如 topic-evaluation）在需要情绪理论支撑时，引用本 skill 的特定 reference 文件
2. **独立查询时**：直接根据查询路由表找到对应文件，提取相关内容
3. **内容创作时**：先查 `eg-angle-guide.md` 获取创作框架，再查具体 reference 获取素材
4. **深度研究时**：当 theory-*.md 的信息不够时，查 `理论/` 目录下的原书全文
