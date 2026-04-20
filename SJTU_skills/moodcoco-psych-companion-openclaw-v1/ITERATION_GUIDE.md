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
8. `AGENTS.openclaw.md`
9. `bundle.json`

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

## 升级目标

本轮及后续迭代只允许做四类优化：

1. 路由更稳
2. 边界更清楚
3. 话术更贴近原文
4. 与 `moodcoco` 主智能体更容易整合

## 升级原则

### 1. 一轮只改一类问题

不要一轮同时大改多个 skill。

### 2. 先修高优先级，再修低优先级

固定顺序：

1. `crisis`
2. `calm-body`
3. `listen`
4. `validation`
5. `untangle`
6. `face-decision`
7. `base-communication`

### 3. 不允许越界扩展

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
- 是否漏掉更高优先级 skill
- 是否出现越界行为

### Step 3：归因

问题只归到这几类：

1. 路由错了
2. skill 触发条件不清
3. skill 禁忌不够硬
4. 话术偏离原文
5. 超出首版技能边界

### Step 4：最小改动

只改直接导致失败的那个文件，不扩大改动面。

### Step 5：重跑同一批样本

必须回放同一批样本，不允许换题规避失败。

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
- `AGENTS.openclaw.md` 的优先级

### 3. 风险筛查不够直接

优先检查：

- `crisis`

### 4. 把低优先级技能提前使用

表现：

- 还没接住情绪就开始澄清
- 还没拆清问题就开始决策支持

优先检查：

- `listen` 是否被跳过
- `validation` 是否在需要时缺位
- `untangle` 和 `face-decision` 是否被过早触发

### 5. 把场景层误做成 skill

处理原则：

- 场景是调用说明，不是首版内置 skill

### 6. 把第二阶段模块误并入首版

处理原则：

- 直接回退，保持首版边界

## 给 AI 协作者的任务模板

给 Codex：

> 读取当前 bundle。不要新增技能，不要扩展到第二阶段。只检查首版 7 个技能的路由优先级、文件一致性、越界风险和回归风险。

给 Claude Code：

> 读取失败 transcript 与目标 skill。不要新增技能，不要引入第二阶段模块。只在首版 7 个技能边界内做最小修复，让行为更符合原文定义，并且不要破坏既定优先级。

## 最后一条规则

严格按文档首版执行，比“多做几个看起来有用的技能”更重要。
