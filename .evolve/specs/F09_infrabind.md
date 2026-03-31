## F09 基础设施绑定 — 深度功能校验方案

### 需求摘要

F09 是一面镜子，不产生新功能，而是验证 F01-F03 三层基础设施在 F04-F08 五条旅程中是否被正确、完整、一致地调用。其核心问题不是"组件存在吗"，而是"组件之间的数据管道在运行时是否真正畅通"。

F09 识别出 7 条跨 Feature 不一致勘误，其中勘误 #5 是本测试方案的核心关注点：`weekly_review.py` 原本只有 `--diary-dir` 参数，缺少 `--memory-dir` 参数，导致 check-in 数据无法被纳入周回顾统计。这个参数已在实现中补入。

---

### 已覆盖

现有测试体系覆盖了以下内容（来源：`docs/公众号/素材/v2-evolve-测试清单.md`）：

**pytest 单元测试（第 1 层，4 个 weekly_review 用例）**

- test_parse_checkins_from_memory：验证从 `memory/YYYY-MM-DD.md` 解析 `## check-in` 块的正向路径。
- test_parse_checkins_empty_dir：空目录时返回空列表。
- test_analyze_week_checkin_only：仅有 check-in、无 diary 时能完成周分析（边缘场景）。
- test_analyze_week_no_data：完全无数据时的行为。

**adapter 结构检查（第 2 层，F09 专项 2 项）**

- weekly_review.py 源码含字符串 `--memory-dir`（关键词存在性）。
- weekly_review.py 源码含字符串 `--format` 和 `html`（关键词存在性）。

**对话回测（第 3 层，F09 仅 1 条）**

- 场景 13：用户说"今天吃了好吃的"，验证 F09 上下文下闲聊保持自然，无禁止词出现。这条测试和 F09 功能毫无关系，只是通用语气合规测试的占位。

---

### 未覆盖

以下是当前测试体系完全未触及的功能路径，按风险等级排列：

**1. --memory-dir 参数的端到端数据流通**

现有 pytest 只测试了 `parse_checkins_from_memory()` 函数本身的解析逻辑，没有测试：`--memory-dir` 参数从命令行传入 → `main()` 接收 → 传递给 `analyze_week()` → check-in 情绪计入 `cluster_counts` → 出现在 `repeated_themes` → 最终影响 `HTML` 色块。这是一条 7 步数据管道，中间任意一步断裂都不会有任何测试报错。

具体代码漏洞：`main()` 中第 1331 行的 `if not diary_files and not args.memory_dir` 逻辑：当 diary 为空但有 memory-dir 时，会继续执行而不是退出，这个分支在现有测试中从未用 CLI 方式触发。

**2. --format html 真实生成产物的内容校验**

adapter 只检查源码里有没有字符串 `html`。没有任何测试：
- 实际执行 `--format html` 后 HTML 文件是否真的写入到 `output_path`。
- HTML 色块是否包含来自 check-in 数据的情绪词（即 memory-dir 数据是否渗透到 HTML 产物）。
- 生成的 HTML 中 `openclaw://agent?message=` Deep Link 是否有效构造。
- HTML 标记中的 `<!-- WEEKLY_BARS -->` 和 `<!-- SUMMARY_ITEMS -->` 占位符是否被完整替换（未替换则 Canvas 展示空白）。

**3. Canvas 卡片 A（周情绪地图）与 design-guide.md 的一致性**

`design-guide.md` 规定了 5 条强制色值规范（暖白 `#FFF8F0`、暖灰 `#8B7E74`、珊瑚 `#FF7F7F` CTA 按钮、阴影 `rgba(255,180,150,0.15)`、圆角 ≥ 12px），以及禁止使用冷色系背景。但 `weekly_review.py` 内嵌的 `CANVAS_HTML_TEMPLATE` CTA 按钮颜色是 `linear-gradient(135deg, #FFD4A2 0%, #FFB74D 100%)`，与 design-guide.md 规定的 `#FF7F7F` 珊瑚色不一致。canvas 目录下 3 个 HTML 模板（farewell-memorial、growth-trajectory、pattern-comparison）全部使用 `#FF7F7F`，而卡片 A 的 CTA 使用暖黄渐变。没有任何测试检测这种跨卡片视觉一致性。

**4. 5 种 Canvas 卡片的变量占位符完整性**

卡片 C（pattern-comparison.html）有 8 个 `{变量}` 占位符（card_title, person_A, person_A_date, person_B, person_B_date, events_A, events_B, match_note, cta_text, cta_message），卡片 D（growth-trajectory.html）有 4 个，卡片 E（farewell-memorial.html）有 2 个（insights, archive_date），卡片 A（weekly_review.py 内嵌）用注释占位符替换。没有任何测试验证：agent 生成 HTML 时是否把所有占位符全部填满、有没有遗漏的 `{变量}` 原样输出到用户界面。

**5. HEARTBEAT 4 条 Cron 规则的优先级执行顺序**

`HEARTBEAT.md` 定义了严格的 4 条规则优先级（决策冷却回访 > 时间胶囊 > 周日回顾 > 日记提醒），且"同一次 Heartbeat 只执行一条规则"。没有任何测试验证：当规则 1 命中时规则 2/3/4 真的被跳过；当 `pending_followup.md` 有到期条目时，周日 20:00 时是否仍然正确执行规则 1 而不是规则 3。

**6. weekly_cache 跨周数据管道**

`cross_week_pattern` 功能依赖 `memory/weekly_cache/YYYY-WNN.json`。现有测试没有覆盖：本周执行后 `write_weekly_cache()` 写入的文件，是否在下次执行时能被 `_load_weekly_cache()` 正确读取并触发 `cross_week_pattern.detected == true`。这是一个需要两次独立执行才能验证的跨轮次数据管道。

**7. memory-dir 下 check-in 情绪词进入 repeated_themes 的阈值逻辑**

check-in 的情绪词通过 `WORD_TO_GROUP`（emotion_groups.json 的 6 族）而非 `WORD_TO_CLUSTER`（9 个扩展簇）映射。两个词典的覆盖范围不同：`WORD_TO_CLUSTER` 包含"崩溃"、"受不了"、"心碎"等口语词，`WORD_TO_GROUP` 只有严格的标准词。当用户 check-in 写了"崩溃"，它会出现在 `checkin_emotions` 中但不会匹配到 `group_counts`，从而不会触发 `repeated_themes` 中的情绪重复检测。这个行为是设计还是缺陷，没有任何测试标注。

---

### 多轮测试场景

以下 6 个场景是专为 F09 设计的深度功能校验，每个场景都需要构造特定的文件系统状态，多轮执行，验证真实产物而非中间代码。

---

**场景 T1：--memory-dir 端到端数据流通验证**

目标：验证 check-in 数据从磁盘文件到 repeated_themes 到 HTML 色块的完整管道。

第 1 轮 — 构造输入：在临时目录构造 `memory/` 下本周周一到周五各一个 `YYYY-MM-DD.md` 文件，每个文件包含规范的 `## check-in` 块，情绪字段全部写"焦虑"（共 5 次）。`diary/` 目录为空。

第 2 轮 — 执行 JSON 模式：运行 `python3 weekly_review.py <空diary目录> --memory-dir <memory目录> --format json`。

第 3 轮 — 验证 JSON 输出：检查返回 JSON 中 `entries` 字段是否等于 5（不是 0），`emotion_clusters.焦虑` 是否 ≥ 5，`repeated_themes` 中是否出现 type=emotion、word=焦虑族的条目（count ≥ 3）。如果 `entries` 是 0 或 `repeated_themes` 为空，说明 --memory-dir 数据流断裂。

第 4 轮 — 执行 HTML 模式：同样参数加 `--format html --output /tmp/test_t1.html`。

第 5 轮 — 验证 HTML 产物：打开 `/tmp/test_t1.html`，检查：(a) 文件确实存在且非空；(b) HTML 中包含颜色值 `#FFB74D`（焦虑簇对应的 CLUSTER_COLORS 橙色）；(c) `<!-- WEEKLY_BARS -->` 和 `<!-- SUMMARY_ITEMS -->` 这两个占位符字符串不出现在产物中（已被替换）；(d) `openclaw://agent?message=` Deep Link 字符串存在。

预期通过标准：所有 5 个检查点全部命中。

---

**场景 T2：diary + check-in 混合数据合并去重**

目标：验证同一天既有 diary 又有 check-in 时，diary 优先，check-in 不双计。

第 1 轮 — 构造输入：同一天（本周周三）同时在 `diary/YYYY/MM/YYYY-MM-DD.md` 写入情绪"难过"，在 `memory/YYYY-MM-DD.md` 写入 check-in emotion="开心"。

第 2 轮 — 执行并验证：运行带 --memory-dir 的 JSON 输出，检查 `daily.周三.source` 是否为 `diary`（而非 `check-in`），`daily.周三.primary_emotion` 是否为"难过"（diary 优先），`entries` 计数是否正确（check-in 当天不重复计入 diary 已有的天数）。

关键代码路径：`analyze_week()` 第 419 行 `if day_key not in daily` 才插入 check-in，是正确的"diary 优先"逻辑，但 `entries` 的计算是 `len(diary_files) + len(checkin_emotions)`，check-in 情绪词长度而非天数。需要验证这个计数逻辑在重叠天场景下是否符合 F09 §1.4 勘误 #5 中"check-in 记录仍计入 weekly_review.py 的数据统计"的意图。

---

**场景 T3：Canvas 卡片 A 与 design-guide.md 一致性检查**

目标：检测 weekly_review.py 内嵌 HTML 模板与 canvas/design-guide.md 规范的视觉偏差。

第 1 轮 — 生成产物：用任意有效数据生成 `--format html` 输出文件。

第 2 轮 — 规范比对（5 个检查点）：
- 检查 1：HTML 背景色是否使用 `#FFF8F0`（暖白）。实际：body 使用 `#FFF8F0`，card 使用 `#FFFFFF`——design-guide 规定卡片背景为暖白，card 使用纯白是否合规需要确认。
- 检查 2：正文文字色是否使用 `#8B7E74` 或 `#5D4E37`（实际模板用 `#5D4E37`，design-guide 规定暖灰 `#8B7E74`），这是已知偏差。
- 检查 3：CTA 按钮颜色，design-guide 规定 `#FF7F7F`（珊瑚），卡片 A 实际是 `linear-gradient(135deg, #FFD4A2 0%, #FFB74D 100%)`（暖黄）——与卡片 C/D/E 均使用 `#FF7F7F` 不一致。
- 检查 4：阴影是否包含 `rgba(255,180,150,0.15)`。
- 检查 5：圆角是否 ≥ 12px（卡片 A 为 20px，合规）。

预期：检查 2 和检查 3 当前会失败，需要确认是刻意设计差异（卡片 A 有独立语气）还是需要统一。

---

**场景 T4：Heartbeat 4 条 Cron 规则优先级多轮验证**

目标：验证"同一次 Heartbeat 只执行一条规则"的互斥逻辑在多种条件组合下均正确。

第 1 轮 — 规则 1 独占场景：构造 `memory/pending_followup.md` 包含一条已到期条目（scheduled_time 早于当前时间），同时构造 `memory/time_capsules.md` 包含一条到期胶囊，设置今天是周日。用多轮对话驱动 agent，发送空消息触发 Heartbeat，验证 agent 回复内容是回访（规则 1），而不是周回顾（规则 3）。

第 2 轮 — 规则 1 清零后规则 2 生效：用对话完成回访，确认 `pending_followup.md` 对应条目被删除。再次触发 Heartbeat，此时规则 1 无命中，验证 agent 执行时间胶囊提示（规则 2）而非周回顾（规则 3）。

第 3 轮 — 周日 20:00 规则 3 执行：构造无 pending_followup、无到期胶囊、本周 diary ≥ 3 条的场景，模拟周日触发，验证 agent 调用 `weekly-reflection` Skill 并尝试执行 `weekly_review.py`。

第 4 轮 — 互斥验证：在规则 3 执行完当天，再触发规则 4（21:30 日记提醒场景），验证 agent 不发第二条消息（周日互斥规则）。

这四轮测试需要通过 `openclaw agent --session-id <固定id>` 跨轮次保持状态，并在每轮之间手动修改 memory 文件状态。

---

**场景 T5：weekly_cache 跨周数据管道双轮验证**

目标：验证本周结果能被下周正确读取，并触发 `cross_week_pattern.detected == true`。

第 1 轮 — 写入上周缓存：在 `memory/weekly_cache/` 目录下手动创建上周标签文件（如 `2026-W13.json`），内容包含 `repeated_themes` 含一个 `type=emotion, word=焦虑族, count=4` 的条目。

第 2 轮 — 构造本周相同重复主题：在 diary 或 memory 中写入本周 ≥ 3 条焦虑情绪记录（使焦虑族在 `group_counts` 中 ≥ 3 次）。

第 3 轮 — 执行并验证 cross_week_pattern：运行带 `--memory-dir` 的 weekly_review.py，验证输出 JSON 中 `cross_week_pattern.detected` 为 `true`，`cross_week_pattern.themes[0].theme` 包含"焦虑"，`span_weeks` 为 2。

第 4 轮 — 验证 weekly_cache 写入：检查执行后 `memory/weekly_cache/` 目录下新增了本周缓存文件，文件内容包含正确的 `repeated_themes`。

第 5 轮 — 验证 agent 行为：通过对话回测，在 `cross_week_pattern.detected == true` 的情况下，确认 agent 的 weekly-reflection 回复中自然提及"这几周都在出现"的表述（J3→J4 转场入口），而不是只说"这周出现了"。

---

**场景 T6：脚本间数据管道完整性（pattern_engine → growth_tracker → weekly_review）**

目标：这 3 个脚本分别写入 `people/*.md`（pattern_engine）、读取 `diary/`（growth_tracker）、聚合 `diary/` + `memory/`（weekly_review），验证它们不互相污染、数据格式兼容。

第 1 轮 — pattern_engine 写入 people 文件：构造两个 people 文件含相同触发词，执行 `pattern_engine.py`，验证 JSON 输出中 `matches` 非空，随后 agent 将 `跨关系匹配段` 写入 people 文件。

第 2 轮 — growth_tracker 读取 diary：构造包含"第一次"和反思标记的 diary 文件，执行 `growth_tracker.py`，验证 IM 节点被正确提取，`format_for_conversation()` 输出的对比对文本用引号保留原话。

第 3 轮 — weekly_review 在 people 文件已被 pattern_engine 修改后的行为：pattern_engine 写入 people 文件的`跨关系匹配段`不是标准的 diary 六元组格式，验证 `parse_diary_entry()` 在遇到 people 目录下带匹配段的文件时不会崩溃（两个目录独立扫描，不互相混淆）。

第 4 轮 — weekly_review cross_check_people 与 pattern_engine 结果的人名一致性：验证 `cross_check_people()` 用于交叉匹配的 `people/` 目录内的文件名，与 `pattern_engine.py` 处理的文件名完全一致（大小写、空格），避免人名匹配失效导致 weekly_review 人物统计和 pattern_engine 模式匹配结果之间出现张力。

---

### 文件路径参考

- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/weekly-reflection/scripts/weekly_review.py` — 核心实现，测试的主要对象
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/weekly-reflection/config/emotion_groups.json` — 情绪族配置，T1/T7 测试的数据依赖
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/design-guide.md` — Canvas 视觉规范，T3 测试的比对基准
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/farewell-memorial.html` — 卡片 E，T3 用于卡片间一致性比对
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/growth-trajectory.html` — 卡片 D，T3 同上
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/pattern-comparison.html` — 卡片 C，T3 同上
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/HEARTBEAT.md` — 4 条 Cron 规则定义，T4 测试的行为规范
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md` — Canvas 调用命令（第 1216 行）、故障降级规则
- `/Users/jianghongwei/Documents/moodcoco/docs/product/product-experience-design.md` 第 6555-7072 行 — F09 完整设计规格，7 条勘误表
- `/Users/jianghongwei/Documents/moodcoco/docs/公众号/素材/v2-evolve-测试清单.md` — 现有 88 项自动化测试清单，本方案的起点