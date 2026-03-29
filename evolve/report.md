# Evolve 进度报告 v2

## 状态：测试中 — 15 个场景批量验证

## 已验证通过的场景（5/15）

| # | 场景 | 情绪类型 | 核心能力 |
|---|------|---------|---------|
| 1 | 吵架急救 | 爆发（委屈、愤怒） | 模式识别→童年连接 |
| 2 | 关系倦怠 | 压抑（麻木、闷） | 觉察"按部就班"下的真实感受 |
| 3 | 反PUA | 愤怒+自我怀疑 | 帮用户看见操控模式 |
| 4 | 已读不回 | 焦虑螺旋 | 3次自我怀疑命中 + 关系空转循环 |
| 5 | 暧昧破冰 | 期待+不确定 | 轻松语气，匹配18岁用户 |

## 批量测试中（10/15）

消息解读、依恋模式测试、关系咨询对话、关系健康度评估、聊天截图解读、关系记忆档案、追女孩子、追男孩子、分手危机、分手恢复

## 最强组合

```
模型: minimax-m2.7 (via OpenRouter)
Thinking: high
USER.md: 预填用户档案
Context: 瘦身（删 TOOLS.md/HEARTBEAT.md）
Skills: 5个 (calm-down, sigh, emotion-journal, relationship-coach, diary)
```

## 关键发现

### Session 泄漏 Bug（已修）
OpenClaw 的 --session-id 不创建新 session，所有调用共享同一个 session。
6轮测试累积 168KB 上下文把 SOUL.md 规则淹没。
修复：adapter.setup() 每次清空 session 文件。

### 10 Methods 测试结果

| 方法 | 影响 |
|------|------|
| 模型选择 (minimax) | **核心变量** |
| thinking high | **核心变量** |
| USER.md 预填 | **核心变量** |
| 满分对话范例 | 微调 (+0.3) |
| Memory 日记 | 模型知道写但 local 模式未执行 |
| Sub-agent | 不需要 |
| Context 瘦身 | 有帮助 |
| SOUL.md 规则 | 约束风格，能力靠 AGENTS.md |
| Skill 精选 | 有 skill 更实用，无更深度 |
| Compaction | 短对话不触发 |

### 评估标准修正
- "看见方法" ≠ AI 给工具（Skill触发）
- "看见方法" = 用户自己找到解决方向

## 新增功能

### diary skill（日记 + 人物档案）
- 融合 emotion-journal + daily-diary-zh + openclaw-diary-core
- 自动识别对话中的人名，创建 people/{名字}.md
- 日记条目用 Markdown 链接指向人物档案
- 结构化六元组：事件-情绪-强度-想法-触发-人物
