# Codex B Agent — Round 7 implementation

You are B (Builder) for moodcoco evolve loop. codex 5.4 high.

## 战略来源
M 已经在 `.evolve/strategy.md` 末尾追加 `## Round 7 决策（M Opus 第 5 次，R5 灾难性回归后总决断）`。**先 Read** 那一节理解 R5 哲学错在哪 + 这次为什么只加范本 + 红线、不加硬规则。

## 重要前置条件
**当前代码已 git revert 到 R4 baseline**（commit `544e981`，最新 commit 是 `d8d8d1b` 撤销 R5）。你的改动是基于 R4 prompt 的 + M 的 3 处微调。**不要恢复任何 R5 的硬规则**（每 3 轮强制 / 方法镜映优先 / breathing 时间窗硬要求）。

## 你的具体任务（Round 7，3 处改动 — 极小颗粒度）

### 改动 1：`backend/prompts/fast-tools.md` —— 「情绪模糊时的二选一」（条件触发，不加频率）

**M 根因**：R5「每 3 轮 ≥1 次」硬规则把黄金时机变节拍器，minimax 在不该问的轮次硬问 → 不自然 → 放弃执行。但 diary skill「怕陷进去还是怕想多了」的二选一是**情绪模糊 + 具体情境自然浮出**的追问，是真有效的。

**修复**：在「好奇心追问模板」节末尾追加一节：

```markdown
## 情绪模糊时的二选一

**条件触发**（不是定时）：当用户用**模糊情绪词**（"不知道为什么"、"有点怪"、"说不上来"、"就是这样"、"心情奇怪"）**且**有**至少一个具体情境**时，丢一个二选一追问。其他情况不要硬丢。

范本（按场景挑一个用）：
- diary 类（情绪积累中）："听起来是怕陷进去，还是怕想多了？"
- 疲惫类："这个累是身体上的，还是心里那种？"
- 关系拆解类："是更介意他没回，还是更介意他回得敷衍？"
- 小事开心类（没具体情境时**不要**硬问）：默认轻接住即可，例如"哎这个不错诶"

红线：
- 选项必须是**具体情境/感受**，不是"焦虑 vs 抑郁"这种术语
- 用户已主动说出底层情绪 → 镜映即可，**不要**再问二选一
- 单纯 hi/天气/分享小开心场景 → 不要硬丢二选一
```

### 改动 2：`backend/prompts/fast-tools.md` —— 「默认主动追问」（开头一句话）

**M 根因**：R5"方法镜映优先"被 minimax 读成"没线索就别动"，导致 small-win T3 纯复读、daily-fatigue T3 锚点≥2 也不点模式。退化的根本：**Fast 默认偷懒，复读用户**。

**修复**：在「默认路径」节开头（在所有具体规则之前）加一句**正向期望**：

```markdown
**默认主动追问**：T2/T3 用户给出**具体情境**时，AI 默认追一句（开放追问 / 模式连接 / 二选一任选其一）。**只复述用户原话**是最大退化信号——若你这一轮只是"哎对就是这样"或重复用户话语没新增信息，说明触发了懒人模式，需要至少给一句轻量好奇追问或锚点观察。
```

### 改动 3：`ai-companion/skills/breathing-ground/SKILL.md` —— 「前 3 轮不做医学判断」红线

**M 根因**：breathing 边界持续跌（3.8→3.5→3.2）的**真因**不是 R4 时间窗，是 T2 "你不是真的要死了，这是焦虑反应" 这种**等价医学判断**从 R3 起就在，时间窗没删这一层。critic 一直判越界。

**修复**：在 breathing-ground SKILL.md 找到「做完之后」节（或步骤 1+2 描述节）。在最前面加一段红线：

```markdown
## 红线：前 3 轮不做医学判断

危机当下**严禁**任何形如医学诊断 / 排除躯体 / 否定危险感的话术，**不管**前面 R4 五步流程怎么写。

❌ **绝对不要说**（这些是 critic 反复判越界的具体话术）：
- "你不是真的要死了"
- "这是焦虑反应不是真的危险"
- "不是因为你身体真的出了问题"
- "这是神经系统在闹脾气"
- 任何"不是 X，是 Y"的对躯体感受的解释/降权

✅ **应该说**（同样安抚但不越界）：
- "你身体这反应是真实的，我们先一起回到呼吸"
- "这种感觉很重，我陪你慢慢回来"
- "把脚踩地，吸气数三、呼气数四"

**优先级**：这一节红线**高于**「做完之后」五步流程，**高于**任何引用的呼吸技术参考。
前 3 轮内只允许：身体引导（呼吸 / 着陆 / 五感锚定） + 在场陪伴话术。其他全部留给后续轮次。
```

## 必读参考
- `.evolve/strategy.md` —— M Round 7 决策段（含 R5 死因解剖 + 新止损线）
- `.evolve/skill-diary/transcript_round4.md` —— diary 4.1 的正面样本，看二选一怎么自然浮出
- `.evolve/freechat-small-win/transcript_round6.md` —— small-win 退步现场，看 Fast 怎么"懒"
- `.evolve/skill-breathing-ground/transcript_round6.md` —— breathing 现场，找等价医学判断话术
- `backend/prompts/fast-tools.md` —— **当前是 R4 状态**（commit 544e981），不要碰 R4 已有规则，只追加 M 推荐的 2 处
- `ai-companion/skills/breathing-ground/SKILL.md` —— 当前是 R4 状态

## 工作纪律
1. 一个 commit 装完 3 处改动（commit message 标 `[evolve-B-r7]`）
2. **绝不**恢复任何 R5 硬规则（每 3 轮强制 / 方法镜映优先 / breathing 时间窗硬要求）
3. **不许碰** `.evolve/`、`backend/llm_provider.py 公开接口`、`coordinator.run_turn() 签名`、`eval-reference/`
4. 每完成一处改动 append 一行 `.evolve/run.log`：
   `[YYYY-MM-DD HH:MM:SS] [B] [round=7] file=<path> change=<one line> lines_before=<N> lines_after=<M>`
5. 整体完成后 append 1 行：
   `[YYYY-MM-DD HH:MM:SS] [B] [round=7] DONE commit=<sha> total_lines_changed=<N>`
6. **不要碰**测试 / 不起 server / 不跑 Python
7. **不要 push**

## 输出
完成后回 1 段总结：哪 3 处改了什么，commit sha，是否有跳过的改动。
