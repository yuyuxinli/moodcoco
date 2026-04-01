# Strategy

## Current Feature
F1: eval_s1 — S1 专属评分标准

## Status: New（首次构建）

## Execution Order
1. F1 eval_s1（评分标准）
2. F2 test-infra（测试脚本）
3. F3 l1-format（格式控制）
4. F4 tool-types（Tool 类型）

## Decision Log

### 2026-04-01 — 新 evolve 任务启动

基于 S1 v1-v9 的 9 轮迭代分析，确认问题是系统性的：
- 评分标准与测试场景不匹配
- 双轨系统互不兼容
- 永久约束未从评分移除
- 确定性评判概率性行为

决策：重建评估框架 + 统一对话链路基础设施。
