# Effective Context Engineering for AI Agents

- **Author:** Anthropic (Prithvi Rajasekaran, Ethan Dixon, Carly Ryan, Jeremy Hadfield; with contributions from Rafi Ayub, Hannah Moran, Cal Rueb, Connor Jennings)
- **Date:** September 29, 2025
- **URL:** https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

## Key Excerpts

### 1. "Goldilocks Zone" -- the right abstraction level for rules

> System prompts should be extremely clear and use simple, direct language that presents ideas at the right altitude for the agent. The right altitude is the Goldilocks zone between two common failure modes. At one extreme, we see engineers hardcoding complex, brittle logic in their prompts to elicit exact agentic behavior. This approach creates fragility and increases maintenance complexity over time. At the other extreme, engineers sometimes provide vague, high-level guidance that fails to give the LLM concrete signals for desired outputs or falsely assumes shared context. The optimal altitude strikes a balance: specific enough to guide behavior effectively, yet flexible enough to provide the model with strong heuristics to guide behavior.

Section: "The anatomy of effective context" > System Prompts

### 2. "Minimal high-signal token set" -- finding the minimal set of tokens

> Given that LLMs are constrained by a finite attention budget, good context engineering means finding the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome. Implementing this practice is much easier said than done, but in the following section, we outline what this guiding principle means in practice across the different components of context.

Supporting quote on diminishing returns:

> While some models exhibit more gentle degradation than others, this characteristic emerges across all models. Context, therefore, must be treated as a finite resource with diminishing marginal returns. Like humans, who have limited working memory capacity, LLMs have an 'attention budget' that they draw on when parsing large volumes of context. Every new token introduced depletes this budget by some amount, increasing the need to carefully curate the tokens available to the LLM.

Section: "Why context engineering is important to building capable agents"

### 3. "Examples over rule lists" -- why examples work better

> Providing examples, otherwise known as few-shot prompting, is a well known best practice that we continue to strongly advise. However, teams will often stuff a laundry list of edge cases into a prompt in an attempt to articulate every possible rule the LLM should follow for a particular task. We do not recommend this. Instead, we recommend working to curate a set of diverse, canonical examples that effectively portray the expected behavior of the agent. For an LLM, examples are the 'pictures' worth a thousand words.

Section: "The anatomy of effective context" > Examples/Few-shot prompting

### 4. "Structured sections with XML/Markdown" -- organizing prompts

> We recommend organizing prompts into distinct sections (like `<background_information>`, `<instructions>`, `## Tool guidance`, `## Output description`, etc) and using techniques like XML tagging or Markdown headers to delineate these sections, although the exact formatting of prompts is likely becoming less important as models become more capable.

Section: "The anatomy of effective context" > Structured Formatting

### 5. "Put important instructions in prominent positions" -- position matters

**Two separate sources, different coverage:**

**Source 1 — Anthropic Context Engineering Guide**
**URL:** https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

NOTE: This guide does NOT contain explicit guidance on instruction positioning (primacy/recency effects). The concept that "位置=优先级" comes from a different, separate Anthropic document.

---

**Source 2 — Anthropic Prompt Engineering Best Practices**
**Title:** *Prompting best practices — Claude 4.6*
**Author:** Anthropic
**Date:** 2025 (continuously updated; Claude 4.6 section added ~2026)
**URL:** https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices

This is where the position-equals-priority guidance actually lives. Verbatim from the "Long context prompting" section:

> **Put longform data at the top**: Place your long documents and inputs near the top of your prompt, above your query, instructions, and examples. This can significantly improve performance across all models.
>
> Queries at the end can improve response quality by up to 30% in tests, especially with complex, multi-document inputs.

Section: "Long context prompting" (under "General principles") in Anthropic Prompt Engineering Best Practices

## Article Structure (for reference)

The context engineering guide is organized into these main sections:

1. Context engineering vs. prompt engineering
2. Why context engineering is important to building capable agents
3. The anatomy of effective context
4. Context retrieval and agentic search
5. Context engineering for long-horizon tasks
   - Compaction
   - Structured note-taking
   - Sub-agent architectures
6. Conclusion

## Additional Notable Quotes

On tools and context efficiency:

> Tools allow agents to operate with their environment and pull in new, additional context as they work. Because tools define the contract between agents and their information/action space, it's extremely important that tools promote efficiency.

> One of the most common failure modes we see is bloated tool sets that cover too much functionality or lead to ambiguous decision points about which tool to use.

On just-in-time context retrieval:

> Rather than pre-processing all relevant data up front, agents built with the 'just in time' approach maintain lightweight identifiers (file paths, stored queries, web links, etc.) and use these references to dynamically load data into context at runtime using tools.

On long-horizon tasks:

> Long-horizon tasks require agents to maintain coherence, context, and goal-directed behavior over sequences of actions where the token count exceeds the LLM's context window.

> Even as models continue to improve, the challenge of maintaining coherence across extended interactions will remain central to building more effective agents.
