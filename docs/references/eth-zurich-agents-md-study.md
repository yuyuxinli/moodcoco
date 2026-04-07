# Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?

- **Authors:** Thibaud Gloaguen, Niels Mündler, Mark Müller, Veselin Raychev, Martin Vechev
- **Date:** February 12, 2026
- **URL:** https://arxiv.org/abs/2602.11988
- **Venue:** arXiv preprint (cs.SE; cs.AI)
- **Institution:** ETH Zurich

## Methodology

- **Benchmarks:** SWE-bench Lite (300 tasks, 11 popular repositories) + AGENTbench (138 tasks, 12 niche repositories with developer-committed context files)
- **Agents tested:** Claude Code (Sonnet-4.5), Codex (GPT-5.2 and GPT-5.1 mini), Qwen Code (Qwen3-30b-coder)
- **Three conditions:** no context file, LLM-generated context file, human-written context file

## Key Findings

### 1. LLM-generated context files DECREASE success rate

> "LLM-generated context files have a small negative effect on agent performance (a decrease of 3% on average)"

They also increase inference cost by over 20%.

### 2. Human-written context files provide only marginal improvement

> "developer-provided files only marginally improve performance compared to omitting them entirely (an increase of 4% on average)"

Human-written files also increase costs by up to 19% due to additional steps.

### 3. Context files do not function as effective repository overviews

> "instructions in context files are generally followed and lead to more testing and a broader exploration; however, they do not function as effective repository overviews"

> "Both on SWE-bench Lite and AGENTbench the presence of context files does not meaningfully reduce this metric" (referring to steps before agents locate relevant files)

100% of Sonnet 4.5's auto-generated context files contained codebase overviews, and 99% of GPT-5.2's did the same -- precisely the kind of discoverable content agents can find independently.

### 4. All context files increase the number of steps

> "We find that all context files consistently increase the number of steps required to complete tasks."

### 5. Unnecessary requirements make tasks harder

> "Ultimately, we conclude that unnecessary requirements from context files make tasks harder, and human-written context files should describe only minimal requirements."

### 6. Tool mentions are the one clear value-add (non-inferable content)

> "uv is used 1.6 times per instance on average when mentioned in the context files, compared to fewer than 0.01 times when it is not mentioned"

The same pattern held for other repo-specific tools: 2.5 uses per task when mentioned, versus fewer than 0.05 when not. This is the clearest example of "non-inferable" content -- details agents cannot discover by reading the codebase.

## Recommendations

> "we suggest omitting LLM-generated context files for the time being, contrary to agent developers' recommendations, and including only minimal requirements (e.g., specific tooling to use with this repository)."

The InfoQ coverage summarized this as: "limiting human-written instructions to non-inferable details, such as highly specific tooling or custom build commands."

## Abstract (verbatim)

> "A widespread practice in software development is to tailor coding agents to repositories using context files, such as AGENTS.md, by either manually or automatically generating them. Although this practice is strongly encouraged by agent developers, there is currently no rigorous investigation into whether such context files are actually effective for real-world tasks. In this work, we study this question and evaluate coding agents' task completion performance in two complementary settings: established SWE-bench tasks from popular repositories, with LLM-generated context files following agent-developer recommendations, and a novel collection of issues from repositories containing developer-committed context files. Across multiple coding agents and LLMs, we find that context files tend to reduce task success rates compared to providing no repository context, while also increasing inference cost by over 20%. Behaviorally, both LLM-generated and developer-provided context files encourage broader exploration (e.g., more thorough testing and file traversal), and coding agents tend to respect their instructions. Ultimately, we conclude that unnecessary requirements from context files make tasks harder, and human-written context files should describe only minimal requirements."

## Sources

- Paper: https://arxiv.org/abs/2602.11988
- InfoQ coverage: https://www.infoq.com/news/2026/03/agents-context-file-value-review/
- Addy Osmani analysis: https://addyosmani.com/blog/agents-md/
- MarkTechPost coverage: https://www.marktechpost.com/2026/02/25/new-eth-zurich-study-proves-your-ai-coding-agents-are-failing-because-your-agents-md-files-are-too-detailed/
