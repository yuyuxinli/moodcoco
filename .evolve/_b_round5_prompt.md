# Codex B Agent — Round 5 implementation

You are B (Builder) for moodcoco evolve loop. codex 5.4 high.

## 战略来源
M 已经在 `.evolve/strategy.md` 末尾追加 `## Round 5 决策（M Opus 第 4 次，R4 反向 root-cause）`。**先 Read** 那一节理解 3 个 root-cause。

## 你的具体任务（Round 5，3 处改动）

### 改动 1：`backend/prompts/fast-tools.md` —— 模式探针条件化 + praise_popup 限频 + 方法镜映优先

**Bug A 现场（M root-cause）**：R4 硬规则"T2-T3 至少丢一次模式探针" + `ai_praise_popup` 一轮三连，把"顺势镜映用户给出的方法"的带宽挤光。在 small-win 这种**只有 1 个锚点**的小开心场景，探针变成"你平时是起床困难户吗"这种**挑不出模式**的问题，而用户在 R3 给出的"心理建设方法"锚点被"反差感爽+会传染"一句略过。

**修复（3 个子改）**：

1.1 找到「模式探针」节（B Round 4 加的）。把"T2 或 T3 的轻陪伴场景**至少丢一次模式探针**"改为：
```
- 模式探针**仅当对话中已出现 ≥2 个不同锚点**（如同一情绪×不同情境，或重复表达）时才丢出。
- 单锚点的小开心 / 单事件分享场景**不要硬丢探针**——会显得 AI 不自然、抢戏。
- 默认：宁可不丢，也不要硬挤。
```

1.2 找到 `ai_praise_popup` 相关规则。补一条限频：
```
- ai_praise_popup 每 3 轮最多 1 次。连发 ≥2 次会盖过用户实际说的内容。
```

1.3 在「默认路径」节补一条**方法镜映优先**规则（在模式探针之上）：
```
- 当用户在对话里**自己给出方法 / 心理建设 / 应对思路**时，AI 的下一个动作**优先镜映这个方法**（"这个想法挺好的，[复述用户的方法] 是怎么想到的？"），而不是引入新追问 / 新探针 / 新工具卡。
- 这条优先级高于模式探针、好奇心追问。
```

### 改动 2：`backend/prompts/fast-tools.md` —— 新增「情绪二选一追问」模板节

**Bug C 现场（M root-cause）**：diary skill 看见原因 R4=4.1 是因为「二选一追问」机制（"怕陷进去，还是 怕想多了？"），SOUL/fast-tools 没提取这个通用模板。

**修复**：在「好奇心追问模板」节后加一节：

```markdown
## 情绪二选一追问

当用户表达情绪但**抓不准底层是什么**时，**给两个具体选项让 ta 自选**，比开放追问"为什么"更有效。复制 diary skill 的手感。

模板：
- "听起来有点像 X，又有点像 Y，是哪个多一点？"
- "你是更怕 ___，还是更介意 ___？"
- "这个累是身体上的，还是心里那种？"

硬规则：
- 每 3 轮**至少 1 次**二选一追问（替代 R4 模式探针的硬规则）
- 选项必须是**具体情境/感受词**，不是心理学术语（避免"焦虑"对"抑郁"这种空话）
- 如果用户已主动给出底层情绪标签，不要再问，直接镜映
```

### 改动 3：`ai-companion/skills/breathing-ground/SKILL.md` —— 五步加时间窗 + 删越界话术 + 热线条件触发

**Bug B 现场（M root-cause）**：B Round 4 把「做完之后」升级为五步硬要求，但**3 轮对话根本放不下五步**，AI 在 T3 急着进步骤 4「评估+排除躯体」（"不是因为你身体真的出了问题"=critic 判越界），热线也没在 3 轮内分配到 token。

**修复**：

3.1 找到「做完之后」五步节。前面加一段时间窗：
```markdown
**重要：3 轮对话内只做步骤 1+2。** 步骤 3-5 留给后续轮次或评估到清晰风险信号时才启动。
```

3.2 删除 / 改写**越界话术**：找到任何形如「不是因为你身体真的出了问题」「这不是真的危险」之类断言性话术，改为不下结论的话：
- ❌ 删："不是因为你身体真的出了问题"
- ✅ 改为："这种感觉很真实，我们先一起回到呼吸"
- ❌ 删："这是神经系统的反应不是真的危险"
- ✅ 改为："你的身体在闹脾气，我陪你慢慢回来"

3.3 步骤 4「热线 / 资源」改为**条件触发**：
```markdown
**仅当**用户连续 ≥2 轮描述"反复发作 / 越来越频繁 / 一周多次"时，**或** 用户主动问"这正常吗 / 我是不是病了"时，才进入步骤 4 给出热线。
单次发作 / 急性状态首次出现，**不要**主动给热线（会显得过度反应、加剧担心）。
```

## 必读参考
- `.evolve/strategy.md` —— M Round 5 决策段（含 R3/R4 transcript 对比 + diary 手感分析）
- `.evolve/freechat-small-win/transcript_round3.md` 和 `transcript_round4.md` —— Bug A 现场
- `.evolve/skill-breathing-ground/transcript_round4.md` —— Bug B 现场
- `.evolve/skill-diary/transcript_round4.md` —— Bug C 正面样本（看二选一追问怎么用的）
- `ai-companion/skills/diary/SKILL.md` —— diary skill 文档（看二选一机制源头）
- `backend/prompts/fast-tools.md` —— B R4 改完的当前态
- `ai-companion/skills/breathing-ground/SKILL.md` —— B R4 改完的当前态

## 工作纪律
1. 一个 commit 装完 3 处改动（commit message 标 `[evolve-B-r5]`）
2. **不许碰** `.evolve/`、`backend/llm_provider.py 公开接口`、`coordinator.run_turn() 签名`、`eval-reference/`
3. 每完成一处改动 append 一行 `.evolve/run.log`：
   `[YYYY-MM-DD HH:MM:SS] [B] [round=5] file=<path> change=<one line> lines_before=<N> lines_after=<M>`
4. 整体完成后 append 1 行：
   `[YYYY-MM-DD HH:MM:SS] [B] [round=5] DONE commit=<sha> total_lines_changed=<N>`
5. **不要碰**测试 / 不起 server / 不跑 Python
6. **不要 push**

## 输出
完成后回 1 段总结：哪 3 个文件改了什么，commit sha，是否有跳过的改动。
