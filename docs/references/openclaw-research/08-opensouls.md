# 08 - OpenSouls Soul Engine 调研报告

> 调研目标：分析 Soul Engine 的核心架构模式，评估其状态机 + 函数式记忆设计对心情可可（moodcoco）的移植价值。
> 
> 源码位置：`/Users/jianghongwei/Documents/GitHub/openclaw-research/opensouls/`

---

## 1. Soul Engine 核心架构

### 1.1 三大抽象

Soul Engine 的设计哲学是"LLM 是前额叶，引擎补全心智的其他部分"。围绕三个核心抽象构建：

| 抽象 | 类比 | 实现 |
|------|------|------|
| **WorkingMemory** | 工作记忆（前额叶缓冲区） | 不可变 Memory 数组，每次操作返回新快照 |
| **cognitiveStep** | 单次认知操作（一个"念头"） | 纯函数：`(WorkingMemory, instruction) → [newMemory, typedResult]` |
| **MentalProcess** | 行为模式/心理状态 | 状态机节点：`(workingMemory) → workingMemory | [workingMemory, nextProcess]` |

### 1.2 WorkingMemory：不可变记忆快照

```typescript
// 核心操作 — 全部返回新实例，原实例不变
workingMemory.withMemory(newMem)        // 追加一条记忆
workingMemory.withRegion("core", mem)   // 设置命名区域（系统人设、摘要等）
workingMemory.slice(start, end)         // 截取
workingMemory.concat(other)             // 拼接
workingMemory.withoutRegions("default") // 移除指定区域
workingMemory.withOnlyRegions("default")// 只保留指定区域
```

**关键设计**：
- **Region 系统**：记忆被分为命名区域（`core` = 人设、`summary` = 摘要、`clue-notes` = 线索、`default` = 对话），可独立操作。`withRegionalOrder("core", "summary", "default")` 控制拼接顺序。
- **clone() 机制**：每次变换都通过 `clone()` 创建新实例。`WorkingMemoryWithTracking` 子类在 clone 时自动注入追踪元数据和安全校验（`harden()` 冻结对象）。
- **Processor 注入**：WorkingMemory 绑定一个 Processor（OpenAI/Anthropic/OpenRouter），cognitiveStep 通过它调用 LLM。

### 1.3 cognitiveStep：类型化的认知操作

通过 `createCognitiveStep` 工厂函数创建。每个 step 定义三件事：

```typescript
createCognitiveStep((instructions) => ({
  command: (wm) => ({ role, content }),  // 1. 注入到 WorkingMemory 的 prompt
  schema?: z.object({...}),              // 2. 结构化输出 schema（可选）
  postProcess: (wm, response) => [newMem, extracted]  // 3. 后处理
}))
```

**内置 cognitiveStep 库**：

| Step | 用途 | 输出类型 |
|------|------|---------|
| `internalMonologue` | 内心独白，模拟思考 | `string`（思考内容） |
| `externalDialog` | 外部对话，生成回复 | `string`（对话内容） |
| `mentalQuery` | 是非判断，评估一个陈述 | `boolean` |
| `decision` | 多选一决策 | `string`（选项值） |
| `brainstorm` | 头脑风暴，生成列表 | `string[]` |
| `instruction` | 通用指令 | `string` |
| `summarize` | 摘要 | `string` |
| `conversationNotes` | 对话笔记 | `string` |
| `userNotes` | 用户侧笔记 | `string` |

**核心洞察**：cognitiveStep 不是"调用 LLM"——它是"一次认知操作"。每次调用都会：
1. 把指令追加到 WorkingMemory
2. 调用 LLM 获取结果
3. 把结果也追加到 WorkingMemory（作为 Assistant 消息）
4. 返回 `[新的 WorkingMemory, 提取的类型化结果]`

这意味着认知链条天然保留在 WorkingMemory 中：思考 → 对话 → 判断 → 决策，每一步都在上一步的语境里进行。

### 1.4 MentalProcess：状态机

MentalProcess 是一个异步函数，接收当前 WorkingMemory，返回：
- 只返回 `workingMemory`：停留在当前状态，等待下一个 perception
- 返回 `[workingMemory, nextProcess]`：切换到新状态
- 返回 `[workingMemory, nextProcess, { executeNow: true }]`：立即执行新状态（不等 perception）
- 返回 `[workingMemory, nextProcess, { params: {...} }]`：带参数切换

**Hugo 猜音乐家示例的状态机**：

```
initialProcess → introduction → guessing ⇄ frustration
                                    ↑          ↓
                                    └──────────┘
```

```typescript
// introduction.ts — 介绍后切换到猜测
return [nextMemory, guessingProcess, { executeNow: false }]

// guessing.ts — 猜了 5 次切换到挫败
if (attempts.current >= 5) {
  return [nextMemory, frustrationProcess, { executeNow: true }]
}
return nextMemory  // 否则留在 guessing

// frustration.ts — 求助后回到猜测
return [nextMemory, guessingProcess]
```

### 1.5 Subprocess：后台认知进程

Subprocess 是在主线程（MentalProcess）执行完之后自动运行的后台过程。典型用途：

- **summarizeConversation**：当 `memories.length > 9` 时压缩对话，保留 region("summary") + 最近 5 条
- **learnsAboutTheMusician**：从对话中提取线索笔记，写入 region("clue-notes")

Subprocess 不控制状态切换——它只修改 WorkingMemory 的内容。

### 1.6 MemoryIntegrator：感知预处理

每当收到外部 perception（用户消息）时，先经过 memoryIntegrator 处理：
1. 注入 core region（人设 markdown）
2. 将 perception 格式化为 User 消息
3. 可选：改变 currentProcess

这是 WorkingMemory 和外部世界的接口层。

### 1.7 useSoulMemory / useProcessMemory：持久化 Hook

```typescript
// useSoulMemory — 跨 process 持久化（类似 React useState）
const attempts = useSoulMemory("guessAttempts", 0)
attempts.current += 1

// useProcessMemory — 单 process 内持久化
const didPick = useProcessMemory("")
didPick.current = "Beatles"
```

实现上是通过 `ProcessMemoryContainer` 维护一个 ref 数组，每次 process 执行前重置索引，按调用顺序恢复/创建。

---

## 2. 状态机实现：对话阶段切换机制详解

### 2.1 执行循环

```
外部事件（用户消息）
    ↓
SubroutineRunner.executeMainThread()
    ↓
memoryIntegrator(perception) → 更新 WorkingMemory
    ↓
internalMainThread() → 执行当前 MentalProcess
    ↓
MentalProcess 返回值分析：
  ├─ 只返回 WorkingMemory → 等下一个 perception
  ├─ [wm, nextProcess] → moveToProcess(next) → 等下一个 perception
  └─ [wm, nextProcess, {executeNow}] → moveToProcess(next) → 递归 internalMainThread()
    ↓
执行 subprocesses → 压缩/学习/笔记
    ↓
持久化状态
```

### 2.2 moveToProcess 做了什么

```typescript
private moveToProcess(processName: string, params?: any) {
  this.state.currentProcess = processName
  this.state.currentMentalProcessInvocationCount = 0
  this.state.currentProcessData = params || {}
  this.currentUseProcessMemory.resetRuntime()  // 清空 process 级记忆
}
```

切换 process 时：
- 重置调用计数器
- 重置 processMemory（因为新 process 有自己的记忆）
- 保留 soulMemory（跨 process 持久化的不受影响）

### 2.3 递归深度保护

```typescript
if (loopCount > 10) {
  throw new Error("too much recursion")
}
```

`executeNow: true` 会递归调用 `internalMainThread`，最多 10 层。这防止两个 process 互相 ping-pong。

### 2.4 状态感知的决策

MentalProcess 内部可以用 cognitiveStep 做决策：

```typescript
// mentalQuery: 布尔判断
const [, isFrustrated] = await mentalQuery(wm, "Hugo已经猜了3次以上没有确认")
if (isFrustrated) { /* 切换状态 */ }

// decision: 多选一
const [, choice] = await decision(wm, { choices: ["continue", "give_up"], description: "..." })

// invocationCount: 计数器
const { invocationCount } = useProcessManager()
if (invocationCount === 0) { /* 首次执行 */ }

// useProcessMemory: 持久计数
const attempts = useSoulMemory("attempts", 0)
if (attempts.current >= 5) { /* 切换 */ }
```

---

## 3. 函数式记忆设计的优势分析

### 3.1 不可变性带来的好处

| 优势 | 说明 |
|------|------|
| **可回溯调试** | 每个 cognitiveStep 前后的 WorkingMemory 都是独立快照，可以精确看到"这步思考时 AI 看到了什么" |
| **分支安全** | 可以在不影响主线的情况下做"试探性思考"：`const [probe, result] = await mentalQuery(wm, "...")`，probe 不影响原 wm |
| **并发安全** | 多个 subprocess 可以同时读取同一个 WorkingMemory 快照，互不干扰 |
| **状态恢复** | 整个对话状态可以序列化为 `StateCommit`，支持 revert 到历史版本 |
| **组合性** | Region 系统允许独立操作记忆的不同部分：压缩 default 区域不影响 core 区域 |

### 3.2 Region 系统的精妙设计

```typescript
workingMemory = workingMemory
  .withRegion("core", { content: soul.staticMemories.core })     // 人设不变
  .withRegion("summary", { content: conversationSummary })        // 摘要可替换
  .withRegionalOrder("core", "clue-notes", "summary", "default") // 控制顺序
```

实际发给 LLM 的消息按 region 顺序拼接：
```
[core] 你是 Hugo，一个曼彻斯特 DJ...
[clue-notes] 已知线索：90年代、英国、摇滚...
[summary] 之前的对话：Hugo 问了3个问题...
[default] 用户: "不是 Oasis"
[default] Hugo: "那是不是 Radiohead？"
[default] 用户: "接近了但不对"
```

这比"把所有东西塞进一个 system prompt"精确得多。每个区域可以独立更新、独立压缩。

### 3.3 与 moodcoco 当前方案的对比

| 维度 | Soul Engine | moodcoco 当前 |
|------|-------------|--------------|
| 记忆管理 | 不可变 WorkingMemory + Region | OpenClaw compaction + memU bridge |
| 上下文组装 | 代码级精确控制每条消息 | AGENTS.md prompt + OpenClaw bootstrapMaxChars |
| 思考链 | cognitiveStep 链天然累积 | 模型 thinking 模式（黑盒） |
| 持久化 | useProcessMemory/useSoulMemory | USER.md + memU |

---

## 4. 可移植性评估：Soul Engine → OpenClaw

### 4.1 架构差异

| 维度 | Soul Engine | OpenClaw |
|------|-------------|---------|
| 运行时 | 自建 TypeScript 引擎 + SES 沙箱 | 通用 Agent 框架，AGENTS.md + Skills + Tools |
| 状态管理 | 代码级状态机（return [wm, nextProcess]） | Prompt 级指令（"检测到X信号 → 加载Y skill"） |
| 记忆 | 不可变 WorkingMemory，代码操作 | 文件系统 + compaction，框架管理 |
| LLM 调用 | 显式链式调用（await step1 → await step2） | 单次调用，模型自主决策 |
| 扩展 | cognitiveStep 库 + subprocess | Skills (SKILL.md) + Tools (exec) |

### 4.2 可移植的设计模式

**A. 状态机思维 → Skill 路由表（已有雏形）**

moodcoco 的 13 Skill 路由表本质上就是一个状态机。但当前是 prompt 级描述，依赖模型判断：

```markdown
# 当前 moodcoco 方式（AGENTS.md prompt）
| P0 | crisis | P0 关键词 | read("skills/crisis/SKILL.md") |
| P1 | calm-body | 躯体症状 | read("skills/calm-body/SKILL.md") |
```

Soul Engine 的方式是代码级切换：
```typescript
if (hasCrisisSignal) return [wm, crisisProcess]
if (hasSomaticSymptom) return [wm, calmBodyProcess]
```

**建议**：当前 prompt 路由方式在 OpenClaw 框架下是合理的。不需要移植代码级状态机，因为 OpenClaw 没有这个运行时。但可以借鉴的是：

1. **状态命名更显式**：在 AGENTS.md 中明确标注"当前处于哪个 Skill 状态"，而不是每次都重新判断
2. **退出条件显式化**：每个 Skill 应该定义清晰的退出条件和"下一个状态"

**B. cognitiveStep 分离 → 可直接移植为 prompt 策略**

Soul Engine 的 `internalMonologue` → `externalDialog` 链条启发了一个关键模式：

```
先想（internalMonologue）→ 再说（externalDialog）
```

这在 OpenClaw 中可以通过 thinking mode 实现（moodcoco 已经在用 `thinking: high`），但 Soul Engine 的做法更可控——thinking 的结果会追加到 WorkingMemory，下一步能看到。而 OpenClaw 的 thinking 是黑盒。

**建议**：在关键判断点（如情绪置信度判断、模式呈现时机判断）使用显式的 self-reflection prompt，而不是完全依赖 thinking mode。

**C. Region 系统 → 可映射到 OpenClaw 的文件 + compaction**

| Soul Engine Region | OpenClaw 对应物 |
|-------------------|----------------|
| `core` | AGENTS.md + SOUL.md（bootstrap 阶段加载） |
| `summary` | compaction 配置 |
| `clue-notes` / 自定义 | USER.md 的结构化字段 + memU |
| `default` | 对话消息流 |

**当前差距**：OpenClaw 的 compaction 是全局的，不能像 Region 系统那样精确控制"压缩对话区但保留人设区"。moodcoco 的 compaction 配置已经在做类似的事（"压缩时必须保留用户的反复情绪模式、核心困扰关键词..."），但粒度不如 Region。

**建议**：这个差距在 OpenClaw 框架内无法完全弥合。但可以通过更精确的 compaction 指令和 USER.md 结构化来逼近。

**D. useProcessMemory → Skill 内状态追踪**

Soul Engine 的 `useProcessMemory` 解决了"Skill 执行到一半，用户中断，下次回来能继续"的问题。moodcoco 当前没有这个机制——每次 Skill 执行都是无状态的。

**建议**：在 USER.md 中增加一个 `skill_state` 字段，记录当前正在执行的 Skill 和进度。例如：

```markdown
## 当前 Skill 状态
- active_skill: see-pattern
- progress: stage_3_of_7
- context: 已呈现"讨好模式"，等待用户反应
```

### 4.3 不建议移植的部分

| 模式 | 不移植原因 |
|------|-----------|
| SES 沙箱 | OpenClaw 自身已有沙箱，不需要 |
| 显式 LLM 链式调用 | OpenClaw 是单次调用模式，链式调用需要自建运行时 |
| WorkingMemory 不可变数据结构 | 需要代码运行时，prompt-only 架构无法实现 |
| SubroutineRunner 事件循环 | 这是引擎级别的，OpenClaw 有自己的事件循环 |

---

## 5. 四步框架 vs MentalProcess 异同

### 5.1 概念映射

| moodcoco 四步框架 | Soul Engine MentalProcess | 类比 |
|-------------------|--------------------------|------|
| 看见情绪 | introduction（接触、建立语境） | 都是"先接住" |
| 看见原因 | guessing（深入探索、提问） | 都是"引导发现" |
| 看见模式 | frustration（模式识别、挫败处理） | 都是"识别重复" |
| 看见方法 | 无直接对应（Soul Engine 偏娱乐） | moodcoco 特有 |

### 5.2 关键差异

**A. 切换触发机制**

- Soul Engine：代码硬编码条件（`attempts >= 5`）或 LLM 判断（`mentalQuery`）
- moodcoco：完全依赖 LLM 在 prompt 指令下的判断（"先接住，再命名"）

**B. 四步不是线性状态机**

moodcoco 的四步框架（接住 → 陪伴 → 引导 → 见证）更像是一个**渐进式协议**而不是状态机：
- 不强制按顺序（"一次对话不需要走完四步"）
- 可以停留在任何步骤
- 有回退机制（情绪不稳定时回到 listen）
- 深夜模式直接截断到第一步

而 Soul Engine 的 MentalProcess 是严格的状态机——你要么在 `guessing`，要么在 `frustration`，不存在"渐进"。

**C. 情绪安全层**

moodcoco 有 Soul Engine 完全没有的安全机制：
- P0/P1 危机检测
- E-branch 情绪淹没保护
- 模式呈现频率限制
- 深夜模式截断

这些在 Soul Engine 中没有对应物，因为 Soul Engine 的设计目标是"有趣的角色扮演"而不是"安全的情绪陪伴"。

### 5.3 可借鉴之处

**从 Soul Engine 借鉴到四步框架**：

1. **invocationCount 模式**：记录当前步骤内的交互轮次，用于判断"是否该推进到下一步"。当前 moodcoco 完全靠模型感觉。
   ```
   看见情绪阶段，如果已经3轮用户都在重复同一情绪，可以推进到看见原因
   ```

2. **mentalQuery 模式**：在推进前做显式的条件检查，而不是模糊判断。
   ```
   在进入"看见模式"之前，先做一个 mentalQuery：
   "用户的情绪是否已经稳定？（≥3个稳定信号）"
   ```

3. **subprocess 模式**：四步框架的每一步都应该有后台任务——在主对话进行时，后台更新 USER.md 的情绪记录、模式笔记。当前 moodcoco 只在告别时写入。

---

## 6. 核心结论与建议

### 6.1 Soul Engine 最有价值的洞察

1. **"先想再说"模式**（internalMonologue → externalDialog）：让 AI 先形成内部想法，再转化为外部表达。这比直接让模型回复多了一层"认知过滤"。

2. **Region 化记忆管理**：不同类型的信息（人设、摘要、线索、对话）应该被独立管理、独立压缩。

3. **显式状态追踪**：用 `useSoulMemory` 追踪跨轮次的状态（如尝试次数、已呈现的模式），而不是让模型自己记。

4. **subprocess 后台学习**：主对话之外运行后台认知过程，持续从对话中提取结构化知识。

### 6.2 对 moodcoco 的具体建议

| 优先级 | 建议 | 实现方式 |
|--------|------|---------|
| P0 | 在 USER.md 增加 `skill_state` 字段 | 记录当前 Skill 和进度，支持跨会话恢复 |
| P0 | 在关键 Skill 中增加显式进度检查 | 借鉴 mentalQuery，在 SKILL.md 中要求模型先判断再行动 |
| P1 | 优化 compaction 为 region 化 | 在 compaction 配置中区分"必须保留"和"可以压缩"的内容类型 |
| P1 | 增加 invocationCount 等价机制 | 在 USER.md 的 skill_state 中记录当前步骤的轮次数 |
| P2 | 考虑 subprocess 等价物 | 用 Heartbeat 触发后台更新（如定期整理 memU 中的模式笔记） |

### 6.3 不需要做的事

- 不需要构建代码级状态机运行时——OpenClaw 的 prompt 级路由足够
- 不需要实现不可变 WorkingMemory——OpenClaw 的 compaction 机制已经在做类似的事
- 不需要移植 SES 沙箱——安全隔离已由 OpenClaw 框架提供
- 不需要实现 cognitiveStep 链——`thinking: high` + 好的 prompt 结构可以达到 80% 的效果

---

## 附录：关键源码索引

| 文件 | 内容 |
|------|------|
| `packages/soul-engine-cloud/src/subroutineRunner.ts` | 核心执行循环、状态切换、主线程逻辑 |
| `packages/soul-engine-cloud/src/subroutineState.ts` | 状态数据结构定义 |
| `packages/soul-engine-cloud/src/code/soulCompartment.ts` | SES 沙箱、Blueprint 定义 |
| `packages/soul-engine-cloud/src/code/soulEngineProcessor.ts` | WorkingMemory 包装、LLM 调用 |
| `packages/soul-engine-cloud/src/useProcessMemory.ts` | 持久化 Hook 实现 |
| `library/src/cognitiveSteps/` | 内置 cognitiveStep 库 |
| `library/src/subprocesses/summarizeConversation.ts` | 对话压缩 subprocess |
| `souls/examples/hugo-guesses-rockstars/` | 最完整的示例：三状态机 + subprocess |
| `souls/examples/example-twenty-questions/` | 带参数传递的状态切换示例 |
| `plans/rivet-actors-migration.md` | 架构迁移计划（Actor 模型方向） |
