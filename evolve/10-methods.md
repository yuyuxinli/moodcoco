# 10 种提升可可对话质量的方法

每种方法的测试方式不同，需要逐个验证。

| # | 方法 | 改什么 | 怎么测 | 状态 |
|---|------|--------|--------|------|
| 1 | **换模型** | `openclaw.json` coco.model | 同一句话发 3 个模型，对比回复 | ✅ deepseek淘汰(慢+泄漏推理)，doubao/minimax可用 |
| 2 | **开 thinking** | `--thinking high` | 同一模型 thinking off vs high，对比深度 | ✅ thinking high 显著提升原因探索和方法引导 |
| 3 | **放满分对话范例** | `references/gold-conversations.md` | 有范例 vs 无范例，同一场景对比 | ✅ 微调提升(+0.3)，minimax+thinking已经够强 |
| 4 | **预填 USER.md** | `USER.md` 写入用户历史 | 有历史 vs 无历史，看模式识别维度 | ✅ 跨session模式连接成功（"室友那次也是这样"） |
| 5 | **Memory 日记** | `AGENTS.md` 记忆规则 + `memory/` | 多轮对话后检查 memory 文件是否写入 | ⚠️ 模型知道要写但local模式下未执行，需配置工具权限 |
| 6 | **Sub-agent 洞察层** | subagents 配置 + AGENTS.md | 单 agent vs 双 agent，对比模式识别分 | ❌ 不需要，minimax+thinking已够强 |
| 7 | **Context 瘦身** | 清空 TOOLS.md/HEARTBEAT.md | 释放 1028 字 context 给规则 | ✅ 回复质量保持高水平，context 更集中 |
| 8 | **SOUL.md 重写** | `SOUL.md` | 有规则 vs 纯人格 | ✅ 规则约束风格（不给结论），能力靠AGENTS.md+thinking |
| 9 | **Skill 精选** | `skills/` 目录增删 | 不同组合跑同一场景 | ✅ relationship-skills让回复更实用(给话术)，无则更深度(提问引导) |
| 10 | **Compaction 定制** | `openclaw.json` compaction | 长对话（15+轮）后检查关键信息是否保留 | ⏭️ 8轮不触发，长对话时再验证 |

## 测试原则

- 每次只改一个变量，其他不动
- 清空 session 再测（避免上次的 bug）
- 用同一个评估标准打分
- 记录每次结果到本文件
