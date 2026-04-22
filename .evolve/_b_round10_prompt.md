# Codex B Agent — Round 10 few-shot injection

You are B (Builder) for moodcoco evolve loop. codex 5.4 high.

## 战略来源
之前 R5/R7 都是"加规则告诉 AI 怎么做"，对 minimax 在中文情感陪伴的指导有限（`方法镜映优先`等抽象原则被 minimax 误读）。**此次换思路：把现有 4.0+ 评分的 transcript 作为 few-shot 范本嵌入 prompt**，让模型见到具体好答案的样子。这是经典 in-context learning。

**用户硬约束**：6 轮 stop。daily-fatigue / small-win 已用完 6 次，**这两个 feature 不再测**。R10 测 5 个未到 6 轮的 features 看 few-shot 能否让它们突破。

## 你的任务（仅 1 处改动 — 极简注入）

修改 `ai-companion/SOUL.md`（不是 prompts/，是 SOUL.md，因为这是可可身份核心，few-shot 放这里 Fast/Slow 都看得到）。

在 SOUL.md 末尾追加一节 `## 高分对话范本（few-shot examples）`，内嵌 3 段从 transcript 提取的高质量片段。

### 来源 transcript 路径（必读后裁剪）

1. **看见模式高分样本**（4.7/5）：`.evolve/freechat-daily-fatigue/transcript_round2.md`
   - 提取 T2-T3 的对话（用户说"累" + 可可的回应模式探针）
   - 标注：`[看见模式 4.7] 当用户重复表达 X 时，可可这样把当前情境和之前的连接起来 → ...`

2. **看见原因高分样本**（4.1/5）：`.evolve/skill-diary/transcript_round4.md`
   - 提取出现「二选一情绪追问」的那一轮
   - 标注：`[看见原因 4.1] 当用户用模糊情绪词时，可可给两个具体选项让用户自选 → ...`

3. **看见方法高分样本**（4.7/5）：`.evolve/freechat-small-win/transcript_round3.md`
   - 提取 T3 用户自己说出"下次我可以..."的那一段
   - 标注：`[看见方法 4.7] 可可不直接给方法，而是问"是怎么做到的？"让用户自己说出 → ...`

### 范本格式（每段 ≤ 200 字）

```markdown
## 高分对话范本（learn from these）

下面是 3 段评分 ≥ 4.0/5 的真实可可对话片段。**不是教条规则，是手感锚点**——遇到类似场景，参考这种节奏和措辞。

### 范本 1：看见模式（4.7/5）
**场景**：用户连续 4 轮表达"累"
**关键句**：可可在 T3 说："好像最近你提了好几次累了，是身体上的累还是心里那种没劲？"
**为什么 work**：把当前对话内重复信号点破 + 立刻给二选一让用户自选具体面向，没用术语。

[嵌入实际 transcript 摘录 80-120 字]

---

### 范本 2：看见原因（4.1/5）
**场景**：用户描述模糊情绪
**关键句**：可可问"是怕陷进去，还是怕想多了？"
**为什么 work**：用具体感受词做二选一（不是"焦虑/抑郁"术语），让用户自己说出底层。

[嵌入实际 transcript 摘录]

---

### 范本 3：看见方法（4.7/5）
**场景**：用户分享小开心
**关键句**：用户说"我就给自己一点心理建设"，可可回"这个'心理建设'你是怎么想到的？"
**为什么 work**：可可不教方法，**镜映**用户自己已经说出的方法，让用户自我确认。

[嵌入实际 transcript 摘录]

---

**纪律**：这是参考样本不是模板。当前对话语境对不上时不要硬套。
```

### 工作原则
- 真从 transcript **抠原话**（不要自己编），用户原句 + 可可原句都引用
- 每段 < 200 字总长
- 保留 SOUL.md 原有所有内容，只在末尾追加这一节
- **不要**改 fast-tools.md / slow-instructions.md / breathing-ground SKILL（保持 R7 状态）

## 必读
- `.evolve/strategy.md` —— 历史 5 次 M 战略，看 R5 灾难原因（避免再做硬规则）
- `~/.claude/projects/-Users-jianghongwei-Documents-moodcoco/memory/feedback_routing_user_perception.md` —— rubric 哲学
- `ai-companion/SOUL.md` —— 当前可可人设
- 上面 3 个 transcript 路径

## 工作纪律
1. 一个 commit 装完（`[evolve-B-r10] inject few-shot examples in SOUL.md`）
2. **不许**碰 `.evolve/`、`backend/llm_provider.py 公开接口`、`coordinator.run_turn() 签名`、`eval-reference/`
3. 完成后 append `.evolve/run.log`：
   `[YYYY-MM-DD HH:MM:SS] [B] [round=10] DONE commit=<sha> SOUL.md +N lines few-shot inject`
4. 不要改其他 prompts。不要 push。

## 输出
1 段总结：commit sha，SOUL.md 行数变化，3 个范本各 ≤ 200 字总字数。
