## F02 交互系统 — 深度功能校验方案

---

### 需求摘要

F02 交互系统是可可的"表达层"，定义了 agent 在何时用什么形态说话：纯文字、Canvas 可视化卡片、Poll 结构化选择、图片仪式化载体、exec 后台脚本。核心规格包含：

- **5 种 Canvas 卡片**（A-E）：各有独立触发条件、数据源、生成脚本、HTML 模板
- **3 种 Poll 场景**（P1-P3）：告别仪式选择、日记情绪精细化、Skill 多选引导
- **一棵交互形态决策树**：情绪高峰优先级最高，依次判断数据量、选择需求、仪式时刻、后台计算
- **渐进解锁机制**：第 1/3/10/15/30 次对话对应不同的可用交互形态
- **Canvas 降级策略**：非 macOS 端全部降级为自然语言，用户无感知

---

### 已覆盖

现有测试对 F02 的覆盖集中在**结构存在性检查**，3 项 adapter 检查点：

| 检查点 | 检查方式 | 问题 |
|--------|---------|------|
| diary SKILL.md 含 Poll 情绪精细化配置 | 关键词匹配 "Poll" + "情绪/精细" | 只检查关键词存在，不验证配置内容正确性 |
| AGENTS.md 含交互形态决策树 | 关键词匹配 "交互形态/决策树" | 只验证文字存在，不验证决策逻辑是否走对分支 |
| Canvas 设计语言定义存在 | canvas/design-guide.md 含色值 | 只验证文件存在，不验证模板变量填充是否正确 |

第 3 层 OpenClaw 对话回测中 F02 只有 1 条场景（场景 4："今天吃了好吃的" → 闲聊保持自然），验证的是**不触发**的负向路径，没有一条验证 Canvas/Poll/图片**实际生成**的正向路径。

---

### 未覆盖

以下是 F02 的功能盲区，现有测试完全未触及：

**Canvas 卡片生成**
- 卡片 A（周情绪地图）：weekly_review.py 有 4 个 pytest 但只测数据解析，没有测 HTML 是否生成、Canvas 是否呈现、数据是否正确注入模板
- 卡片 B（关系时间线）：无任何测试——无 pytest、无 adapter 检查、无 OpenClaw 对话回测
- 卡片 C（模式对比卡）：adapter 仅检查 HTML 文件存在，未验证 `{events_A}` `{events_B}` `{cta_message}` 等模板变量是否被实际填充
- 卡片 D（成长轨迹卡）：adapter 仅检查 HTML 文件存在，未验证 `{im_nodes}` 的 IM 类型色标映射是否正确（Action→薄荷、Reflection→薰衣草 等）
- 卡片 E（告别纪念卡）：adapter 仅检查 HTML 文件存在，未验证 `{insights}` 是否真正去名字化、`{archive_date}` 是否正确

**Poll 行为**
- P1 告别仪式选择：只有 pytest 验证 archive_manager 的 `burn_belief_ritual` 执行，没有测 Poll 配置是否正确发出（pollMulti 是否为 false，4 个选项是否完整）
- P2 情绪精细化选择：adapter 只检查关键词存在，未验证 pollMulti 是否为 true（多选是 P2 的关键特性）
- P3 Skill 引导选择：完全没有覆盖，无任何层级的测试
- Poll 结果写回记忆：情绪选择写入 diary/.md、仪式选择写入 people/.md、Skill 选择写入 memory/ 这三条写回路径均未测试

**交互形态决策树**
- 情绪高峰时强制纯对话（最高优先级）：没有测试验证"用户正在倾诉时 agent 不发 Canvas/Poll"
- 渠道检测逻辑：macOS 发 Canvas、非 macOS 降级为文字，这个渠道判断分支完全未覆盖
- 深夜模式（22:00-06:00）禁止 Poll：AGENTS.md 明确定义深夜不触发情绪精细化 Poll，但没有测试验证这条规则
- 决策树的顺序优先级：数据量判断在选择需求判断之前，这个顺序是否被 agent 正确执行没有验证

**渐进解锁机制**
- 第 1 次对话只能纯对话（无 Poll）：未测试
- 第 3 次对话解锁 Poll：未测试 "第 3 次对话时 Poll 能触发、第 1 次不能"
- 第 10 次解锁 Canvas（周情绪地图）：未测试
- 第 15 次解锁关系时间线和模式检测：未测试
- 数据不足时的自然降级（空 Canvas 不发出）：未测试

**降级策略**
- Canvas 不可用时的文字降级内容：5 种卡片的降级文字模板均未验证语气和数据一致性
- exec 脚本失败时 Canvas 路径的降级：只测了脚本返回空的情况，没测"脚本成功但 Canvas present 失败"的降级
- 降级时"不说无法展示卡片"的语气约束：未验证

**图片生成**
- ritual_image.py 和 milestone_image.py：无任何测试（F02 新增脚本，F01 测试清单不覆盖）
- 图片生成失败时的文字降级：未测试

**Deep Link 回调**
- Canvas 卡片内的 CTA 按钮点击后 agent 收到消息并正确继续对话：完全未测试

---

### 多轮测试场景

以下 12 个场景专门覆盖上述盲区。每个场景都不是"能不能发消息"，而是验证特定功能是否生效。

---

**场景 T01：Canvas 卡片 A 的数据注入正确性**

场景名：周情绪地图数据绑定验证

前置条件：
- workspace 中预置本周（周一至周六）的 6 条 diary/*.md，包含已标注情绪词（"焦虑""委屈"各 3 次）、人物标签（"小凯" 4 次），以及至少 1 个明确触发（"已读不回"）
- 当前渠道为 macOS 桌面端
- 模拟 Heartbeat 触发（周日 20:00）或直接发送"可以帮我看看我这周的心情吗"

对话轮次：
1. 用户发送触发消息
2. Agent 调用 exec 运行 weekly_review.py
3. Agent 调用 canvas present 展示卡片

验证点：
- exec 返回的 JSON 中 `emotion_counts` 字段包含 "焦虑:3"，不是凭空生成
- Canvas HTML 的 `{weekly_entries}` 中每天情绪色块深浅与 diary 数据的情绪强度匹配（情绪词多的那天色块更深）
- 最常出现的情绪词"焦虑"在卡片中被放大，"小凯"出现在人物标签区
- 卡片标题用可可语气（"你这周的心情地图"），不是"情绪分析报告"
- CTA 按钮存在，href 为 `openclaw://agent?message=...`，消息内容与周回顾相关

---

**场景 T02：Canvas 卡片 A 的降级路径**

场景名：非 macOS 渠道的周回顾降级

前置条件：
- 与 T01 相同的 diary 数据
- 当前渠道为 Telegram（非 macOS 桌面端）
- 用户发送"可以帮我看看我这周的心情吗"

对话轮次：
1. 用户触发请求
2. Agent 检测渠道 → 非 macOS → 不调用 canvas present

验证点：
- Agent 回复中无任何 Canvas 相关命令
- 回复包含文字形式的周回顾，内容包含情绪词频（"这周你提到了 3 次焦虑"）和人物标注（"3 次和小凯有关"）
- 回复语气保持口语化（"你这周…"），不变成报告体
- 数据内容与 T01 中 Canvas 数据来源一致（同样来自 diary，不是随机生成）

---

**场景 T03：Canvas 卡片 C 的模板变量填充**

场景名：模式对比卡双列时间线填充验证

前置条件：
- people/ 目录有 2 个文件：小凯.md、小明.md（各含退出信号段、关系阶段段、至少 3 个事件记录）
- 两段关系在第 3 个月均有"他好像没那么在乎我了"类似描述（用于匹配）
- pattern_engine.py 已有匹配结果 JSON 可返回
- 当前渠道 macOS 桌面端
- 情绪稳定信号 ≥3 个已出现

对话轮次：
1. 用户提到退出意图："我和小凯现在这样，感觉和以前小明那次一样"
2. Agent 判断需要模式对比，调用 exec pattern_engine.py
3. Agent 根据匹配结果填充 pattern-comparison.html 模板变量
4. Agent 调用 canvas present 展示

验证点：
- pattern-comparison.html 中 `{person_A}` 为"小凯"，`{person_B}` 为"小明"（不是占位符）
- `{events_A}` 中包含小凯关系中的实际事件，不是空块
- `{events_B}` 中包含小明关系中的实际对应事件
- `{match_note}` 有实际说明文字
- `{cta_message}` URL 编码后解码内容与这段模式相关（不是空字符串）
- 模板中无未替换的 `{变量名}` 占位符残留

---

**场景 T04：Canvas 卡片 D 的 IM 类型色标映射**

场景名：成长轨迹卡 IM 节点颜色正确性

前置条件：
- diary/ 中有 ≥2 周数据
- growth_tracker.py 能返回至少 2 个 IM，类型分别包含 Action（薄荷 #A8E6CF）和 Reflection（薰衣草 #C5A3FF）
- 用户处于自我否定 + 对话次数 ≥30 的状态

对话轮次：
1. 用户说"我怎么每次都这样，是不是我天生不适合谈恋爱"
2. Agent 触发 growth-story skill，调用 growth_tracker.py
3. Agent 填充 growth-trajectory.html，展示成长卡

验证点：
- HTML 中 Action 类型节点的圆点颜色为 `#A8E6CF`，Reflection 类型为 `#C5A3FF`（不是统一颜色）
- `{im_nodes}` 中用户原话引用是真实的 diary 原文，而不是 agent 自行总结的话
- 时间线方向从旧到新，第一个 IM 时间早于最后一个 IM 时间
- `{card_title}` 使用可可语气而非报告体

---

**场景 T05：Canvas 卡片 E 的去名字化验证**

场景名：告别纪念卡 insights 匿名化

前置条件：
- people/小凯.md 存在，含"小凯"这个名字的关系记录
- 执行完整告别仪式（Path B 仪式化封存）流程到 Phase 4
- archive_manager.py 返回 pattern_insights 数组
- 渠道 macOS 桌面端

对话轮次：
1-N. 完整走完 farewell skill 的仪式流程
N+1. Agent 根据 insights 填充 farewell-memorial.html

验证点：
- farewell-memorial.html 的 `{insights}` 内容中不含"小凯"这个名字（已去名字化）
- insights 条数在 2-3 条之间（规格要求）
- `{archive_date}` 是实际封存日期（格式 YYYY-MM-DD），不是占位符
- 卡片底部文字"这段关系被认真地送走了。"出现
- 整张卡片无未替换的 `{变量名}` 占位符

---

**场景 T06：Poll P1 告别仪式选择的配置正确性**

场景名：告别 Poll 配置参数与选项完整性

前置条件：
- 已有 people/小凯.md 存在
- 用户表达告别意图："我想跟小凯的这段关系说再见了"
- 渠道支持 Poll（Telegram）

对话轮次：
1. 用户发送告别意图消息
2. Agent 读取 farewell SKILL.md，进入告别流程
3. Agent 发出 Poll

验证点：
- Poll 配置中 `pollMulti` 为 `false`（单选，不是多选）
- 选项数量恰好为 4 个（不多不少）
- 4 个选项内容匹配规格：烧掉日记、烧掉信念、时间胶囊、未寄出的信
- `pollQuestion` 与规格一致（"你想用什么方式跟这段关系告别？"）
- 用户选择后，agent 不追问"为什么选这个"
- 用户选择写入 people/小凯.md 头部 `告别方式: {选项} | {日期}`

---

**场景 T07：Poll P2 情绪精细化的多选特性**

场景名：情绪命名 Poll 的 pollMulti=true 及结果写回

前置条件：
- 用户说"就是……不知道怎么说，就很不舒服"（低置信度情绪信号）
- 渠道支持 Poll（Telegram）
- 非深夜时段（08:00-21:59）

对话轮次：
1. 用户发出模糊情绪表达
2. Agent 判断低置信度 → 触发情绪精细化 Poll
3. 用户选择多个情绪词（如"委屈"+"害怕"）
4. Agent 接纳选择，继续对话

验证点：
- Poll 配置中 `pollMulti` 为 `true`（允许多选，这是 P2 的核心特性）
- 选项数量在 3-4 个（规格要求），最后一个选项为兜底的"说不清"
- 用户多选后，agent 能同时处理两个情绪词，不只处理第一个
- 选择结果写入当日 diary/*.md 的情绪字段（不是只接收不写入）
- 同一次对话内 P2 Poll 只触发 1 次（规格硬规则：每次对话最多 1 次情绪 Poll）

---

**场景 T08：深夜禁止 Poll 规则**

场景名：深夜模式下 P2 情绪 Poll 不触发

前置条件：
- envelopeTimestamp + userTimezone 对应当前时间为 23:30（深夜模式）
- 用户发出与 T07 相同的模糊情绪表达："就是……不知道怎么说，就很不舒服"

对话轮次：
1. 用户发出模糊情绪表达
2. Agent 检测深夜模式
3. Agent 回应

验证点：
- Agent 回复中无任何 Poll 配置（无 `"action": "poll"` 的工具调用）
- Agent 回复是浅层情绪接住（不深挖），语气更轻柔（如"这个时间还没睡，一定很不好受"）
- Agent 不进行情绪精细化，不问"你是烦他还是害怕"
- 回复中无"你为什么"类的原因探询

---

**场景 T09：交互形态决策树——情绪高峰强制纯对话**

场景名：情绪高峰时 Canvas/Poll 均不触发

前置条件：
- 用户处于情绪高峰状态（连续多条短消息、感叹号、哭泣描述）
- workspace 中有足够数据本可触发 Canvas（有本周 diary 数据）
- 渠道为 macOS 桌面端（Canvas 理论上可用）

对话轮次：
1. 用户连续发送："他怎么可以这样！！""我好难受""他根本不在乎我"
2. Agent 判断情绪高峰状态

验证点：
- Agent 回复中无 Canvas present 调用
- Agent 回复中无 Poll 配置
- Agent 回复中无 exec 调用（不跑后台脚本）
- Agent 只进行纯文字情绪接住
- 这条规则在决策树中是最高优先级，验证它能覆盖所有其他判断分支

---

**场景 T10：渐进解锁——新用户不触发 Poll**

场景名：第 1 次对话中情绪模糊时的降级

前置条件：
- 全新 workspace，无 diary/ 数据，无 people/ 文件
- USER.md 中对话次数记录为 0 或 1
- 用户说"就是……不知道，有点烦"（低置信度情绪信号）
- 渠道支持 Poll

对话轮次：
1. 用户发出模糊情绪
2. Agent 检测对话次数为 1，Poll 功能尚未解锁（第 3 次才解锁）

验证点：
- Agent 不发出 Poll（即使渠道支持，即使情绪低置信度）
- Agent 改用文字方式辅助情绪命名（"那种不舒服更像什么？是闷闷的，还是慌慌的？"）
- 对话保持纯文字，无任何工具调用

---

**场景 T11：Poll 文字输入 fallback——用户绕过 Poll 直接回复**

场景名：Poll 外直接打字时的意图识别

前置条件：
- Agent 已正确发出 P1 告别仪式 Poll（4 个选项）
- 渠道为 Telegram

对话轮次：
1. Agent 发出告别仪式 Poll
2. 用户不选 Poll，直接发文字："我想写封信给他"

验证点：
- Agent 识别"写封信给他"等价于 Poll 选项"未寄出的信"
- Agent 进入"未寄出的信"仪式流程（不重发 Poll，不说"请在 Poll 里选"）
- 后续写入 people/*.md 的告别方式字段记录为"未寄出的信"，不是空

---

**场景 T12：exec 图片生成失败的降级**

场景名：ritual_image.py 失败时仪式对话不中断

前置条件：
- 用户已完成告别仪式流程，选择"烧掉日记"
- 模拟 ritual_image.py 失败（可临时将脚本替换为返回 `{"status": "error", "error": "PIL not available"}` 的版本）

对话轮次：
1. Agent 调用 exec ritual_image.py
2. 脚本返回 error 状态
3. Agent 处理失败

验证点：
- Agent 回复中无错误堆栈、无"PIL not available"、无任何技术细节
- Agent 不说"脚本出错了"或"图片生成失败"
- 仪式对话正常继续（用文字描述替代视觉，如"烧掉了。从现在起，这些不再是你的负担。"）
- 告别仪式主流程（写入 people/.md、触发后续对话）不受图片失败影响

---

### 补充说明

以下是这 12 个场景覆盖的功能矩阵和测试优先级：

| 场景 | 优先级 | 覆盖功能 | 验证的核心问题 |
|------|--------|---------|--------------|
| T01 | P0 | Canvas A 数据注入 | 数据有没有从 diary 真实流入卡片 |
| T02 | P0 | Canvas 降级语气 | 降级后是否保持口语化，数据是否一致 |
| T03 | P0 | Canvas C 模板填充 | 有没有残留 `{变量名}` 占位符 |
| T04 | P1 | Canvas D IM 色标 | 不同 IM 类型是否对应正确颜色 |
| T05 | P0 | Canvas E 去名字化 | insights 有没有泄露具体人名 |
| T06 | P0 | Poll P1 配置 | pollMulti 是否为 false，选项是否完整 |
| T07 | P0 | Poll P2 多选 | pollMulti 是否为 true，结果写回 |
| T08 | P0 | 深夜禁 Poll | 深夜规则是否覆盖常规 Poll 触发 |
| T09 | P0 | 决策树最高优先级 | 情绪高峰时有没有"漏发" Canvas/Poll |
| T10 | P1 | 渐进解锁 | 新用户有没有被过早触发高级功能 |
| T11 | P1 | Poll fallback | 绕过 Poll 时意图识别是否有效 |
| T12 | P1 | 图片生成降级 | 脚本失败有没有暴露技术错误 |

T09 是整个 F02 最高优先级的测试，因为"情绪高峰永远纯对话"是一条跨功能的安全规则，一旦失效会导致用户在最脆弱的时刻被打断。T05 的去名字化验证是隐私安全关键点，告别纪念卡展示的 insights 如果意外保留人名会造成情感伤害。T03 的模板变量残留检查是最容易被忽视但实际上在工程上最常出问题的地方。

---

**关键文件参考**

- `/Users/jianghongwei/Documents/moodcoco/docs/product/product-experience-design.md` 第 789-1481 行（F02 完整规格）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md` 第 140-185 行（情绪 Poll 触发逻辑）、第 410-431 行（深夜特殊规则）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/design-guide.md`（色彩和布局规范）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/farewell-memorial.html`（卡片 E 模板变量定义）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/growth-trajectory.html`（卡片 D IM 色标定义）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/pattern-comparison.html`（卡片 C 双列模板变量）
- `/Users/jianghongwei/Documents/moodcoco/docs/公众号/素材/v2-evolve-测试清单.md`（现有测试覆盖范围）