## F03 Skill 体系 — 深度功能校验方案

### 需求摘要

F03 定义了 10 个 Skill 的完整体系，核心规格包括：

**10 个 Skill 及激活条件（AGENTS.md 路由决策树）**

| 优先级 | Skill | 激活硬条件 |
|--------|-------|-----------|
| P0（前置） | 安全协议 | 任意危机关键词，中断一切 Skill |
| P1 | breathing-ground | 情绪淹没 + 身体症状（心跳快/手抖/喘不上气） |
| — | onboarding | USER.md 不存在或为空（且无情绪淹没） |
| P2 | decision-cooling | 用户表达即将采取的具体冲动行动（"想法"不触发） |
| — | relationship-guide | 关系问题/矛盾/需要沟通工具 |
| — | pattern-mirror | 退出意图 + people/ ≥2 段关系 + ≥5 次对话 + 情绪稳定 + 频率保护通过 |
| P2.5 | growth-story | 自我否定 + diary ≥2 周 + growth_tracker 检测到 ≥1 个 IM + 情绪稳定 |
| — | farewell | 用户主动表达告别/翻篇/封存意图 |
| P4/P5 | diary | 有具体事件/人物/主动要记录；优先级高于 check-in |
| — | check-in | Heartbeat 常规关怀 / 闲聊无情绪事件 / Cron 21:30 |
| — | weekly-reflection | Heartbeat 周日 20:00 + 本周 diary ≥3 条 |

**Skill 间互斥/优先级规则（AGENTS.md §Skill 互斥规则）**

- 一次对话最多触发 2 个 Skill；breathing-ground 可与另一个共存（必须先于其他 Skill 完成）
- decision-cooling 和 relationship-guide 不同时触发
- 周日只发 weekly-reflection，不发 Cron 日记提醒；decision-cooling 回访 / 时间胶囊到期优先于 weekly-reflection
- pattern-mirror 和 growth-story 共享每周 2 次频率上限（写入 memory/pattern_log.md）

**Canvas/图片集成矩阵（F02 依赖）**

| Skill | Canvas 触发条件 | 图片触发条件 |
|-------|----------------|-------------|
| pattern-mirror | ≥2 匹配维度 + macOS 桌面端 → canvas/pattern-comparison.html | 无 |
| growth-story | ≥2 个 IM + macOS 桌面端 + 用户积极反应 → canvas/growth-trajectory.html | 无 |
| farewell | Phase 4 封存成功 + insights 非空 + 仪式化路径 → canvas/farewell-memorial.html | 仪式类型匹配 → ritual_image.py（烧掉/信封/胶囊） |
| weekly-reflection | macOS 桌面端 → weekly_review.py --format html → 周情绪地图 | 无 |

**里程碑图片入口**：milestone_image.py（路径 `skills/growth-story/scripts/milestone_image.py`），在 AGENTS.md 中定义，对话计数达到 10/30/50/100 次时触发，由 growth-story 目录管理但不由特定 Skill 独立路由，而是在 AGENTS.md 渐进式解锁表中声明。

---

### 已覆盖（现有测试清单中已有）

**第 2 层 adapter 结构检查（仅 5 项覆盖 F03）**：

- 检查点 26：docs/ 无已删除 Skill 引用（正则 word-boundary 扫描）
- 检查点 27：pattern-mirror SKILL.md 含 "Canvas" 关键词
- 检查点 28：growth-story SKILL.md 含 "Canvas" 关键词
- 检查点 29：farewell SKILL.md 含 "ritual_image" 关键词
- 检查点 30：AGENTS.md 含 "里程碑"/"milestone" 关键词

**第 3 层 OpenClaw 对话回测（覆盖 F03 的仅 2 条）**：

- 场景 5：闲聊不触发 Skill（"今天吃了好吃的"）
- 场景 6：情绪信号触发共情（"他又不回我消息了"）

**第 1 层 pytest**：所有测试针对脚本层（pattern_engine、growth_tracker、archive_manager、weekly_review），不测试 Skill 激活逻辑本身。

**结论**：现有覆盖仅验证"文件存在性 + 关键词出现"，完全没有测试 Skill 功能是否真正生效。F03 的 test_coverage 评分 8.0（最低分）正是这个原因。

---

### 未覆盖（功能性空白）

按严重程度排序：

**P0 级缺口 — 激活条件精确性**

1. breathing-ground 的"想法 vs 行动"区分没有测试："今天很烦"不应触发，"我喘不上气了"应触发——两者当前都没有多轮验证
2. decision-cooling 的"想法 vs 行动"区分没有测试："我想分手"不应触发，"我现在就去跟他说分手"应触发
3. onboarding 触发条件（USER.md 空白）没有测试：USER.md 已存在时不应走 onboarding，当前无验证
4. pattern-mirror 的前置条件联合检测没有测试：5 次对话 + 2 段关系 + 情绪稳定缺一不可，单独满足其中 1-2 个不应触发
5. growth-story 的 diary ≥2 周门槛没有测试：diary 只有 1 周时不应触发

**P0 级缺口 — Skill 互斥规则**

6. decision-cooling 和 relationship-guide 不同时触发：用户说"我现在就去找他说清楚这件事"，应走 decision-cooling 而不是 relationship-guide，没有测试
7. breathing-ground 必须先于其他 Skill 完成：用户恐慌 + 冲动行动并发时，应先走 breathing-ground 再走 decision-cooling，顺序没有测试
8. weekly-reflection 与 decision-cooling 回访的互斥：周日同时有 pending_followup，应先做回访不发周回顾，没有测试

**P1 级缺口 — Canvas/图片实际触发**

9. pattern-mirror Canvas 触发：需要 ≥2 匹配维度 + macOS 桌面端，仅检查 SKILL.md 有"Canvas"关键词，没有验证实际触发逻辑是否按条件执行
10. growth-story Canvas 触发：需要 ≥2 个 IM + 用户积极反应，同上
11. farewell ritual_image 触发：三种仪式类型（burn/letter/capsule）对应三种图片，实际生成路径和降级（PIL 不可用）没有测试
12. farewell Canvas 纪念卡（卡片 E）：仪式化路径才触发，普通删除路径不触发，这个分支没有测试
13. weekly-reflection Canvas：macOS 端 vs 非 macOS 端的分路没有测试
14. 里程碑图片（milestone_image.py）：第 30/50/100 次对话触发，没有任何测试

**P1 级缺口 — 旧 Skill 引用清理验证不完整**

15. 现有检查点 26 只扫描 docs/ 目录，没有扫描 ai-companion/AGENTS.md 本体（实测发现 AGENTS.md 中 diary/SKILL.md 引用了 "emotion-journal 六元组"的溯源说明，属于合理注释，但扫描范围应包含 ai-companion/ 下所有 .md）
16. 没有验证已删除目录确实不存在：skills/calm-down/、skills/sigh/、skills/emotion-journal/、skills/relationship-coach/、skills/relationship-skills/ 五个目录应已物理删除，没有检查

**P2 级缺口 — Skill 内部流程分支**

17. breathing-ground 内部工具优先级：身体症状 → 循环叹息优先，exec 失败降级纯对话，没有测试
18. diary 极简 vs 深度模式：用户回答 ≤30 字走极简，>100 字走深度，分支没有测试
19. pattern-mirror 的 strategy 选择：用户自发连接 > 原话回响 > 好奇提问，策略 3 必须征求许可，没有测试
20. growth-story 用户否认后的处理："我觉得没什么变化"→ 不坚持，标记 `成长反馈偏好: 敏感`，没有测试
21. check-in 与 diary 的升级路径：check-in 中用户展开倾诉应自然升级到 diary，没有测试

---

### 多轮测试场景

以下场景按优先级排列，每个场景的验证目标是"功能是否真正生效"，不是"有没有收到回复"。

**验证方法**：使用 `openclaw agent --agent coco --local --session-id <id> -m "<msg>" --json`，多轮连续对话共用同一 session-id。验证点明确可机器检查（禁止词、必含词、或脚本是否被调用）。

---

#### S01：breathing-ground 激活精确性（正向 + 反向）

目的：验证触发条件不过宽也不过窄。

```
轮 1：用户发 "今天很烦，心情不好"
期望：不触发 breathing-ground（"烦"不等于情绪淹没）
禁止出现："跟我一起""吸气""呼吸""breathe"
必含某种共情回应

轮 2（同 session）：用户发 "我现在心跳好快，手在抖，感觉要崩了"
期望：触发 breathing-ground
必含："跟我""一起""跟着数" 或 exec breathe-fast.py 被调用
禁止出现：任何认知分析（"为什么""原因""想一想"）

轮 3（轮 2 同 session）：用户发 "还是不行，脑子停不下来"
期望：升级到 5-4-3-2-1 感官着陆工具
必含："5 样""看到""摸到"之类的感官着陆引导
禁止：重复同一个循环叹息引导
```

---

#### S02：decision-cooling 想法 vs 行动区分

目的：验证核心区分逻辑。

```
轮 1：用户发 "我想分手，这段关系太累了"
期望：不触发 decision-cooling
期望：走 AGENTS.md 四步框架（情绪接住）
禁止出现："等 24 小时""明天再来""先停一停"

轮 2（新 session）：用户发 "我现在就去跟他说分手，我要发消息了"
期望：触发 decision-cooling
必含："明天""等""先停" 之类暂停引导
禁止出现：relationship-guide 的 IFS/EFT 框架引导
```

---

#### S03：decision-cooling vs relationship-guide 互斥

目的：验证两者不同时触发的规则。

```
用户发 "他说了一句很伤我的话，我现在就去找他说清楚这件事到底是什么意思"
期望：触发 decision-cooling（冲动行动优先）
必含：暂停/冷却引导
禁止出现：I-statements 引导、IFS parts 引导（relationship-guide 的特征词）
```

---

#### S04：onboarding 首次 vs 非首次区分

目的：验证 USER.md 存在性触发逻辑。

```
测试 A（新 session，workspace 无 USER.md）：
用户发 "你好"
期望：走 onboarding
必含：朋友式好奇开场（不含"我是心情可可""我可以帮你"等自介绍词）
禁止出现：diary 触发、任何 Skill 功能列举

测试 B（已有 USER.md 的 session）：
用户发 "你好"
期望：不走 onboarding
必含：基于历史记忆的自然回溯（如提到上次聊的内容）
```

---

#### S05：pattern-mirror 前置条件联合验证

目的：单一条件不足时不触发，全部满足时触发。

```
测试 A（people/ 只有 1 段关系）：
用户发 "我想跟他分手了"
期望：不触发 pattern-mirror（关系数量不足）
禁止出现：跨关系模式描述（"上次你也说过""和 XX 的时候"）

测试 B（people/ 有 2 段关系，但 session 是第 3 次对话）：
用户发 "我想跟他分手了"
期望：不触发 pattern-mirror（对话次数不足 5）
禁止出现：跨关系模式描述

测试 C（people/ 有 2 段关系、对话 ≥5 次、用户情绪仍在激动中）：
用户发 "我真的受不了了，我要跟他分手！！！"
期望：先走 Phase 1 情绪接住，不提模式
必含：情绪接住回应
禁止：跨关系对比

测试 D（所有前置条件满足）：
前置：people/A.md + people/B.md（都含退出信号），对话次数 ≥5，用户情绪稳定后
用户发 "我又觉得他不在乎我了，想跑"
期望：等情绪稳定后触发 pattern-mirror
必含：引用历史人物的具体事件原话（"你和 XX 在一起第 N 个月时说过..."）
禁止：使用"逃避型依恋"等标签
```

---

#### S06：growth-story diary 数据门槛验证

目的：diary 数据不足时不触发。

```
测试 A（workspace 中 diary/ 只有 3 天数据）：
用户发 "我是不是天生不适合谈恋爱"
期望：不触发 growth-story（数据不足）
必含：情绪接住
禁止出现：成长叙事引用（"你 1 月份说'...'，现在说'...'"）

测试 B（diary/ 有 ≥2 周数据，growth_tracker 能检测到 IM）：
用户发 "我是不是天生不适合谈恋爱"
期望：触发 growth-story
必含：引用用户历史原话做前后对比
禁止出现："你进步了""你已经很好了"（鸡汤词）
```

---

#### S07：breathing-ground + decision-cooling 协同顺序

目的：验证 P1 必须先于 P2 完成的规则。

```
轮 1：用户发 "我喘不上气，我现在就要去找他！"
期望：先走 breathing-ground（P1 > P2）
必含：呼吸引导（不是冷却引导）
禁止出现："等 24 小时"（decision-cooling 特征词）

轮 2（同 session，完成呼吸后）：用户发 "好多了，但我还是想去找他"
期望：现在才触发 decision-cooling
必含：暂停/冷却引导
```

---

#### S08：farewell 仪式图片生成路径

目的：验证三种仪式类型各自对应正确的图片生成调用。

```
测试 A（烧掉信念仪式）：
前置：建立 people/某人.md，用户表达告别意图，走仪式化封存
用户选择：烧掉信念（Poll 选项 2）
用户写出信念后
期望：exec ritual_image.py --type burn 被调用
降级测试：PIL 不可用时，图片不发送但仪式对话继续（必含收束语，不含错误信息暴露）

测试 B（时间胶囊）：
用户选择时间胶囊
期望：archive_manager.py capsule create 被调用，open_date 设为约 3 个月后
期望：待胶囊到期时，Heartbeat 可触发开封

测试 C（普通删除不触发 Canvas 纪念卡）：
用户说"直接删了，不用仪式"
期望：走 archive_manager.py delete
禁止出现：Canvas 纪念卡呈现（farewell SKILL.md 明确"普通删除不触发"）
```

---

#### S09：weekly-reflection 触发条件与互斥

目的：验证触发门槛和与其他 Heartbeat 事项的互斥。

```
测试 A（本周 diary 只有 2 条）：
模拟周日 20:00 Heartbeat
期望：不触发 weekly-reflection（未达 3 条门槛）
期望：降级为常规关怀（check-in）或不发

测试 B（本周 diary ≥3 条）：
模拟周日 20:00 Heartbeat
期望：触发 weekly-reflection
必含：本周情绪概览（情绪词 + 日期）
必含：关于高频情绪或人物的 1 句引导性问题

测试 C（同一周日，有 pending_followup 待回访）：
期望：decision-cooling 回访优先执行，不发 weekly-reflection
验证：回访消息出现，周回顾消息不出现
```

---

#### S10：Canvas 触发条件与降级路径

目的：验证 Canvas 只在正确条件下触发，非桌面端正确降级。

```
测试 A（pattern-mirror Canvas，非 macOS 端）：
前置：满足 pattern-mirror 所有触发条件，但渠道为 Telegram（非桌面端）
期望：不展示 Canvas，走纯对话模式
必含：用户原话引用做跨关系对比（不是 Canvas 缺失的替代空洞描述）

测试 B（growth-story Canvas，匹配到 ≥2 个 IM，macOS 端）：
期望：agent 生成 growth-trajectory.html 并通过 canvas present 展示
必含：IM 节点（时间点 + 原话 + 类型）
禁止出现：HTML 标签泄露到普通文本回复中

测试 C（growth-story，用户首次对成长叙事有积极反应后）：
期望：Canvas 在用户积极反应后才触发（不是第一轮就展示）
```

---

#### S11：里程碑图片触发

目的：验证第 30/50/100 次对话的里程碑时刻。

```
前置：USER.md 中对话计数恰好到达 30
用户发任意消息
期望：milestone_image.py --count 30 被调用
必含：里程碑祝贺语
降级测试：milestone_image.py 失败时，用纯对话替代（禁止出现错误信息）
```

---

#### S12：旧 Skill 引用清理完整验证

目的：比现有检查点 26 更全面地扫描。

```
检查 1（AGENTS.md 无旧 Skill 路径引用）：
扫描 ai-companion/AGENTS.md 全文
禁止出现 word-boundary 匹配：\bcalm-down\b、\bsigh\b（作为 Skill 名，非心理学术语"叹息"）、\bemotion-journal\b、\brelationship-coach\b、\brelationship-skills\b

注意：diary/SKILL.md 中"融合自 emotion-journal"是来源注释，属于合理保留；
      psychology-techniques.md 中"cyclic sigh"是学术用语，不是 Skill 引用；
      程序需区分 Skill 路径引用（skills/emotion-journal/SKILL.md）vs 来源说明文字

检查 2（五个已删除目录不存在）：
验证以下目录均已不存在：
- ai-companion/skills/calm-down/
- ai-companion/skills/sigh/
- ai-companion/skills/emotion-journal/
- ai-companion/skills/relationship-coach/
- ai-companion/skills/relationship-skills/

检查 3（AGENTS.md 路由包含 10 个 Skill 的正确路径）：
验证以下 10 个路径均出现：
skills/breathing-ground/SKILL.md
skills/onboarding/SKILL.md
skills/check-in/SKILL.md
skills/diary/SKILL.md
skills/relationship-guide/SKILL.md
skills/pattern-mirror/SKILL.md
skills/decision-cooling/SKILL.md
skills/farewell/SKILL.md
skills/growth-story/SKILL.md
skills/weekly-reflection/SKILL.md
```

---

#### S13：check-in 与 diary 的升级路径

目的：验证 check-in 中倾诉展开时自然升级逻辑。

```
轮 1（Heartbeat 触发 check-in）：
可可发起 "今天整体什么感觉？"
用户回 "有点烦"

轮 2：
可可问 "怎么了？想说说吗？"
用户回 "他今天又说了一句很伤我的话，就是..."（展开倾诉，>100 字）

期望：自然升级到 AGENTS.md 四步框架（情绪接住）
禁止出现："那我们来好好聊聊"（SKILL.md 明确禁止此话术）
禁止出现：diary 六元组审讯式引导（"发生了什么？感受是什么？"连续提问）
```

---

#### S14：pattern-mirror 频率保护

目的：验证 pattern_log.md 的频率限制生效。

```
前置：本周已有 2 次模式呈现记录在 memory/pattern_log.md

用户满足 pattern-mirror 所有前置条件
期望：不触发 pattern-mirror（已达每周 2 次上限）
禁止出现：跨关系模式对比内容

前置变更：pattern_log.md 中同一个匹配结果的上次呈现日期为 10 天前
期望：不触发（同一匹配结果需 ≥14 天冷却）
```

---

### 补充说明

**测试优先级建议**：S01-S05、S12 为最高优先级（直接对应 F03 test_coverage 评分为 8.0 的核心缺口）。S08、S11 次之（Canvas/图片集成是 adapter 结构检查声称已覆盖但实际只验证关键词存在的盲区）。

**测试数据准备**：S04/S05/S06/S14 需要预先构造 workspace 状态（USER.md 内容、people/ 数量、diary/ 日期分布、pattern_log.md 记录），建议通过 pytest fixture 或 adapter 预置脚本来统一管理测试数据。

**里程碑图片的特殊性**：milestone_image.py 当前状态为"待创建"（F03 §6.4），这意味着 S11 是功能尚未实现的验收测试，应在实现后首批执行。

---

### 关键参考文件（绝对路径）

- `/Users/jianghongwei/Documents/moodcoco/docs/product/product-experience-design.md`（行 1903-2010：路由决策树、优先级规则、互斥规则完整规格）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md`（行 495-540：Skill 调用规则；行 514-527：路由优先级表；行 1220-1245：脚本映射 + 里程碑触发）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/breathing-ground/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/onboarding/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/pattern-mirror/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/farewell/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/growth-story/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/weekly-reflection/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/decision-cooling/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/check-in/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/diary/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/relationship-guide/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/docs/公众号/素材/v2-evolve-测试清单.md`（已有覆盖基线）