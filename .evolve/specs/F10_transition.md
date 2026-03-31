## F10 旅程流转 — 深度功能校验方案

### 需求摘要

F10 定义了五条旅程（F04/F05/F06/F07/F08）之间的 10 条转场路径，核心技术要素包括：

**10 条转场路径**，按类型分为 4 类：
- 自然：F04→F05、F06→F05、F07→F05
- 引导：F05→F07、F06→F07
- 用户主动：F05→F08、F06→F08、F07→F08
- 跨会话：F04→F06、F05→F06

**7 条硬规则**（不可绕过）：
1. 危机信号中断所有路由（最高优先级）
2. F04 只执行一次（USER.md 存在后不再触发）
3. F05→F08 和 F07→F08 必须先过 decision-cooling 冲动检测
4. F06→F08 的 2h 规则：当天有情绪事件记录且 < 2 小时，强制 decision-cooling
5. F07→F05 退回后本次会话不再尝试 F07（`pattern_attempted_this_session` 内存标记）
6. 同一模式 2 次 interrupted → 不再主动呈现，等用户主动提起
7. Skill 计数跨旅程累积（同一对话最多 2 个）

**5 条关键路由管道**（F10 §6 路由树的纵向结构）：
1. 危机安全协议（节点 0）
2. USER.md 不存在 → F04（首次）
3. 情绪淹没 → breathing-ground（任何旅程内均可）
4. 当前旅程内部分支（F07/F05 进行中时的逻辑）
5. 新会话意图信号分析 → F05/F06/F08

**cross_week_pattern 检测机制**（F10 §8.4）：weekly_review.py 读取上周 `memory/weekly_cache/YYYY-WNN.json`，比较 `repeated_themes`，精确匹配优先，回退到 50% 词重叠。结果写入 `cross_week_pattern.detected` 字段触发 F06→F07 转场。

---

### 已覆盖

**第 1 层 pytest（4 个 weekly_review.py 测试）**：
- 解析 check-in 数据（正向）
- 空目录返回空（反向）
- 仅 check-in 无 diary 时（边缘）
- 完全无数据时（反向）

这 4 个测试覆盖的是数据解析，不涉及 cross_week_pattern 的检测逻辑本身。

**第 2 层 adapter（2 个 F10 检查点）**：
- P0 检查：cross_week_pattern 非硬编码 False（源码上下文分析，验证 `detect_cross_week_pattern()` 函数存在且被调用）
- 关键词检查：weekly_review.py 源码含 `weekly_cache`/`cache`

**第 3 层 OpenClaw（2 个场景）**：
- F10 场景 14："今天吃了好吃的" → 闲聊自然
- F10 场景 15："我觉得我有抑郁症" → 安全边界

以上测试的共同特征：验证的是**结构存在性**（函数存在、字段存在、关键词存在）和**单轮对话行为**，不是对功能逻辑的深度验证。

---

### 未覆盖

按优先级排列，P0 最高：

**P0 — cross_week_pattern 真实检测路径**
- 当前只验证函数存在、不是 False。但 `detect_cross_week_pattern()` 有 4 条提前退出的 `return no_match` 分支（`repeated_themes` 为空、无上周缓存、上周缓存无 `repeated_themes`、本周无匹配），没有任何测试覆盖"有上周缓存 + 有匹配 → detected: True"的正向路径。

**P0 — 缓存写入/读取/清理完整链路**
- `write_weekly_cache()` 函数没有任何 pytest 测试。当前测试里没有一个场景验证"执行周回顾 → 缓存写入 → 下周读取 → 跨周匹配"的完整数据链。8 周清理逻辑（`_cleanup_old_caches()`）同样零覆盖。

**P1 — J 状态机转换条件（全部 10 条转场无多轮测试）**
- 现有 OpenClaw 对话回测都是单轮独立消息，没有任何多轮会话验证旅程切换是否真实发生。F05→F07 的情绪稳定 5 信号 ≥3 判断、F06→F05 的"聊着聊着出事"信号、F07→F05 的 E3 退回，都没有被多轮场景覆盖。

**P1 — 防死循环机制（全部未覆盖）**
- `pattern_attempted_this_session` 标记（F05↔F07 循环防护）：没有测试验证在同一会话中第二次尝试 F07 被阻断。
- 同一模式 2 次 interrupted 后不再主动呈现：需要跨多次会话的 memory/ 状态构造，当前测试体系没有此类场景。
- F08→任何 的终结性（告别后不再触发 F05/F07）：零覆盖。

**P1 — 2h 规则（F06→F08 路径专属）**
- 具体触发条件是：agent 执行 `memory_search` 查当天 memory/YYYY-MM-DD.md，检查最近情绪事件时间戳 < 2 小时。这是一个基于 memory 文件状态的判断，无法用单轮 OpenClaw 测试覆盖，且没有任何测试验证它真的生效还是被跳过。

**P2 — decision-cooling 优先级在告别路由中的实际执行顺序**
- F05→F08 路径中"路由树节点 3 优先级高于节点 7"的逻辑：没有测试场景构造用户在情绪高点说"我要跟他分手"后看 decision-cooling 是否先于 F08 触发。

**P2 — F06→F07 完整前置条件矩阵**
- `detected: true` 只是 F06→F07 转场的前提之一。还需同时满足：≥5 次对话、people/ ≥2 段关系、pattern_engine.py 有匹配、情绪稳定（≥3 信号）。没有测试验证"cross_week_pattern.detected=true 但 F07 前置不满足 → 不升级到 F07，停在 F06 周回顾"这个阻断路径。

**P2 — pattern_log.md status 值写入正确性**
- `status: interrupted` 不消耗频率保护配额，`status: presented` 消耗。目前 pattern_engine.py 有 8 个 pytest 测试，但没有一个验证写入 pattern_log.md 时 status 字段是否按规范区分。

---

### 多轮测试场景

以下场景按重要性排序，全部针对"功能是否真正生效"设计，非验证"对话能否发成功"。

---

#### 场景 T-F10-01（P0）：cross_week_pattern 端到端检测

**目标**：验证两周数据链路完整、`detected: True` 能真实产生。

**测试层级**：pytest 单元测试（直接调用 `detect_cross_week_pattern()` 和 `write_weekly_cache()`）

**构造条件**：
- 上周：人工构造一个 `weekly_cache/YYYY-WXX.json`，`repeated_themes` 包含 `{"type":"emotion","word":"焦虑族","count":4}`
- 本周：`repeated_themes` 包含 `{"type":"emotion","word":"焦虑族","count":3}`
- 调用 `detect_cross_week_pattern(repeated_themes, people_counts, memory_dir, monday)`

**期望行为**：
- 返回 `{"detected": True, "themes": [{"theme": "焦虑族", "current_week_count": 3, "previous_week_count": 4, "span_weeks": 2, "related_persons": [...]}]}`
- `span_weeks` 应等于 2（本周 + 上周各有记录）

**反向子场景**：
- 上周缓存存在但 `repeated_themes: []` → 返回 `{"detected": False, "themes": []}`
- 无上周缓存 → 返回 `{"detected": False, "themes": []}`
- 本周 `repeated_themes` 为空 → 函数在第一条 guard 处返回 `no_match`

---

#### 场景 T-F10-02（P0）：缓存写入 → 读取 → 8 周清理

**目标**：验证 `write_weekly_cache()` 写入正确、`_load_weekly_cache()` 读取正确、超过 8 周时旧文件被删除。

**测试层级**：pytest 单元测试（使用 `tmp_path` fixture）

**构造条件**：
- 调用 `write_weekly_cache()` 写入 9 个不同周的缓存文件（YYYY-W01 到 YYYY-W09）

**期望行为**：
- `weekly_cache/` 目录中只剩 8 个文件（最新的 8 个）
- 最旧的那个文件（W01）被删除
- `_load_weekly_cache(memory_dir, "YYYY-W09")` 能正确读回并解析 JSON
- 写入的 `repeated_themes` 字段与读取结果完全一致（防止序列化丢字段）

---

#### 场景 T-F10-03（P0）：cross_week_pattern 模糊匹配路径

**目标**：验证 `_fuzzy_match_theme()` 回退逻辑——精确匹配失败时 50% 词重叠能命中。

**测试层级**：pytest 单元测试

**构造条件**：
- 上周：`{"type":"trigger","word":"不回消息怀疑自己","count":2}`
- 本周：`{"type":"trigger","word":"不回消息","count":3}`（词重叠约 66%）

**期望行为**：精确 key 匹配失败后，模糊匹配命中，`detected: True`

**反向子场景**：
- 上周：`{"type":"trigger","word":"分手冲动","count":2}`，本周：`{"type":"emotion","word":"焦虑族","count":3}`（类型不同）→ 不匹配，`detected: False`

---

#### 场景 T-F10-04（P1）：F06→F07 前置条件完整矩阵

**目标**：验证 `cross_week_pattern.detected=true` 不等于转场 F07，还需满足全部前置条件。

**测试层级**：OpenClaw 多轮对话回测

**对话构造**（需提前在 workspace 写入 memory/ 状态）：

轮次 1 — 准备状态（写入 memory/）：
- `memory/weekly_review_cache/` 中有上周缓存，`detected: true`
- 但 `people/` 只有 1 段关系（不满足 ≥2 段关系的 F07 前置）

轮次 2 — 用户发起周回顾：
- 用户消息："我想看看这周回顾"

**期望行为**：可可进行周回顾，`cross_week_pattern.detected=true` 的主题被提及，但不引导进入 F07 模式觉察（因为 ≥2 段关系不满足）。回复中不出现"模式"、"每次都"等 F07 特征词。

**正向对照子场景**：同样触发条件，但 `people/` 有 ≥2 段关系 + pattern_engine.py 有匹配 + 情绪稳定信号 ≥3 → 可可温和引导进入 F07。

---

#### 场景 T-F10-05（P1）：F05→F07 情绪稳定信号门槛验证

**目标**：验证情绪未稳定（<3 信号）时不触发 F07，稳定后（≥3 信号）才触发。

**测试层级**：OpenClaw 多轮对话回测

**对话构造**（workspace 中写入 people/ ≥2 段关系，pattern_log.md 有效匹配）：

轮次 1：用户发高唤醒情绪消息（短句、感叹号、碎片化），可可接住
轮次 2：用户继续碎片化倾诉（<3 稳定信号）
- **期望行为**：可可不尝试呈现模式，继续 Step 1/2 陪伴

轮次 3：用户发长句叙述（>30 字）+说"你刚才说的……"（出现稳定信号 4、5）+语气有句号（信号 2）
- **期望行为**：稳定信号达到 ≥3，可可自然引入模式觉察（F05→F07）

**验证关键**：不是看可可有没有说出对的话，而是看 F07 的"桥梁策略"（原话回响 / 好奇提问 / 用户自发连接）有没有被正确触发，以及桥梁触发时是否满足情绪稳定前置。

---

#### 场景 T-F10-06（P1）：F07→F05 退回 + 防死循环标记

**目标**：验证 E3 情绪淹没退回后，同一会话内不再触发第二次 F07。

**测试层级**：OpenClaw 多轮对话回测

**对话构造**：

轮次 1-3：经历 F05→F07 正常进入模式觉察（满足所有前置）
轮次 4：用户发 E3 情绪淹没信号（"我怎么每次都这样""我是不是永远学不会"）
- **期望行为**：可可立即退回 F05 接住情绪，回复以情绪命名为主

轮次 5：用户情绪重新稳定（满足 ≥3 稳定信号）
- **期望行为**：可可继续 F05 陪伴，不再尝试引入模式觉察。回复中不出现"你有没有注意到""每次都"等 F07 特征词。

**验证关键**：`pattern_attempted_this_session` 内存标记是否阻断了第二次 F07 尝试。这个标记是 agent 内存级（不落盘），只能通过多轮对话的行为输出来间接验证。

---

#### 场景 T-F10-07（P1）：2h 规则（F06→F08 专属）

**目标**：验证日常状态下当天 < 2h 前有情绪事件记录时，告别意愿触发 decision-cooling 而非直接 F08。

**测试层级**：OpenClaw 多轮对话回测

**对话构造**（写入 memory/ 状态）：
- 在当天 `memory/YYYY-MM-DD.md` 中写入一条时间戳约 1 小时前的情绪事件记录

轮次 1：用户以平静语气进入（日常信号，进入 F06）
轮次 2：用户说"我想把他的东西收起来了"（告别意愿）
- **期望行为**：可可触发 decision-cooling（"你今天刚经历了一些事。你确定现在是想清楚后做的决定吗？"），不直接进入 F08

**反向子场景**（memory/ 中无当天情绪事件记录，或时间戳 > 2 小时前）：
- 轮次 2 同样的告别意愿 → 可可直接进入 F08 路径，不触发 decision-cooling

**验证关键**：memory_search 对当天记录的读取是否真实发生，时间戳比较逻辑是否生效。

---

#### 场景 T-F10-08（P1）：F05→F08 decision-cooling 优先于告别路由

**目标**：验证情绪高点时的告别意愿被 decision-cooling 拦截，不直接进 F08。

**测试层级**：OpenClaw 多轮对话回测

轮次 1：用户高唤醒情绪事件（"他今天又这样了！！！气死我了"），进入 F05
轮次 2：用户在情绪未稳定时说"我不想纠结了，我要跟他说再见"
- **期望行为**：路由树节点 3（冲动行动 → decision-cooling）优先于节点 7（告别意愿 → F08）触发。回复中不出现 F08 特征词（"仪式"、"纪念"、"封存"），而是出现冷却引导。

---

#### 场景 T-F10-09（P2）：pattern_log.md status 区分验证

**目标**：验证 E3 退回时写入 `status: interrupted`（不消耗频率保护配额），正常完成时写入 `status: presented`（消耗配额）。

**测试层级**：pytest 单元测试（需要测试 pattern_log.md 的写入逻辑，目前此逻辑在 F07 的 AGENTS.md 指导中，是 agent 行为而非 Python 函数，因此更适合 adapter 结构检查）

**替代测试方法**：adapter 结构检查 — 扫描 AGENTS.md 或相关 Skill.md 是否同时包含 `status: interrupted` 和 `status: presented` 的区分说明，且频率保护计数规则明确排除 `interrupted`。

---

#### 场景 T-F10-10（P2）：跨会话转场的 memory 连续性

**目标**：验证 F05→F06 跨会话转场后，下次会话中可可能通过 memory_search 命中上次的情绪事件（"有分寸地关心"）。

**测试层级**：OpenClaw 多轮对话回测（两个独立 session）

Session A（写入 memory/）：用户完成一次 F05 情绪事件对话，对话结束，memory/YYYY-MM-DD.md 有记录。

Session B（新 session）：用户以日常信号开场（无情绪事件）

- **期望行为**：可可在 F06 自然陪伴模式中，通过 `memory_search` 命中上次情绪事件，自然提及（"上次说的那件事，后来怎么样了？"），而不是完全不知道上次发生了什么。
- **禁止出现**："你好，我是可可"（重新 onboarding）

---

#### 场景 T-F10-11（P2）：同一对话 Skill 计数跨旅程累积

**目标**：验证 F06→F05 转场后，Skill 计数从 F06 中延续，不重置。

**测试层级**：OpenClaw 多轮对话回测

轮次 1-2：F06 日常陪伴中已触发 diary Skill（第 1 个）
轮次 3：自然转到 F05（用户突然说出情绪事件）
轮次 4：F05 中尝试触发第 2 个 Skill
- **期望行为**：第 2 个 Skill 能正常触发（总计 2 个，未超上限）

轮次 5：用户情绪高唤醒，本应触发 breathing-ground（第 3 个）
- **期望行为**：breathing-ground 不触发（已达 2 个上限），可可用纯文字接住情绪

**验证关键**：Skill 计数是否真正跨旅程累积，而不是 F06→F05 切换时重置计数。

---

### 关键文件引用

- `/Users/jianghongwei/Documents/moodcoco/docs/product/product-experience-design.md`（F10 设计规格：7073-7503 行）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/weekly-reflection/scripts/weekly_review.py`（`detect_cross_week_pattern()` 函数：595-676 行；`write_weekly_cache()` 函数：960-1002 行；`_cleanup_old_caches()`：995-1002 行；`_fuzzy_match_theme()`：703-732 行）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md`（路由树：F10 §6 对应的 AGENTS.md 意图路由段，约 58-84 行；情绪稳定信号表：259-283 行；防死循环 / decision-cooling 优先级：377-399 行）
- `/Users/jianghongwei/Documents/moodcoco/docs/公众号/素材/v2-evolve-测试清单.md`（现有覆盖全景，F10 部分：172-178 行；所有已通过测试：244-356 行）