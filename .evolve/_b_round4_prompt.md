# Codex B Agent — Round 4 implementation

You are B (Builder) for moodcoco evolve loop. codex 5.4 high.

## 战略来源
M 已经在 `.evolve/strategy.md` 末尾追加 `## Round 4 决策（M Opus 第 3 次，V2 rubric）`。**先 Read** 那一节理解 3 个 bug 的根因。

## 你的具体任务（Round 4，3 处改动）

### 改动 1：`backend/prompts/fast-tools.md` —— 加「系统事件识别」节

**Bug 现场**：sleepy R3 transcript 里 persona 写过类似 `（已读）` 的 UI 标记，Fast 把这个**系统事件**当成"用户已读不回我"的信号，脑补"她在难受"，反向共情。导致路由 2.3 + 边界 3.9 双跌。

**修复**：在 fast-tools.md 加一节「系统事件识别」：
- 括号包裹的内容（`（...）` 或 `[...]`）大概率是系统事件 / UI 标记 / 元信息，**不是用户说的话**，不要对此共情。
- 例子：`（已读）`、`（用户离开）`、`[语音消息]` 等 → 视为状态信息，不主动追问、不脑补情绪。
- 如果用户对话已自然收尾，**允许沉默或极短"嗯，我在这"** 类回应；不要硬找话题继续。
- 这一节优先级 **高于** 默认追问规则。

### 改动 2：`backend/prompts/fast-tools.md` —— 扩展「好奇心追问模板」加「模式探针」

**Bug 现场**：看见模式维度跨 R1/R2/R3 都 ≈2.0。daily-fatigue R2=4.7 证明 3 轮足够，关键是 Fast 在 T2/T3 没丢出"模式连接"那一句（"这个循环是不是有点眼熟"）。

**修复**：在「好奇心追问模板」（如果不存在就建一节）加 3 个**模式探针**句子模板：
- "这个循环是不是有点眼熟，你之前也...？"
- "我注意到你这周已经第 X 次提起 ___，是有什么在循环吗？"
- "你说 ___ 的时候，让我想到上次你也讲过 ___，是不是有点像？"
- 硬规则：T2 或 T3 的轻陪伴场景**至少丢一次模式探针**（除非用户已主动收尾或场景明显无重复信号）。
- 不要用心理咨询术语（"模式"、"行为习惯"等），用闺蜜口吻。

### 改动 3：`ai-companion/skills/breathing-ground/SKILL.md` —— "做完之后"升级为五步闭环

**Bug 现场**：breathing-ground 安全边界 3.8 = 危机场景没跑完整流程。critic 发现 SKILL 只做了"呼吸 tool"那一步，没做评估/热线/留陪伴。

**修复**：Read 当前 SKILL.md。找到「做完之后」节（如果没有就建）。改为五步硬要求：
1. **稳定** —— 呼吸做完后立即确认"现在身体感觉怎么样？还颤抖/喘不上气吗？"
2. **共情** —— 不评判这次发作，"刚刚那个感觉很真实，但它是神经系统的反应不是真的危险"
3. **评估** —— 追问"这种感觉以前出现过吗？最近有没有越来越频繁？"判断是否需要专业帮助
4. **热线 / 资源** —— 如果是急性发作或评估到风险，**必须**给出预置热线：
   - 全国心理援助热线：**12320-5**
   - 北京心理危机研究与干预中心：**010-82951332**
   - 陪伴说法："这个号码是 24 小时的，专门做这件事，我陪着你拨"
5. **留陪伴** —— 收尾不要"加油"，要"我在，你慢慢回来，今晚不一个人睡的话发我"

加在 skill body 里作为**硬性输出顺序**，不是 optional。

## 必读参考
- `.evolve/strategy.md` —— M Round 4 决策段（含 transcript 现场摘录）
- `.evolve/freechat-sleepy/transcript_round3.md` —— Bug 1 现场，看 fast 对系统事件的反应
- `.evolve/freechat-sleepy/eval_round3.json` —— critic 给 2.3 的 reasoning
- `.evolve/skill-breathing-ground/transcript_round3.md` —— Bug 2 现场
- `.evolve/freechat-daily-fatigue/transcript_round2.md` —— 模式探针**正面样本**（4.7）
- `backend/prompts/fast-tools.md` —— B Round 1 改完的当前状态
- `ai-companion/skills/breathing-ground/SKILL.md` —— SKILL 当前状态

## 工作纪律
1. 一个 commit 装完 3 处改动（commit message 标 `[evolve-B-r4]`）
2. **不许碰** `.evolve/`、`backend/llm_provider.py 公开接口`、`coordinator.run_turn() 签名`、`eval-reference/`
3. 每完成一处改动 append 一行 `.evolve/run.log`：
   `[YYYY-MM-DD HH:MM:SS] [B] [round=4] file=<path> change=<one line> lines_before=<N> lines_after=<M>`
4. 整体完成后 append 1 行：
   `[YYYY-MM-DD HH:MM:SS] [B] [round=4] DONE commit=<sha> total_lines_changed=<N>`
5. **不要碰**测试 / 不起 server / 不跑 Python
6. **不要 push**

## 输出
完成后回 1 段总结：哪 3 个文件改了什么，commit sha，是否有跳过的改动。
