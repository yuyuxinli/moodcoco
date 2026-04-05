# Program: 架构改良 — 统一对话链路 + 评估框架修正

基于前 9 轮 S1 迭代的系统性分析，实施架构改良。

## Product Requirements

1. 废弃 MoodAgent 双轨系统，统一走 OpenClaw Gateway 链路
2. 评估框架与测试场景对齐（per-stage 评分标准）
3. 为小程序端提供 JSON 格式输出（content_type）的基础设施
4. Tool 类型约束（枚举替代自由字符串）

## Feature List

- [ ] F1: eval_s1 — S1 专属评分标准
- [ ] F2: test-infra — 测试脚本改进（Turn7 拆分 + 等待改进 + 3 次中位数）
- [ ] F3: l1-format — L1 JSON 格式控制 prompt
- [ ] F4: tool-types — OpenClaw Plugin Tool 类型定义

## Evaluation Criteria

全部 deterministic。详见 eval.yml。

## Technical Constraints

- 双仓库：moodcoco（当前工作区）+ psychologists（/Users/jianghongwei/Documents/psychologists）
- 不改 OpenClaw 源码（response_format 透传是独立 TODO）
- 不启动后端服务（纯文件级别改动）
- Git commit after each agent run

## Agent Rules

- Do not modify program.md
- Do not modify files under .claude/skills/evolve/
- Git commit after each agent run
- F1/F2 在 moodcoco 仓库操作
- F3/F4 在 psychologists 仓库操作
- 参考文档：docs/superpowers/specs/2026-03-31-project-merge-design.md

## Reference

- 架构设计：`docs/superpowers/specs/2026-03-31-project-merge-design.md`
- 旧 eval：`.evolve/archive_s1_v9/eval.yml`
- 旧测试脚本：`.evolve/b_output/run_s1_v9.py`
- AI 行为规范：`ai-companion/AGENTS.md`
