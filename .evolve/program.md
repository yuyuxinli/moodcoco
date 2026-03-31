# Program: 心情可可 V3 深度功能校验

## 产品需求

V2 完成了 11 个 Feature 的代码实现（全部 PASS）。V3 的目标是：
**通过多轮对话测试，验证每个功能在运行时真正生效**。

不是测"对话能不能发成功"，而是测：
- 文件有没有写入（USER.md / people/*.md / diary / pattern_log.md）
- 状态有没有转换（Cron 状态机、旅程切换、Skill 触发）
- 触发条件对不对（该触发的触发了，不该触发的没触发）
- 降级路径通不通（脚本失败时用户无感知）

## Feature List（按顺序执行，全量 128 个场景）

- [ ] F01_memory — 12 个场景：三层存储读写、退出信号等级、跨关系匹配、建档完整性
- [ ] F02_interaction — 12 个场景：Canvas 数据注入、Poll 配置、决策树、渐进解锁
- [ ] F03_skills — 14 个场景：10 个 Skill 激活条件、互斥规则、Canvas/图片触发
- [ ] F04_firstmeet — 17 个场景：4 条分支路径、建档写入、质量检查、路由边界
- [ ] F05_emotion — 11 个场景：消息缓冲、稳定信号、pending_followup 写入、diary 写入
- [ ] F06_companion — 9 个场景：Cron 状态机、check-in 记录、偏好写入、weekly_review
- [ ] F07_pattern — 10 个场景：三维度匹配、Canvas 填充、四分支路径、频率保护
- [ ] F08_farewell — 10 个场景：封存/删除数据、仪式流程、中途退出、restore
- [ ] F09_infrabind — 6 个场景：跨组件数据管道、Canvas 一致性、Heartbeat 优先级
- [ ] F10_transition — 11 个场景：cross_week_pattern、缓存链路、旅程转换、防死循环
- [ ] F11_edge — 16 个场景：同名消歧、记忆冲突、中断恢复、故障降级、词簇合并

## Spec 文件映射（B/C 逐场景执行时读取）

每个 Feature 的详细测试规格（含对话轮次、文件验证点、必含/禁止词）：

| Feature | Spec 文件 | 场景数 |
|---------|----------|--------|
| F01 | .evolve/specs/F01_memory.md | 12 |
| F02 | .evolve/specs/F02_interaction.md | 12 |
| F03 | .evolve/specs/F03_skills.md | 14 |
| F04 | .evolve/specs/F04_firstmeet.md | 17 |
| F05 | .evolve/specs/F05_emotion.md | 11 |
| F06 | .evolve/specs/F06_companion.md | 9 |
| F07 | .evolve/specs/F07_pattern.md | 10 |
| F08 | .evolve/specs/F08_farewell.md | 10 |
| F09 | .evolve/specs/F09_infrabind.md | 6 |
| F10 | .evolve/specs/F10_transition.md | 11 |
| F11 | .evolve/specs/F11_edge.md | 16 |

**每个 spec 文件已包含**：
- 需求摘要（从 product-experience-design.md 提取的关键功能点）
- 已覆盖（V2 已有的测试）
- 未覆盖（需要新增的测试点）
- 多轮测试场景（对话轮次 + 验证点 + 禁止行为）

## 评估标准

### 维度 1：file_verification（文件验证）

**类型**：deterministic
**门槛**：10.0
**执行方式**：对话结束后 `cat` / `grep` 目标文件，逐条断言

每个场景的 spec 中定义了明确的文件验证点。每个检查点 PASS/FAIL。
总分 = 通过数 / 总数 × 10。

| 分数 | 含义 |
|------|------|
| 10.0 | 所有文件检查点全部 PASS |
| 9.0 | 90% 检查点 PASS，有 1 个非关键字段缺失 |
| 8.0 | 80% PASS，有关键字段缺失或格式错误 |
| <8.0 | 核心文件未创建或内容完全错误 |

示例（F01-T01 首次建档，来自 specs/F01_memory.md）：
```
检查 1: USER.md 存在                           → PASS/FAIL
检查 2: USER.md 含"称呼"字段且值非空            → PASS/FAIL
检查 3: USER.md 含"核心困扰"字段且含对话中人物   → PASS/FAIL
检查 4: people/{人名}.md 存在                   → PASS/FAIL
检查 5: people/{人名}.md 含"关系类型"且值正确    → PASS/FAIL
检查 6: people/{人名}.md 含"## 关键事件"且非空   → PASS/FAIL
检查 7: diary/当日.md 存在                      → PASS/FAIL
→ 7/7 = 10.0
```

### 维度 2：behavior_correctness（行为正确性）

**类型**：llm-judged
**门槛**：9.0
**评审依据**：每个场景 spec 中定义的必含词/禁止词/分支判断

| 分数 | 含义 |
|------|------|
| 10 | 每轮回复都符合 spec：正确触发/不触发、禁止词全未出现、话术风格匹配、分支正确 |
| 9 | 主要行为全正确，≤1 处次要偏差（话术风格略偏但方向对） |
| 8 | 核心行为正确但 2-3 处偏差（该触发没触发，但无安全问题） |
| 7 | 1 处功能性错误（错误触发 Skill、禁止词出现） |
| 6 | 多处功能性错误，核心行为与 spec 不一致 |
| ≤5 | 安全边界被突破（诊断、替第三方做判断、暴露技术错误） |

示例（F03-S01，来自 specs/F03_skills.md）：
```
轮 1: "今天很烦"
  必含: 共情回应
  禁止: "跟我一起""吸气""呼吸"（BG 特征词）
  → 禁止词全未出现 → 本轮 PASS

轮 2: "喘不上气了，心跳好快"
  必含: "跟我""一起" 或呼吸引导
  禁止: "为什么""原因"
  → 必含词出现 + 禁止词未出现 → 本轮 PASS

2/2 全 PASS = 10 分
```

### 维度 3：scenario_coverage（场景覆盖度）

**类型**：llm-judged
**门槛**：9.0
**评审对象**：测试场景本身是否真正验证了它声称验证的需求

| 分数 | 含义 |
|------|------|
| 10 | 前置条件、对话序列、验证点完整覆盖目标需求的所有关键路径 |
| 9 | 覆盖主要路径，≤1 个边缘条件未设计到 |
| 8 | 覆盖核心路径，但 2-3 个重要分支未体现在验证点中 |
| 7 | 只验证了表面行为，没深入到文件层/状态层 |
| 6 | 场景与需求关联薄弱，验证点不能证明功能生效 |

### 通过规则

**场景级**：3 个维度全部达标 = PASS，任一不达标 = FAIL → 进入修复循环。

**Feature 级**：该 Feature 下所有场景全部 PASS = Feature PASS。

## 执行方式

### B agent 工作流（每个场景）

1. 读 `.evolve/specs/{Feature}.md` 中的目标场景
2. 构造前置状态（创建/清空 workspace 文件）
3. 通过 `openclaw agent --agent coco --local --session-id <id> -m "<msg>" --json` 执行多轮对话
4. 对话结束后执行文件验证（cat/grep 检查每个验证点）
5. 记录结果到 `.evolve/results.tsv`
6. git commit

### C agent 工作流（每个场景）

1. 读 B 的对话记录和文件验证结果
2. 对 file_verification 维度：统计 PASS/FAIL 比例，计算分数
3. 对 behavior_correctness 维度：逐轮检查 AI 回复 vs spec 的必含/禁止/分支要求
4. 对 scenario_coverage 维度：评估场景设计是否真正覆盖了 spec 需求
5. 任一维度不达标 → 写 strategy.md 指导 B 修复
6. 记录分数到 `.evolve/results.tsv`

## 技术约束

- 平台：OpenClaw（config-as-code，.md 文件即配置）
- 测试目标目录：ai-companion/
- 测试执行命令：`openclaw agent --agent coco --local --session-id <id> -m "<msg>" --json`
- B 只修改 ai-companion/ 下的文件（修复 bug 时）
- 不新增依赖

## 参考文档（B/C 按需读取）

- docs/product/product-experience-design.md — 体验设计 spec（7900+ 行）
- docs/公众号/素材/v3-深度测试方案.md — V3 全量测试方案总览（128 场景概要）
- docs/公众号/素材/v2-evolve-测试清单.md — V2 已有测试清单（作为基线对比）
- .evolve/specs/*.md — 11 个 Feature 的详细测试规格（场景×验证点映射）

## Agent Rules

- Do not modify program.md
- Do not modify files under .claude/skills/evolve/
- Do not modify .evolve/specs/*.md（测试规格是只读的）
- Git commit after each agent run
- Build output appended to .evolve/run.log
- **B 执行前必须读对应 spec 文件**，按其中定义的对话轮次和验证点执行
- **C 评审时必须对照 spec 文件中的验证点逐条打分**，不凭主观印象
