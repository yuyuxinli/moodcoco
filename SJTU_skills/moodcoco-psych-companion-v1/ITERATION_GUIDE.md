# MoodCoco Skills Iteration Guide

这份文档针对当前首版 bundle，也就是：

- `6` 个陪伴 skills
- `1` 个风险 skill

任何评估和升级都不能越过这个边界。

## 当前允许迭代的文件

1. `skills/base-communication/SKILL.md`
2. `skills/listen/SKILL.md`
3. `skills/untangle/SKILL.md`
4. `skills/validation/SKILL.md`
5. `skills/face-decision/SKILL.md`
6. `skills/calm-body/SKILL.md`
7. `skills/crisis/SKILL.md`
8. `AGENTS.md`
9. `bundle.json`
10. `README.md`
11. `AUTO_EVAL_CHECKLIST.md`

## 当前不允许擅自新增的内容

- `know-myself`
- `see-pattern`
- `relationship-coach`
- `scene-router`

如果评估者认为这些模块未来有价值，只能记为“第二阶段建议”，不并入这版首包。

## 统一优先级

### 路由优先级

1. `crisis`
2. `calm-body`
3. `listen`
4. `validation`
5. `untangle`
6. `face-decision`

### 常驻层

`base-communication` 始终加载，不参与上面的抢占式路由。

## 统一运行时结构

当前首版迭代按四层处理，不要跳层：

1. `safety routing`
   先判 `crisis`，再判 `calm-body`
2. `mode routing`
   在非危机、非必须先稳定时，先判 `fast / slow`
3. `skill routing`
   再在 `listen / validation / untangle / face-decision` 中选主 skill
4. `executor behavior`
   决定当前只做轻承接、轻缩窄，还是进入更完整的多步执行

规则：

- `fast / slow` 是 mode layer，不是新 skill
- `base-communication` 是 always-on layer，不参与 routed skill 竞争
- 若安全未过，不能直接讨论 deeper execution

## 升级目标

本轮及后续迭代只允许做四类优化：

1. 路由更稳
2. 边界更清楚
3. 话术更贴近原文
4. 与 `moodcoco` 主智能体更容易整合

## 升级原则

### 1. 先改 routing / handoff / mode，再改 skill 文案

如果问题可以通过：

- `AGENTS.md`
- `bundle.json`
- `AUTO_EVAL_CHECKLIST.md`

解决，就不要先去大改 skill 文案。

### 2. 一轮只修一条 failure chain

允许同步改同一条 failure chain 相关的：

- routing
- handoff
- mode
- regression checklist

但不要顺手做无证据的大改 prompt。

### 3. 先修高优先级，再修低优先级

固定顺序：

1. `crisis`
2. `calm-body`
3. `listen`
4. `validation`
5. `untangle`
6. `face-decision`
7. `base-communication`

### 4. 不允许越界扩展

如果某个失败样本看起来需要：

- 自我探索
- 跨会话模式识别
- 亲密关系专题框架

当前版本只能把它记为“首版能力边界之外”，不能直接新增技能。

## 推荐的 Claude Code / Codex 分工

### Codex

负责：

- 结构检查
- 路由优先级检查
- 文件一致性
- 回归风险检查
- 判断是否超出首版技能边界

### Claude Code

负责：

- skill 文案改写
- 执行步骤微调
- 让技能行为更贴近原文
- 针对失败 transcript 做最小修复

### 裁判层

负责：

- 对比改前改后 transcript
- 判断是否真的更符合原文
- 判断是否引入越界扩展

## 一轮标准迭代流程

### Step 1：固定评测集

至少覆盖：

- 一般情绪倾诉
- 混乱纠缠
- 自责羞耻
- 两难决策
- 高唤醒/恐慌
- 风险/危机

### Step 2：跑基线

记录：

- 实际触发了哪个 skill
- 实际触发了哪个 action
- 实际走的是 `fast` 还是 `slow`
- 有没有正确进入 handoff / narrowing / safety recheck
- 是否漏掉更高优先级 skill
- 是否出现越界行为

### Step 3：归因

问题只归到这几类：

1. `routing_error`
2. `handoff_error`
3. `mode_missing`
4. `skill_trigger_unclear`
5. `skill_boundary_too_soft`
6. `regression_risk`
7. `scope_violation_risk`
8. `phase_2_not_in_scope`

并且每个问题都要记录：

- 证据文件
- 是否必须本轮修
- 该改哪个文件

### Step 4：最小改动

优先顺序：

1. `AGENTS.md`
2. `bundle.json`
3. `AUTO_EVAL_CHECKLIST.md`
4. `ITERATION_GUIDE.md`
5. 必要时才改对应 `skills/*/SKILL.md`

如果问题只是执行层没有明确规则，不要把它伪装成“多写一点话术”。

### Step 5：重跑同一批样本

必须回放同一批样本，不允许换题规避失败。

建议固定执行 `route replay v2`，至少保留这些字段：

- `expected_skill / actual_skill`
- `expected_mode / actual_mode`
- `expected_action / actual_action`
- `handoff_ok`
- `narrowing_ok`
- `safety_recheck_ok`

也就是说，重跑时至少要看到 `mode / handoff / narrowing / safety_recheck`，而不只看 first skill。

### Step 6：写升级记录

每轮记录：

- 改了哪个文件
- 修的是哪一类问题
- 是否有回归
- 是否仍严格停留在首版 7 个技能内
- 是否破坏了既定优先级

## 常见失败模式

### 1. 过早建议

优先检查：

- `listen`
- `base-communication`

### 2. 高唤醒时仍在深聊

优先检查：

- `calm-body`
- `AGENTS.md` 的优先级
- `mode routing` 是否仍停在 `fast`
- `calm-body` 的退出规则是否清楚

### 3. 风险筛查不够直接

优先检查：

- `crisis`
- `safety routing` 是否硬覆盖
- `crisis` 是否错误继续陪伴式深聊

### 4. 把低优先级技能提前使用

表现：

- 还没接住情绪就开始澄清
- 还没拆清问题就开始决策支持

优先检查：

- `listen` 是否被跳过
- `validation` 是否在需要时缺位
- `untangle` 和 `face-decision` 是否被过早触发
- 是否缺少单步缩窄问题动作

### 4A. 缺少 mode 规则

表现：

- 第一轮就进入高成本深聊
- `calm-body` 或 `face-decision` 反复做太久
- 该轻承接时做成多轮盘问

优先检查：

- `AGENTS.md` 的 `fast / slow` 进入与退出条件
- `bundle.json` 的 `mode_routing`
- `AUTO_EVAL_CHECKLIST.md` 是否有 mode 回归项

### 5. 把场景层误做成 skill

处理原则：

- 场景是调用说明，不是首版内置 skill

### 6. 把第二阶段模块误并入首版

处理原则：

- 直接回退，保持首版边界

## 给 AI 协作者的任务模板

给 Codex：

> 读取当前 bundle。不要新增技能，不要扩展到第二阶段。先检查首版 7 个技能的 safety routing、mode routing、skill routing、handoff、文件一致性、越界风险和回归风险。

给 Claude Code：

> 读取失败 transcript 与目标 skill。不要新增技能，不要引入第二阶段模块。优先修 routing / handoff / mode 缺口；只有在需要时才微调首版 7 个技能文案，让行为更符合原文定义，并且不要破坏既定优先级。

## 最后一条规则

严格按文档首版执行，比“多做几个看起来有用的技能”更重要。
