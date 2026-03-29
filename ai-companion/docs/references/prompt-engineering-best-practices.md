# Prompt Engineering Best Practices - 参考文献与溯源

> 为教学文档中引用的 Prompt Engineering 最佳实践提供权威来源。
> 整理日期：2026-03-26

---

## 1. 正面指令优于负面约束

**教学文档原始主张**：不做什么比做什么更重要（Negative constraints are more effective than positive instructions）

### 溯源结论

这个主张需要修正。权威来源实际上推荐的是**正面指令优于负面约束**——即告诉 AI "做什么"比告诉它"不做什么"更有效。但负面约束在划定边界时仍有其价值。

### 权威来源

#### Anthropic Claude 官方文档（Prompting Best Practices）

- **Title:** *Prompting best practices — Claude 4.6*
- **Author:** Anthropic
- **Date:** 2025 (continuously updated; Claude 4.6 section added ~2026)

在 "Control the format of responses" 一节中，Anthropic 明确建议：

> **Tell Claude what to do instead of what not to do**
> - Instead of: "Do not use markdown in your response"
> - Try: "Your response should be composed of smoothly flowing prose paragraphs."

同时，在 "Add context to improve performance" 一节中给出对比：
- Less effective: `NEVER use ellipses`
- More effective: `Your response will be read aloud by a text-to-speech engine, so never use ellipses since the text-to-speech engine will not know how to pronounce them.`

关键洞察：即使必须使用负面约束，给出理由（why）也比单纯的禁止更有效。

- 来源：https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices

#### DAIR.AI Prompt Engineering Guide

在 "To do or not to do?" 一节中明确建议避免负面指令：
- 失败示例：`DO NOT ASK FOR INTERESTS. DO NOT ASK FOR PERSONAL INFORMATION.`
- 推荐方式：`The agent is responsible to recommend a movie from the top global trending movies.`

- 来源：https://www.promptingguide.ai/introduction/tips

#### Anthropic "Effective Context Engineering for AI Agents" 博客

推荐使用校准过的具体性（calibrated specificity），避免极端的禁令列表，改用代表性示例来展示期望行为。

- 来源：https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

### 教学建议

教学文档中的表述需要调整。更准确的说法是：
- 正面指令（"做什么"）通常比负面约束（"不做什么"）更有效
- 如果必须使用负面约束，同时给出原因（why）和替代行为
- 在角色设定中，用"你是一个温暖的倾听者"比"你不是冷漠的机器"更有效

---

## 2. 具体数字优于模糊描述

**教学文档原始主张**：具体数字 > 模糊描述（"不超过80字" 优于 "回复要简短"）

### 溯源结论

有广泛的权威来源支持。所有主流 LLM 厂商的官方指南都一致强调"具体 > 模糊"。

### 权威来源

#### Anthropic Claude 官方文档

在 "Be clear and direct" 一节中：

> Being specific about your desired output can help enhance results. If you want "above and beyond" behavior, explicitly request it rather than relying on the model to infer this from vague prompts.
>
> **Golden rule:** Show your prompt to a colleague with minimal context on the task and ask them to follow it. If they'd be confused, Claude will be too.

- 来源：https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices

#### DAIR.AI Prompt Engineering Guide

在 "Avoid Impreciseness" 一节中给出具体示例：
- 模糊：请求"几句话"（a few sentences）
- 具体：`Use 2-3 sentences to explain the concept of prompt engineering to a high school student.`

- 来源：https://www.promptingguide.ai/introduction/tips

#### OpenAI GPT-4.1 Prompting Guide

在示例中展示具体数字的使用，如 "3 lines of context immediately above and 3 lines immediately below each change"，并强调规则列表中的行为需要可量化。

- 来源：https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide

#### PromptLayer 博客（引用 Anthropic 高级 Prompt 工程师 Zack Witten 的建议）

指出应使用具体的句子数量范围（如 "Limit your response to 2-3 sentences"）而非模糊的"be concise"，并建议包含数量、时间范围和具体焦点领域。

- 来源：https://blog.promptlayer.com/prompt-engineering-with-anthropic-claude-5399da57461d/

### 注意事项

LLM 对精确字数/字符数的控制是近似的而非精确的。"不超过80字"作为指导是有效的，但不要期望模型精确遵守到个位数。结构化描述（如"2-3段"、"3个要点"）通常比精确字数更容易被遵循。

---

## 3. 位置影响优先级

**教学文档原始主张**：位置 = 优先级（Position affects priority），放在前面的规则获得更高优先级。

### 溯源结论

有学术研究和厂商文档支持，但情况比"越前越优先"更复杂。不同模型表现不同，且存在"中间丢失"现象。

### 权威来源

#### 学术研究：Lost in the Middle

**Liu et al., "Lost in the Middle: How Language Models Use Long Contexts"**
Transactions of the Association for Computational Linguistics (TACL), 2024

关键发现：LLM 展现出 U 型性能曲线——开头和结尾的信息被最好地利用，中间位置的信息最容易被忽略。

- 来源：https://arxiv.org/abs/2307.03172
- 发表于：https://aclanthology.org/2024.tacl-1.9/

#### 学术研究：Serial Position Effects of Large Language Models

**Guo & Vosoughi, "Serial Position Effects of Large Language Models"**, 2024

发现 LLM 展现出类似人类的序列位置效应，包括首因效应（primacy effect）和近因效应（recency effect）。精心设计的 prompt 可以在一定程度上缓解这些偏差，但效果不一致。

- 来源：https://arxiv.org/abs/2406.15981

#### 学术研究：Primacy Effect of ChatGPT

**"Primacy Effect of ChatGPT"**, arXiv 2310.13206, 2024

发现 ChatGPT 的决策对 prompt 中标签的顺序敏感，倾向于选择较早位置的标签。

- 来源：https://arxiv.org/abs/2310.13206

#### 学术研究：Exploiting Primacy Effect

**Raimondi et al., "Exploiting Primacy Effect To Improve Large Language Models"**, RANLP 2025

研究者发现首因效应在多选题回答中显著影响 LLM 表现，微调会放大这种偏差。通过策略性重排选项可以利用这一效应提升性能。

- 来源：https://arxiv.org/abs/2507.13949

#### 学术研究：Judging the Judges

**Shi et al., "Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge"**, AACL-IJCNLP 2025

对 15 个 LLM 评判者进行约 150,000 次评估，发现位置偏差不是随机的，且在不同评判者和任务间显著变化。

- 来源：https://arxiv.org/abs/2406.07791

#### OpenAI GPT-4.1 Prompting Guide（厂商实践）

明确给出位置指导：
- 长上下文中，最理想的做法是把指令**同时放在开头和结尾**
- 如果只放一处，放在上下文**上方**比下方效果更好
- 当指令冲突时，GPT-4.1 倾向于遵循**更靠近结尾**的指令

- 来源：https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide

#### Anthropic Claude 官方文档

在 "Long context prompting" 一节中：
- 把长文档数据放在 prompt 的**顶部**
- 查询放在底部可以将响应质量提升高达 30%

- 来源：https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices

### 教学建议

"位置=优先级"的说法需要细化：
- **Claude**：长文档放顶部，查询/指令放底部效果最佳
- **GPT 系列**：冲突指令时，后出现的优先；长上下文时，首尾同时放指令最佳
- **通用规律**：中间位置的信息最容易被忽略（Lost in the Middle）
- 建议表述为："位置影响注意力分配，开头和结尾最受重视，中间最容易被忽略"

---

## 4. 示例胜过规则列表

**教学文档原始主张**：示例胜过规则（Examples are worth more than rule lists）

### 溯源结论

有强力的权威来源支持。Anthropic 博客文章中有非常直接的论述。

### 权威来源

#### Anthropic "Effective Context Engineering for AI Agents" 博客（最直接的来源）

这是最权威且最直接的支持：

> "teams will often stuff a laundry list of edge cases into a prompt in an attempt to articulate every possible rule the LLM should follow for a particular task. We do not recommend this. Instead...curate a set of diverse, canonical examples"
>
> "For an LLM, examples are the 'pictures' worth a thousand words."

- 来源：https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

#### Anthropic Claude 官方文档

在 "Use examples effectively" 一节中：

> Examples are one of the most reliable ways to steer Claude's output format, tone, and structure. A few well-crafted examples (known as few-shot or multishot prompting) can dramatically improve accuracy and consistency.

建议使用 3-5 个示例获得最佳效果。

- 来源：https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices

#### OpenAI GPT-4.1 Prompting Guide

建议将示例与规则结合使用：

> "Ensure that any important behavior demonstrated in your examples are also cited in your rules."

- 来源：https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide

#### 奠基论文：Brown et al. (2020)

**Brown et al., "Language Models are Few-Shot Learners"**, NeurIPS 2020

这篇论文（GPT-3 论文）奠定了 few-shot prompting 的学术基础，展示了仅通过在 prompt 中提供少量示例（而非微调），大型语言模型就能在大量 NLP 任务上取得强劲表现。

- 来源：https://arxiv.org/abs/2005.14165

### 教学建议

这个主张有充分的权威支持。建议在教学中强调：
- 3-5 个精选示例比长篇规则列表更有效（Anthropic 推荐）
- 示例应多样化，覆盖边界情况
- 最佳实践是**示例 + 关键规则结合**（OpenAI 推荐），而非完全抛弃规则

---

## 5. CodeConductor Context Engineering 四大支柱

**教学文档原始主张**：引用 CodeConductor 的 Context Engineering 指南，提出"四大支柱：composition, ordering, formatting, feedback loops"

### 溯源结论

CodeConductor 确实发布了一篇 Context Engineering 指南，但其四大支柱的实际命名与教学文档中引用的不完全一致。

### 实际内容

#### CodeConductor 博客文章

- **Title:** *Context Engineering: The Secret Sauce of AI Agent Builders*
- **Author:** CodeConductor Team
- **Date:** September 30, 2025
- **URL:** https://codeconductor.ai/blog/context-engineering

CodeConductor 提出的**四大支柱**实际为（Verbatim quotes from the blog post）：

1. **Context Composition**（上下文组合）：
   > "Context composition is about selecting the right ingredients."

2. **Context Ranking and Relevance**（上下文排序与相关性）：
   > "More context is not always better. Irrelevant or noisy inputs can confuse the model or cause it to focus on the wrong signals."

3. **Context Optimization**（上下文优化）：
   > "LLMs have limited context windows. That means you cannot feed them everything."

4. **Context Orchestration**（上下文编排）：
   > "Context is not static. In real-world systems, it is generated dynamically based on the task, user input, tool state, or previous steps."

Feedback loops 作为补充实践（非四大支柱之一）：
> "Feedback loops to improve context selection or adjust system behavior over time"

- 来源：https://codeconductor.ai/blog/context-engineering

### 教学建议

教学文档中引用的"四大支柱"名称（composition, ordering, formatting, feedback loops）与原文不完全匹配。原文使用的是 composition, ranking, optimization, orchestration。建议：
- 如引用 CodeConductor，使用其原始术语
- 或标注为"基于 CodeConductor 框架改编"，列出教学版本的术语
- feedback loops 在原文中是独立的补充概念，而非四大支柱之一

---

## 6. AI 默认行为是"什么都做"（B8）

**教学文档原始主张**：AI 的默认行为就是"什么都做"——它会安慰、分析、建议、共情、总结……全部自动加上。

### 溯源结论

Anthropic 官方文档明确描述了这一行为，并提供了约束方法。

### 权威来源

#### Anthropic Claude 官方文档 — Overeagerness（过度积极）

- **Title:** *Prompting best practices — Claude 4.6*
- **Author:** Anthropic
- **Date:** 2025 (continuously updated; Claude 4.6 section added ~2026)

**Section: "Agentic systems" > "Overeagerness"**

> Claude Opus 4.5 and Claude Opus 4.6 have a tendency to overengineer by creating extra files, adding unnecessary abstractions, or building in flexibility that wasn't requested.

官方建议的约束 prompt 直接列举了 AI 默认会做但不应该做的行为：

> - Don't add features, refactor code, or make "improvements" beyond what was asked.
> - Don't add error handling, fallbacks, or validation for scenarios that can't happen.
> - Don't create helpers, utilities, or abstractions for one-time operations.
> - Don't design for hypothetical future requirements.

- 来源：https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices

#### Anthropic Claude 官方文档 — Balancing autonomy and safety

**Section: "Agentic systems" > "Balancing autonomy and safety"**

> Without guidance, Claude Opus 4.6 may take actions that are difficult to reverse or affect shared systems, such as deleting files, force-pushing, or posting to external services.

这进一步证实：**没有约束时，AI 默认什么都做**——包括破坏性操作。

- 来源：https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices

### 教学建议

教学文档中"AI 的默认行为就是什么都做"的表述与 Anthropic 官方描述一致。关键教学点：
- AI 不需要被告知"做什么"——它默认就会做很多事
- 人格塑造的核心是"不做什么"——通过禁止项约束默认行为
- 这不是 bug，是 RLHF 训练的结果（模型被训练为"尽可能有帮助"）

---

## 汇总：所有引用来源

### 厂商官方文档

| 来源 | URL |
|------|-----|
| Anthropic - Prompting Best Practices (Claude 4.6) | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices |
| Anthropic - Effective Context Engineering for AI Agents | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| OpenAI - GPT-4.1 Prompting Guide | https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide |
| DAIR.AI - Prompt Engineering Guide | https://www.promptingguide.ai/introduction/tips |
| CodeConductor - Context Engineering Guide | https://codeconductor.ai/blog/context-engineering |

### 学术论文

| 论文 | 作者 | 发表 | URL |
|------|------|------|-----|
| Lost in the Middle: How Language Models Use Long Contexts | Liu et al. | TACL 2024 | https://arxiv.org/abs/2307.03172 |
| Serial Position Effects of Large Language Models | Guo & Vosoughi | arXiv 2024 | https://arxiv.org/abs/2406.15981 |
| Primacy Effect of ChatGPT | - | arXiv 2024 | https://arxiv.org/abs/2310.13206 |
| Exploiting Primacy Effect To Improve Large Language Models | Raimondi et al. | RANLP 2025 | https://arxiv.org/abs/2507.13949 |
| Judging the Judges: Position Bias in LLM-as-a-Judge | Shi et al. | AACL-IJCNLP 2025 | https://arxiv.org/abs/2406.07791 |
| Language Models are Few-Shot Learners (GPT-3) | Brown et al. | NeurIPS 2020 | https://arxiv.org/abs/2005.14165 |
