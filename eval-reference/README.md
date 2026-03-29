# 评估参考（Eval Reference）

这个目录是一次完整的 AI 对话质量评估记录，可以作为参考但不需要直接使用。

如果要从零开始评估，运行 `/evolve` 即可，它会自动生成新的 `.evolve/` 目录。

## 这里有什么

| 文件 | 说明 |
|------|------|
| `eval.yml` | 5 个评估维度和门槛（看见情绪/原因/模式/方法 + 安全边界，全 9.0） |
| `spec.md` | 15 个测试场景的定义和验收标准 |
| `personas/` | 4 个模拟用户人设（小雨/阿瑶/玉玉/小桔），像小说一样的复杂背景 |
| `test_scripts/` | 15 个场景配置（只有主题和心情，不写死消息） |
| `adapter.py` | 测试适配器：豆包 API 模拟用户 ↔ OpenClaw coco 真实多轮对话 |
| `transcripts/` | 15 个场景的完整对话记录 |
| `10-methods.md` | 10 种提升方法的验证结果 |
| `report.md` | 最终进度报告 |
| `迭代过程复盘.md` | 完整复盘（含 session 泄漏 bug 发现过程） |

## 关键结论

**最强组合**：minimax-m2.7 + thinking high + USER.md 预填

**核心变量只有 3 个**（10 种方法测完后的结论）：
1. 模型选择（minimax-m2.7）
2. thinking level（high）
3. USER.md 预填用户历史

**发现的 bug**：OpenClaw 的 `--session-id` 不创建新 session，多轮测试会累积上下文把 prompt 规则淹没。修复：每次测试前清空 session 文件。
