## F08 告别 — 深度功能校验方案

---

### 需求摘要

F08 告别是五条旅程中唯一的"结束型"旅程，设计目标是有尊严地送走一段关系，而不是冷冰冰地删数据。核心功能分两条路径：

**路径 A（普通删除）**：archive_manager.py delete → 清理 people/diary/memory 三个目录，含 pending_followup.md 和 time_capsules.md 的 section 级清理 → 简洁收束，不触发纪念卡。

**路径 B（仪式化封存）**：5 个节点串行 — B1 确认准备 → B2 仪式选择（Poll / 4 种仪式 / 自由形式）→ B3 执行仪式（烧掉日记 / 烧掉信念 / 时间胶囊 / 未寄出的信）→ B4 数据处理（archive_manager.py archive，含 insights 提取写入 USER.md）→ B4.5 Canvas 告别纪念卡（insights 非空时）→ B5 仪式专用收束话术。

关键数据契约：archive_manager.py archive 返回 JSON 中的 `insights` 字段，同时驱动 USER.md 写入和 Canvas 纪念卡数据填充两件事。

---

### 已覆盖

**第 1 层 pytest 单元测试（8 项，F08 直接相关）**

| 测试名 | 验证内容 |
|---|---|
| test_delete_cleans_pending_followup | P0 回归：delete_person 对 pending_followup.md 做 section 级清理 |
| test_delete_cleans_time_capsules | P0 回归：delete_person 对 time_capsules.md 做 section 级清理 |
| test_delete_basic_functionality | 基本删除：people/diary 文件移除 |
| test_archive_creates_backup_and_modifies | archive_person 创建 archive/ 备份目录 + 修改原文件 |
| test_archive_already_archived | 重复封存幂等性：返回 already_archived 而非崩溃 |
| test_archive_not_found | 封存不存在人物：返回 not_found |
| test_archive_restore_roundtrip | 封存→恢复全流程：恢复后内容与原文件完全一致 |
| test_time_capsule_creation | 时间胶囊创建：写入 time_capsules.md + open_date 精确 3 个自然月 |

**第 2 层 adapter 结构检查（3 项）**

| 检查点 | 验证内容 |
|---|---|
| P0: delete_person() 无 continue 跳过 pending/capsules | 源码逻辑分析，确认段级清理已实现 |
| P0: delete_person() pending_followup 处理无误 | 多行源码扫描 |
| Canvas 告别纪念卡 HTML 存在 | farewell-memorial.html 文件存在性 |

**第 3 层 OpenClaw 对话回测（1 项，F08 相关）**

| 消息 | 验证什么 |
|---|---|
| "今天吃了好吃的" | 闲聊不意外触发告别流程 |

**关于烧掉信念仪式的 pytest 覆盖**：已有 test_archive_with_burn_belief_ritual（仪式执行）和 test_archive_belief_write_to_user_md（新信念写入 USER.md）。

---

### 未覆盖（测试盲区）

以下是现有 116+ 项测试完全没有触碰的区域，按风险等级排列。

**P0 级（数据正确性，功能不对 = 用户数据损坏）**

1. **archive 流程的 pending_followup 清理**：现有 P0 测试只覆盖了 delete 路径，archive_person() 对 pending_followup.md 和 time_capsules.md 的 section 级清理（archive_manager.py 第 329-335 行）没有独立 pytest 验证。逻辑与 delete 不同（delete 用 `_remove_sections_mentioning`，archive 同样用此函数但在不同分支），需要单独测。

2. **insights 为空时纪念卡静默跳过**：archive_person() 返回 `{"insights": []}` 时，agent 应跳过 B4.5 纪念卡直接进入 B5。目前没有任何测试验证这条降级路径，Canvas 呈现逻辑完全依赖 agent 的行为，且 farewell-memorial.html 模板中 `{insights}` 为空时 HTML 结构会出现空 div，未经验证。

3. **restore 后 USER.md 模式洞察清理**：restore_person() 从备份恢复 people/diary/memory 文件，但 USER.md 中已经写入的去名字洞察不在恢复范围内（archive.py 第 443-527 行，restore 不触碰 USER.md）。这是设计决策但未文档化，且没有测试验证"恢复后 USER.md 是否应清理相关洞察"的行为。

**功能完整性（告别流程断链风险）**

4. **仪式串行执行后统一封存**：用户选择"烧掉信念 + 未寄出的信"两个仪式串行执行时，数据封存应在全部仪式完成后统一调用一次 archive_manager.py archive。目前没有多轮对话测试验证：(a) 两个仪式都完成后才触发 archive，(b) 中途退出后 archive 不被触发，(c) insights 正确包含两个仪式的洞察。

5. **中途退出保存机制**：用户说"算了不想了"后，已完成的仪式内容应保存在 memory/YYYY-MM-DD.md 中且不执行数据封存。没有任何测试验证"中途退出后 archive_manager.py 未被调用"这一关键负向路径。

6. **时间胶囊 open_date 月末溢出**：create_time_capsule 用 _add_months() 处理月末（如 1月31日 + 3个月 = 4月30日），archive_manager.py 第 650-658 行有 calendar.monthrange 处理逻辑，但没有 pytest 覆盖 1/31、10/31、12/31 等边界日期。

7. **时间胶囊 Heartbeat 到期检测**：check_time_capsules() 的解析逻辑依赖多行状态机（第 715-738 行），已有基本 test_time_capsule_creation，但缺少：(a) sealed → 到期检测，(b) opened 状态的胶囊不重复出现，(c) 多个胶囊混合时只返回到期项。

**Canvas 纪念卡数据填充（纯 agent 行为，无法 pytest，需对话回测）**

8. **{insights} HTML 块生成格式**：farewell-memorial.html 要求每条洞察用 `.insight` div 包裹，agent 从 archive_manager.py 返回的 `insights` 列表填充。没有对话回测验证 agent 是否正确生成 HTML 块，还是直接把文本字符串插入。

9. **{archive_date} 填充正确性**：纪念卡的 `{archive_date}` 应为当天日期，没有测试验证这个字段是否被正确填充（而非留空或写错格式）。

**告别后状态隔离（封存边界）**

10. **封存后 pattern_engine 过滤**：SKILL.md 第 214 行明确：pattern-mirror 呈现跨关系模式时，匹配结果只涉及封存关系的条目不呈现。这个过滤规则依赖读取 people/{name}.md 检查"当前状态：封存"，没有测试验证封存标记存在后 pattern_engine 是否真的排除该人。

11. **封存后 weekly-reflection 情绪统计行为**：SKILL.md 第 216 行要求封存条目的情绪标签仍参与统计但不显示具体内容来源。weekly_review.py 现有测试不涉及已封存条目的统计逻辑。

---

### 多轮测试场景

以下场景全部使用 OpenClaw 对话回测框架（`openclaw agent --agent coco --local --session-id <id> -m "<消息>" --json`）执行，需跨轮次验证文件系统状态，不能用单条消息测。

---

**场景 T01：路径 A 完整告别 + 数据清理验证（P0）**

测试层级：OpenClaw 多轮对话 + 文件系统断言

前置状态：
- workspace 中存在 `people/小凯.md`（含"当前状态：活跃"）
- `memory/pending_followup.md` 中有 `## 小凯` section
- `memory/time_capsules.md` 中有含"小凯"字段的胶囊条目

轮次：
```
轮1  用户："把跟小凯有关的东西都删了。"
轮2  可可：说清楚会发生什么（含模式保留说明）→ 验证：未直接执行删除
轮3  用户："可以。"
轮4  可可：执行 exec archive_manager.py delete → 收束两句话
```

文件系统断言：
- `people/小凯.md` 不存在
- `memory/pending_followup.md` 中不含"小凯"任何变体，但其他 section 完整保留
- `memory/time_capsules.md` 中不含"小凯"任何变体，但其他胶囊条目完整保留
- `archive/` 目录不存在（delete 不创建备份）
- `USER.md` 中无新增模式洞察（delete 不保留 insights）

禁止行为验证：
- 可可在轮2中没有出现"你确定吗"/"真的要删吗"/"再想想"

---

**场景 T02：路径 B 完整仪式 — 烧掉信念（含 USER.md 写入验证）**

测试层级：OpenClaw 多轮对话 + 文件系统断言

前置状态：
- `people/小凯.md` 存在，含"当前状态：活跃"和"## 我们之间的模式"段落

轮次：
```
轮1  用户："我想跟小凯这段关系正式说再见了。"
轮2  可可：确认话术（不说"你确定吗"）→ 验证话术格式
轮3  用户："嗯，准备好了。"
轮4  可可：发 Poll（仪式选择）
轮5  用户：选择"烧掉信念"
轮6  可可：询问旧信念
轮7  用户："我不值得被好好对待。"
轮8  可可：原文复述 → 见证 → 生成图片（或降级）→ 询问新信念
轮9  用户："我值得有人认真对我。"
轮10 可可：收到新信念 → 触发 archive_manager.py archive → 生成 Canvas 纪念卡 → 收束话术
```

文件系统断言：
- `people/小凯.md` 包含"当前状态：封存"
- `people/小凯.md` 正文被清空，## 段落存在但内容为 `<!-- 已封存 -->`
- `archive/小凯_{日期}/小凯.md` 存在且是封存前的完整版本
- `USER.md` 的"用户信念记录"段包含"我值得有人认真对我"
- `USER.md` 的"模式级洞察"段包含来自 people/小凯.md 提取的去名字洞察（不含"小凯"字样）
- `memory/pending_followup.md` 不含"小凯"（archive 流程的 section 级清理）
- `memory/time_capsules.md` 不含"小凯"（同上）

Canvas 断言（回复内容检查）：
- 可可轮10的回复中包含 Canvas 纪念卡（含 farewell-memorial.html 的 div 结构）
- 卡片中的 `{archive_date}` 为今日日期格式
- 卡片中的洞察文本不出现"小凯"

---

**场景 T03：路径 B — 时间胶囊仪式（含 3 个月 open_date 验证）**

测试层级：OpenClaw 多轮对话 + 文件系统断言

轮次：
```
轮1  用户："我想跟这段关系说再见，选时间胶囊。"
轮2  可可：询问"你想对 3 个月后的自己说什么？"
轮3  用户："希望那时候的我不会再怕麻烦别人了。"
轮4  可可：触发 archive_manager.py capsule create → 触发 ritual_image.py --type capsule → 说出 open_date
```

文件系统断言：
- `memory/time_capsules.md` 存在
- 文件中包含 `## capsule_` section
- `状态：sealed`
- `开启日期` = 今日 + 精确 3 个自然月（月末溢出验证：若当日为 1月31日，开启日应为 4月30日）
- `> 希望那时候的我不会再怕麻烦别人了` 完整保存

额外：模拟日期到开启日，调用 `archive_manager.py capsule check`，验证返回该 capsule；调用 `capsule open <id>`，验证返回 content 与写入内容一致，且文件中状态更新为 `opened`。

---

**场景 T04：中途退出 — archive 不执行（P0 负向路径）**

测试层级：OpenClaw 多轮对话 + 文件系统断言

轮次：
```
轮1  用户："我想跟小凯告别，用烧掉日记。"
轮2  可可：询问最后一句话
轮3  用户："算了不想了。"
轮4  可可："好。随时可以回来。"
```

文件系统断言：
- `people/小凯.md` 仍然存在且状态为"活跃"（未封存）
- `archive/` 目录未创建或不含小凯的备份
- `USER.md` 无新增模式洞察（archive 未执行）
- `memory/pending_followup.md` 中"小凯"相关条目仍完整保留

禁止行为：可可不追问"为什么不想了""确定不想了吗"

---

**场景 T05：仪式串行 — 两个仪式后统一封存**

测试层级：OpenClaw 多轮对话 + 文件系统断言

轮次：
```
轮1  用户："我能先烧掉信念，再写一封信吗？"
轮2  可可："可以，一个一个来。先做哪个？"
轮3  用户选择烧掉信念 → 完整执行仪式1
[仪式1 完成后，验证 archive/ 备份目录尚未创建]
轮4  用户完成仪式1 → 进入仪式2（未寄出的信）
轮5  完整执行仪式2 → 统一触发 archive
```

文件系统断言：
- 仪式1完成时（轮3结束后）：people/小凯.md 仍为活跃状态（archive 未提前触发）
- 两个仪式全部完成后（轮5结束后）：people/小凯.md 包含封存标记
- archive_manager.py archive 只被调用一次（通过检查 backup_path 目录只有一个）
- diary 中存在标记为"告别信"的条目

---

**场景 T06：封存后引用隔离 — 新对话不再提及已封存人物**

测试层级：OpenClaw 多轮对话（跨 session）

前置状态：完成场景 T02，小凯已封存。

轮次：
```
Session 2 轮1  用户："最近怎么样？"（普通闲聊）
Session 2 轮2  可可：日常回应
Session 3 轮1  用户："他又不回我消息了，我好烦。"（模糊表达，未指名）
Session 3 轮2  可可：情绪接住，不主动提"小凯"
Session 4 轮1  用户自己主动提："我有时候还是会想起小凯。"
Session 4 轮2  可可：承认记得但不引用具体事件，询问用户是否想聊
```

断言（回复内容检查）：
- Session 2-3 中，可可的回复不主动出现"小凯"
- Session 4 中，可可回复不包含"小凯说过""那次你和小凯"等具体事件引用
- Session 4 中，可可可以说"你之前有过类似的经历"但不说名字

---

**场景 T07：restore 恢复功能**

测试层级：pytest 单元测试扩展（已有 test_archive_restore_roundtrip，需增加以下场景）

子场景 T07-a：恢复后 people/小凯.md 与封存前内容逐字节一致（已覆盖）

子场景 T07-b（未覆盖）：archive → 修改 USER.md 写入洞察 → restore → 验证 USER.md 中的洞察不被还原（restore 不应触碰 USER.md）

子场景 T07-c（未覆盖）：restore 不存在的备份时返回 `{"status": "not_found"}`（已有 test_restore_not_found，但缺少验证 restore 后的文件系统状态检查）

子场景 T07-d（未覆盖）：多次 archive 同一人（封存 → 恢复 → 再封存），restore 应取最新备份（backup_dirs 按日期倒序，取第一个），验证恢复的是第二次封存前的状态而非第一次。

---

**场景 T08：insights 为空时的降级路径**

测试层级：pytest 单元测试 + OpenClaw 对话回测

pytest 部分：构造一个 people/测试人.md，仅含标题和基本字段，无"## 我们之间的模式"/"## 退出信号"/"## 跨关系匹配"段落 → 调用 archive_person() → 断言返回 `{"insights": []}` 且 status 为 "ok"。

OpenClaw 部分：
```
前置：people/陌生人.md 存在但无模式内容
轮1  用户："我想跟陌生人告别。"
轮2-n  完整路径 B 流程
```
断言：可可在 B4.5 节点不发 Canvas 纪念卡，直接进入 B5 收束话术，且收束话术为仪式对应的专用版本（不是空卡片或错误消息）。

---

**场景 T09：路径 B — 自由形式告别（无仪式选择）**

测试层级：OpenClaw 多轮对话

轮次：
```
轮1  用户："我想跟这段关系说再见，但我不知道用哪种方式。"
轮2  可可：提供 Poll 仪式选择
轮3  用户："都不太像我想的。"
轮4  可可：进入自由形式告别，作为见证者倾听
轮5  用户：长段告白式输出
轮6  用户："就这样吧。"（收束信号）
轮7  可可："我收到了。"→ 触发 archive → B4.5 纪念卡 → 收束话术"我收到了。你走吧。"
```

断言：
- 轮7收束话术必须是"我收到了。你走吧。"而非其他仪式的专用话术
- `people/{名字}.md` 封存状态已更新
- 可可在轮4-6中没有打断用户、引导结构或推销仪式

---

**场景 T10：路径 A — 用户要求模式也删除**

测试层级：OpenClaw 多轮对话 + 文件系统断言

轮次：
```
轮1  用户："把跟小凯有关的都删了，模式也别留。"
轮2  可可："好，全部清掉。"→ exec delete → 手动清除 USER.md 中与小凯相关的模式洞察
```

文件系统断言：
- `USER.md` 中原本含有"来自告别仪式"或涉及小凯关系的洞察条目被移除
- `USER.md` 其他字段完整保留

---

### 覆盖缺口优先级总结

| 优先级 | 场景/测试 | 类型 | 风险 |
|---|---|---|---|
| P0 | archive 流程对 pending_followup / time_capsules 的 section 清理 | pytest | 数据泄漏 |
| P0 | 中途退出时 archive 不被触发（T04） | OpenClaw 多轮 | 意外封存 |
| P1 | insights 为空时纪念卡静默跳过（T08） | pytest + OpenClaw | Canvas 空白/错误 |
| P1 | 仪式串行时 archive 只触发一次（T05） | OpenClaw 多轮 | 重复封存 |
| P1 | 月末 open_date 溢出边界（T03 扩展） | pytest | 时间胶囊永不到期 |
| P2 | restore 不还原 USER.md（T07-b） | pytest | 洞察混淆 |
| P2 | 封存后 pattern_engine 过滤（T06 扩展） | OpenClaw 多轮 | 已封存关系被引用 |
| P2 | Canvas 纪念卡 HTML 格式（T02 Canvas 断言） | OpenClaw 多轮 | 渲染失败 |
| P3 | 自由形式告别收束话术正确（T09） | OpenClaw 多轮 | 话术错乱 |
| P3 | 路径 A 用户要求模式也删（T10） | OpenClaw 多轮 | 洞察残留 |

---

### 关键文件索引

- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/farewell/SKILL.md` — F08 完整流程规格，5 阶段 + 4 种仪式 + 硬规则
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/farewell/scripts/archive_manager.py` — 数据层核心，archive/delete/restore/capsule 4 个操作，P0 清理逻辑在第 321-335 行（archive）和第 618-629 行（delete）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/farewell-memorial.html` — Canvas 纪念卡模板，`{insights}` 和 `{archive_date}` 两个填充变量
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md` — J5 路由规则（第 860-878 行）、封存后数据引用防护（第 1058-1065 行）、archive_manager 故障降级（第 1075 行）
- `/Users/jianghongwei/Documents/moodcoco/docs/公众号/素材/v2-evolve-测试清单.md` — 现有 116+ 项测试全量清单，F08 已覆盖项在第 57-64 行（需求→测试总表）