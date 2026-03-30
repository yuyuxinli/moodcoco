# 心情可可 · 实现计划 V2（Feature 精修）

*Version: 2.0 | 2026-03-30*

> V1 搭了骨架（7 步基础设施），V2 逐 Feature 填血肉。
> 每个 Feature 的完整设计在 `docs/product/product-experience-design.md` 对应章节。
> B agent 直接读 spec 对应行范围实现，不需要中间文档。

---

## 评估标准

### 维度定义

| 维度 | 类型 | 门槛 | 说明 |
|------|------|------|------|
| spec_completeness | llm-judged | 9.0 | 功能完善 + 与设计文档一致 |
| architecture | llm-judged | 9.0 | 代码设计合理 + 引用完整 + 跨功能一致 |
| test_coverage | llm-judged | 9.0 | 测试驱动，OpenClaw 测试覆盖充分 |
| openclaw_test | deterministic | 10.0 | 自动化对话回测全通过 |

### 评分细则

**spec_completeness**

| 分数 | 定义 |
|------|------|
| 10 | spec 每个节点、规则、分支、边缘 case 都实现且经 OpenClaw 验证通过 |
| 9 | 主线 + 所有分支实现，仅缺极少边缘细节（≤2 处） |
| 8 | 主线 + 主要分支全部实现，无功能性缺失，覆盖 ≥90% |
| 7 | 主线完整，但 ≥3 个分支路径缺失或与 spec 不一致 |
| 6 | 主线有断点或核心功能与 spec 偏离 |

**architecture**

| 分数 | 定义 |
|------|------|
| 10 | 零冗余零重复，跨功能数据管道全通，类型完整，ruff/pyright 零报错 |
| 9 | 架构清晰无冗余，引用 100% 正确，极少 lint 问题 |
| 8 | 架构合理，无重复逻辑，引用正确，跨功能一致（≤1 处小问题） |
| 7 | 有可见冗余或 2-3 处引用不一致 |
| 6 | 架构问题影响功能 |

**test_coverage**

| 分数 | 定义 |
|------|------|
| 10 | 每个功能路径有 OpenClaw 测试（正向 + 反向 + 边缘），含多轮对话场景 |
| 9 | 主要路径 + 反向全覆盖，至少 1 个多轮深度测试 |
| 8 | 主要路径全覆盖（正向 + 反向），每个 Skill 至少 3 个测试场景 |
| 7 | 有测试但只覆盖正向，无反向/安全边界测试 |
| 6 | 测试覆盖不足一半 |

### 测试方法

- **快速测试**：`openclaw agent --agent coco --local --session-id <id> -m "<msg>" --json`
- **多轮测试**：同一 session-id 连续发消息，验证跨轮行为
- **测试隔离**：每个测试场景独立 session-id，测试前 `openclaw sessions cleanup --enforce`
- **测试驱动**：先写测试场景，再实现功能（/superpowers:test-driven-development）

---

## 执行顺序

按文档顺序 F01→F11。每个 Feature 独立执行：读 spec → TDD（先写测试）→ 实现 → OpenClaw 验证。

| # | Feature | Spec 行范围 | 核心差距 | 工作量 |
|---|---------|------------|---------|--------|
| 1 | F01 记忆体系 | 13-788 | 脚本 CLI 接口不符 spec、USER.md 缺字段、辅助目录不存在 | 中 |
| 2 | F02 交互系统 | 789-1485 | Canvas 卡片 B-E 缺失、diary Poll P2 未实现、交互决策树不统一 | 中 |
| 3 | F03 Skill 体系 | 1486-2174 | 各 Skill 缺 Canvas/图片集成指令、里程碑触发无入口、旧文档引用未清理 | 中 |
| 4 | F04 首次相遇 | 2175-2775 | 4 条分支路径细节不完整、Streaming 配置未体现 | 小 |
| 5 | F05 情绪事件 | 2776-3701 | 消息缓冲策略缺失、情绪稳定信号表缺失、Canvas 模式对比卡缺失 | 中 |
| 6 | F06 日常陪伴 | 3702-4763 | Cron 自适应调度状态机缺失（大）、偏好 schema 未统一、weekly_review 不读 check-in 数据 | 大 |
| 7 | F07 模式觉察 | 4764-5699 | Canvas 模式对比卡/成长轨迹卡 HTML 缺失 | 中 |
| 8 | F08 告别 | 5700-6554 | delete_person 不清理 pending/capsule（P0 bug）、Canvas 告别卡缺失 | 中 |
| 9 | F09 基础设施绑定 | 6555-7072 | weekly_review.py 缺 --memory-dir 参数、Canvas 模板系列整合验证 | 小 |
| 10 | F10 旅程流转 | 7073-7503 | cross_week_pattern 硬编码 False（P0 bug）、缓存机制未实现 | 中 |
| 11 | F11 边缘场景 | 7504-7907 | 长期用户演化规则缺失、prompt 级微调 | 小 |

---

## B agent 上下文注入方式

每个 Feature 的 B agent 收到：

```
1. Spec: product-experience-design.md:<start>-<end>（直接注入对应行范围）
2. 当前实现: ai-companion/ 下相关文件（B 自己读）
3. 测试场景: 先写 OpenClaw 测试（TDD），再实现
4. 评分标准: 本文档的评分细则
```

不给 B 中间翻译文档。B 读原始 spec，自己决定怎么实现。

---

## B/C 可用 Skills

### B（Builder）实现时调用

| Skill | 何时用 | 哪些 Feature 适用 |
|-------|--------|-----------------|
| `/superpowers:test-driven-development` | **每个 Feature 必用** — 先写 OpenClaw 测试场景，再实现 | 全部 |
| `/simplify` | 实现完成后检查代码是否可精简 | 全部 |
| `/eg-emotion-knowledge` | 涉及情绪词汇、情绪分类时查心理学准确性 | F05 F06 F07 F11 |
| `/investigate` | 遇到 bug 时系统化排查（如 P0 bug 修复） | F08 F10 |

### C（Critic）评估时调用

| Skill | 何时用 | 哪些 Feature 适用 |
|-------|--------|-----------------|
| `/superpowers:verification-before-completion` | **每个 Feature 必用** — 声称完成前必须跑验证 | 全部 |
| `/superpowers:requesting-code-review` | 大 Feature 完成后请求 code review | F05 F06 F07 |
| `/review` | 最终合并前的 PR review | 全部完成后 |
| `/codex` | 独立 code review（作为第二评估器） | 全部 |

### 通用原则

- B 实现前**必须先调 /superpowers:test-driven-development**，写完测试再写代码
- C 声称通过前**必须先调 /superpowers:verification-before-completion**
- 涉及心理学内容时**必须调 /eg-emotion-knowledge** 查准确性
- 不确定的地方先查 `docs/references/理论/` 和竞品做法，不自己造轮子

---

## C agent 评估流程

```
1. 运行 deterministic 检查（integrity + openclaw_test）
2. 调独立评估器打 3 个 LLM 维度分（spec_completeness / architecture / test_coverage）
3. 评估器收到：spec 对应行范围 + 实现代码 + 测试结果 + 评分细则
4. 任何维度 < 9.0 → fail → C 写 strategy.md → B 修复
```

---

## P0 Bug（必须在对应 Feature 中修复）

| Bug | Feature | 影响 |
|-----|---------|------|
| `cross_week_pattern` 硬编码 False | F10 | J3→J4 转换永远不触发 |
| `delete_person()` 不清理 pending_followup + time_capsules | F08 | 告别后残留数据 |

---

## 依赖图

```
F01 记忆体系（基础）
  ↓
F02 交互系统（Canvas/Poll 基础）
  ↓
F03 Skill 体系（集成 F01+F02 到各 Skill）
  ↓
F04 首次相遇 → F05 情绪事件 → F06 日常陪伴
                                    ↓
                              F07 模式觉察 → F08 告别
                                                ↓
                                    F09 绑定验证 → F10 流转 → F11 边缘
```
