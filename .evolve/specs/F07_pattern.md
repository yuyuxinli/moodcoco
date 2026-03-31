## F07 模式觉察 — 深度功能校验方案

---

### 需求摘要

F07 是产品最核心的差异化旅程，依赖四层组件协同工作：

**触发层**：硬性前置条件（≥5次对话 + people/≥2段关系 + pattern_engine 返回≥1个匹配且≥2维度 + 情绪稳定≥3信号）+ 频率保护（`memory/pattern_log.md`，周上限2次、同一模式14天冷却、被拒30天冷却）。

**执行层**：7节点旅程（A接住当下 → B情绪稳定等待 → C模式桥梁 → D模式呈现 → E用户反应四分支 → F意义整合 → G未来锚定）。

**脚本层**：`pattern_engine.py` 负责跨关系匹配（时间/触发/反应/结果四维度），`growth_tracker.py` 负责 Innovative Moments 检测（5种IM类型）。

**呈现层**：Canvas 模式对比卡（卡片C，`pattern-comparison.html`）、Canvas 成长轨迹卡（卡片D，`growth-trajectory.html`），均需 agent 动态填充模板变量。

---

### 已覆盖

现有测试体系在以下层面有覆盖：

**脚本单元测试（pytest，8+8个）**

- `pattern_engine.py`：正向解析、文件不存在、格式错误不崩溃、两人触发关键词匹配返回跨关系结果、当前事件匹配历史模式、无匹配返回空
- `growth_tracker.py`：Action IM检测、Reflection IM检测、空/不存在目录返回空、反思型和行动型对比对匹配、两种类型对比对格式化为对话文本

**结构检查（adapter，2个）**

- Canvas 模式对比卡 HTML 文件存在
- Canvas 成长轨迹卡 HTML 文件存在

**对话回测（OpenClaw，1个）**

- F07场景11："他又不回我消息了" → 验证进入共情（单轮，无前置记忆数据）

---

### 未覆盖

以下是现有测试完全没有触及的功能关键路径，按严重程度排列：

**P0 级（功能正确性无法判断）**

1. `pattern_engine.py` 时间匹配维度（timing）从未有测试——现有8个pytest只测了trigger维度，timing 和 reaction 的跨关系匹配逻辑从未被专门验证
2. `pattern_engine.py` 的 `_build_spec_output` 输出格式从未测试——agent 实际使用的 JSON schema（`status/matches/evidence_a/evidence_b/dimension` 字段）正确性没有断言
3. `growth_tracker.py` 默认30天窗口过滤逻辑从未测试——`--since` 参数不传时的行为，以及时间窗口外的条目是否被正确过滤
4. Canvas 模式对比卡模板变量填充从未验证——HTML 文件存在只是结构检查，`{events_A}` `{events_B}` `{person_A}` 等占位符能否被 agent 从 pattern_engine 的 JSON 正确填充没有测试
5. Canvas 成长轨迹卡 IM 节点填充从未验证——`{im_nodes}` 的色标（5种IM类型对应颜色）和时间顺序有没有被正确生成没有测试

**P1 级（关键旅程节点缺失）**

6. 触发条件门槛联合检验——现有对话回测只发一条消息，不验证"≥5次对话 + ≥2段关系 + 模式匹配"三个条件必须同时满足才触发、缺一个就不触发的逻辑
7. 情绪稳定5信号≥3才进入节点C的判断逻辑——有定义没有测试
8. 三种桥梁策略（节点C）的选择优先级——策略1用户自发连接、策略2原话回响、策略3好奇提问的触发和互斥从未在对话层面验证
9. 节点E四分支路径——否认（E1）/惊讶（E2）/情绪淹没（E3）/好奇（E4）的不同处理路径，以及E3必须立刻停止且不再返回F07的硬规则，从未有对话级测试
10. 频率保护读取逻辑——agent 触发前必须读 `pattern_log.md` 检查周配额和冷却期，有没有真的被执行没有测试

**P2 级（降级路径和边缘场景）**

11. `pattern_engine.py` 执行失败时 agent 降级为手动读 people/*.md 定性比较的行为
12. `growth_tracker.py` 执行失败时 agent 降级路径
13. Canvas 渲染失败后降级为纯对话的行为
14. 封存关系（`当前状态：封存`）在模式对比卡中不显示真名、替换为"一段过去的关系"的逻辑
15. growth-story 的 ≥30天门槛检测——和 pattern-mirror 共享 `pattern_log.md` 的频率记录但 30天门槛从未被校验

---

### 多轮测试场景

以下场景需要多轮对话，且每个场景验证的是功能有没有生效，不是对话能不能发出去。

---

**场景 T1：pattern_engine 三维度匹配验证**

目标：验证跨关系匹配引擎能正确检测 timing + trigger + reaction 三个维度并返回正确 JSON schema。

前置数据准备：在 `ai-companion/memory/people/` 下创建两个测试档案，分别含有相同月份的退出信号（timing）、相同触发关键词（trigger）、相同反应关键词（reaction）。通过 CLI 直接调用验证：

```
python3 ai-companion/skills/diary/scripts/pattern_engine.py \
  --people-dir ai-companion/memory/people/ \
  --min-relations 2
```

验收标准：
- `status` 为 `ok`
- `matches` 数组包含至少一个 `dimension: "time"`、至少一个 `dimension: "trigger"`、至少一个 `dimension: "reaction"` 的条目
- 每个 match 的 `evidence_a.quote` 和 `evidence_b.quote` 不为空字符串，且来自对应档案的退出信号原话
- `person_a` 和 `person_b` 字段分别对应两个测试档案的文件名（不含.md）

验证 `insufficient_data` 分支：只提供一个档案时，`status` 必须为 `insufficient_data`，`matches` 为空数组。

---

**场景 T2：growth_tracker IM 节点完整性验证**

目标：验证五种 IM 类型都能被正确检测，且输出的 `innovative_moments` 数组字段完整，时间过滤逻辑正确。

前置数据准备：在 `ai-companion/memory/diary/` 创建测试日记文件，包含 action、reflection、protest、reconceptualization、performing_change 五种标记词，分布在30天内和30天外。

```
python3 ai-companion/skills/diary/scripts/growth_tracker.py \
  --diary-dir ai-companion/memory/diary/ \
  --people-dir ai-companion/memory/people/ \
  --user-file ai-companion/memory/USER.md \
  --im-types reflection,protest,action
```

验收标准：
- `status` 为 `ok`
- 30天外的条目不出现在 `innovative_moments` 中
- 每个节点包含 `type`、`date`、`quote`、`contrast_quote`（如有对比对）字段
- `contrast_pairs` 中 `reflection_growth` 类型的 `before.date` 早于 `after.date`
- 有 `action_growth` 类型时，`before` 字段允许为 `null`（设计规定）
- 测试 `--since` 参数传入指定日期，验证只返回该日期之后的节点

---

**场景 T3：Canvas 模式对比卡数据填充验证**

目标：验证 agent 能否从 pattern_engine 的 JSON 输出正确填充 `pattern-comparison.html` 的所有模板变量。

测试思路：给 agent 一个含有 pattern_engine JSON 输出的提示，要求生成对比卡 HTML，然后检查生成结果。

验收标准（对生成的 HTML 做字符串检查）：
- `{card_title}` 已被真实文本替换，不含花括号
- 左右两列分别对应 `person_a` 和 `person_b`，姓名已填入 `和{person_A}` 位置
- `{events_A}` 位置已展开为包含 `.event` div 的 HTML，且包含来自 `evidence_a.quote` 的用户原话
- `{events_B}` 同上，使用 `evidence_b.quote`
- 封存关系（当前状态为"封存"的档案对应人物）位置显示"一段过去的关系"而非真名
- `href` 的 Deep Link 格式正确：`openclaw://agent?message={url_encoded_text}`，`{cta_message}` 已被 URL 编码的真实文本替换

---

**场景 T4：Canvas 成长轨迹卡 IM 节点颜色和顺序验证**

目标：验证 `growth-trajectory.html` 的 `{im_nodes}` 被正确填充，每种 IM 类型对应正确色值，且节点按时间从旧到新排列。

验收标准（对生成的 HTML 做检查）：
- 出现 `reflection` 类型的节点时，对应 dot 颜色为 `#C5A3FF`
- 出现 `action` 类型时，颜色为 `#A8E6CF`
- 出现 `protest` 类型时，颜色为 `#FFD4A2`
- 出现 `reconceptualization` 类型时，颜色为 `#FF7F7F`
- 节点的日期属性从上到下单调递增（旧→新排列）
- 每个节点包含用户原话，不含可可的解读文字
- `{card_title}`、`{cta_text}`、`{cta_message}` 均无花括号残留

---

**场景 T5：触发条件门槛联合验证（多轮对话）**

目标：验证三个硬性条件必须同时满足，缺一个就不触发 F07。

设计三个 session，每个 session 缺一个条件：
- Session A：people/ 只有1段关系（缺"≥2段关系"），发送情绪触发消息 → 期望：不进入 F07，走正常 F05 共情
- Session B：对话次数为2次（缺"≥5次对话"），people/ 有2段关系 → 期望：同上
- Session C：people/ 有2段关系，对话次数≥5，但 pattern_engine 返回 `no_match` → 期望：同上
- Session D（正向）：三个条件全满足 + 触发词 → 期望：进入模式桥梁，出现"我注意到一个东西"或"你刚才说……"类话术

验收标准：Session A/B/C 的回复不出现任何跨关系比较话术；Session D 出现节点C的桥梁话术。

---

**场景 T6：节点 E 四分支路径验证**

目标：验证模式呈现后的四种用户反应各自走向正确分支。

在同一个已有足够数据的 session 上，先触发模式呈现，然后：

分支 E1（否认）：用户回复"我觉得这次不一样，阿轩不是那种人"
- 期望：可可回复含"也许确实不一样"，并追问"哪里不一样"
- 禁止：可可坚持模式、重复引用历史数据

分支 E2（惊讶）：用户回复"天，好像真的每次都这样"
- 期望：可可回复含"你现在是什么感觉"，不追加第二个模式
- 禁止：可可说"没错，你就是这样的人"、继续堆叠更多模式

分支 E3（情绪淹没）：用户回复"所以我就是这样的人，永远都学不会"
- 期望：可可回复含"看到重复不等于你有问题"、停止模式探索，同一对话不再出现跨关系分析
- 禁止：可可继续推进节点 F 的意义整合

分支 E4（好奇）：用户回复"为什么我每次都会这样"
- 期望：可可回复含"我不知道为什么，但我们可以一起看看"，用提问引导而非给答案
- 禁止：可可说"你可能是焦虑型依恋"或任何依恋类型标签

---

**场景 T7：频率保护 pattern_log.md 读写验证**

目标：验证频率保护逻辑真实生效，不是纸面规定。

步骤1：在一个符合条件的 session 触发模式呈现，验证 `memory/pattern_log.md` 被追加一条记录，格式符合规范（含日期、模式类型、status、cooldown_until）。

步骤2：在同一周内再次用相同数据触发，期望不再呈现同一模式，验证 `pattern_log.md` 中的冷却期被正确读取。

步骤3：模拟用户否认（E1分支），验证 `pattern_log.md` 记录的 `status: denied`，且 `cooldown_until` 为30天后。

步骤4：修改 `pattern_log.md` 中的 `cooldown_until` 为昨天，重新触发，验证冷却过期后可以再次呈现。

---

**场景 T8：growth-story ≥30天门槛和 pattern-mirror 协同验证**

目标：验证成长叙事触发的时间门槛，以及在 F07 节点 F 的 F-2 路径中两个 Skill 正确协同。

步骤1：USER.md 中首次对话日期设为今天（不满30天），发触发用户自我否定的消息，验证 growth-story 不触发，可可走 F-1 路径（纯模式探索，不呈现成长叙事对比）。

步骤2：将首次对话日期改为31天前，diary/ 中有 ≥2 周记录且包含对比节点，触发模式觉察旅程后进入节点 F，验证：
- `growth_tracker.py` 被调用
- 可可先说"你看到了一个重复的模式，可能心里不太好受"（承认情绪），再呈现前后对比
- 对比必须使用用户原话（从 diary/ 条目中提取），不含"你进步了"等空洞鼓励
- Canvas 成长轨迹卡被触发（macOS端）

步骤3：`growth_tracker.py` 返回 `no_growth_detected` 时，验证可可只走 F-1 路径，不勉强呈现空洞成长叙事。

---

**场景 T9：用户自己发现模式（最理想路径）验证**

目标：这是核心设计原则"用户自己发现而非 AI 告知"的关键验证。

在用户自己说出"好像每次都这样"或"以前也是这样"时（节点C策略1），验证：
- 可可不再使用策略3的"好奇提问"话术（"我能不能问你一个可能有点奇怪的问题"）
- 可可直接接住用户的自发连接，用"你说每次都这样，你记得上次是什么情况吗？"
- 不出现"获取许可"的环节（这个策略只有策略3需要）
- 整个模式呈现的发现权在用户手中，可可只是"跟着走"，不是"主导"

---

**场景 T10：降级路径端到端验证**

目标：`pattern_engine.py` 或 `growth_tracker.py` 执行失败时，用户无感知地降级。

方法：将脚本临时重命名或在测试环境中让其返回非零退出码，发送触发消息，验证：
- 可可不说任何技术细节（"脚本出错了"禁止出现）
- 可可通过 `memory_search` 或直接读 people/*.md 做定性比较，话术质量与脚本正常时基本相当
- Canvas 在 agent 无法生成 HTML 时回退到纯文字的两段关系叙述，不是空回复

---

### 测试实施优先级

| 优先级 | 场景 | 原因 |
|--------|------|------|
| P0 | T1（pattern_engine三维度）、T4（Canvas IM色标+顺序）、T3（Canvas填充）| 这是引擎层正确性，其他所有测试依赖它 |
| P1 | T5（触发条件门槛）、T6（E分支四路径）、T9（用户自己发现） | 旅程核心逻辑，直接影响体验质量 |
| P2 | T7（频率保护）、T8（30天门槛+协同）、T2（IM完整性）、T10（降级） | 边界条件和安全网 |

---

### 关键文件索引

- `/Users/jianghongwei/Documents/moodcoco/docs/product/product-experience-design.md`（第4764-5699行，F07完整设计规格）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md`（行为规则主文件，情绪稳定信号、四步框架、Skill触发映射）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/pattern-mirror/SKILL.md`（跨关系模式觉察Skill，Phase 1-7流程 + Canvas卡片C规则 + pattern_log格式）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/growth-story/SKILL.md`（成长叙事Skill，30天门槛 + 5种IM + Canvas卡片D规则）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/diary/scripts/pattern_engine.py`（跨关系匹配引擎，四维度匹配逻辑 + spec-compliant输出格式）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/diary/scripts/growth_tracker.py`（IM检测引擎，对比对生成 + 时间过滤 + spec输出）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/pattern-comparison.html`（模式对比卡模板，9个模板变量定义）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/canvas/growth-trajectory.html`（成长轨迹卡模板，5种IM色标 + im_nodes格式）
- `/Users/jianghongwei/Documents/moodcoco/docs/公众号/素材/v2-evolve-测试清单.md`（现有测试体系全景，F07仅2个结构检查+1个对话回测）