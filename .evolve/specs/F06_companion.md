## F06 日常陪伴 — 深度功能校验方案

---

### 需求摘要

F06 由三条并行机制驱动日常陪伴：

**Heartbeat（主会话）** 在 24h+ 无对话后主动发一条具体关怀消息，优先级顺序为：pending_followup 回访 > 时间胶囊到期 > 周日 20:00 回顾 > 常规关怀；触发后 48h 冷却。

**Cron（新会话，每日 21:30）** 发送日记提醒，触发前读取 USER.md 的 `## Cron 调度状态` 区块，按 5 字段状态机决定是否发送、是否跳过、是否进入暂停。状态机有三个终态：`active`、`paused`（3 天或 7 天）、`off`（用户主动关闭）。

**weekly_review.py（周日 exec 调用）** 读取本周 `diary/YYYY/MM/` 文件和 `memory/YYYY-MM-DD.md` 的 `## check-in` 块，加载 `emotion_groups.json` 的 6 族分类，输出 JSON，供 agent 生成情绪地图并引导消化。

核心数据流路径：用户对话 → check-in 写入 `memory/YYYY-MM-DD.md` → diary 写入 `diary/YYYY/MM/*.md` → weekly_review.py 读取两者 → 输出 JSON 含 emotion_summary / repeated_themes / growth_signals → agent 呈现 + 写入 `memory/weekly_cache/YYYY-WNN.json`。

---

### 已覆盖

当前测试体系（pytest 4 个 + adapter 9 项 + 对话 1 条）已覆盖以下内容：

**weekly_review.py 基础解析**
- `test_parse_checkins_from_memory`：正向验证 `## check-in` 块解析
- `test_parse_checkins_empty_dir`：空目录返回空列表
- `test_analyze_week_checkin_only`：只有 check-in 无 diary 时的周分析
- `test_analyze_week_no_data`：完全无数据返回 no_data 状态

**结构性校验**
- USER.md 含 `cron_state` 字段（adapter #39）
- USER.md 偏好字段含 ≥2 个英文 field name（adapter #40）
- weekly_review.py 含 `--memory-dir` 参数（adapter #41）
- `emotion_groups.json` 文件存在（adapter #42）
- AGENTS.md 含新用户过渡策略关键词（adapter #43）

**对话回测**
- F06 场景 10："今天吃了好吃的" → 闲聊自然，不触发呼吸/情绪急救 Skill

---

### 未覆盖

以下功能点无任何测试用例，属于真正的空白区：

**1. Cron 状态机 5 字段转换**：现有 adapter 只检查 `cron_state` 字段存在性，没有验证任何状态转移逻辑。连续 3 天未回复是否正确触发暂停、`pause_count` 是否正确递增、`pause_until` 是否写入正确日期、频率是否从 `daily` 降为 `every_2_days`、用户说"别提醒我了"是否将 state 置为 `off`——全部未测试。

**2. check-in 记录写入格式**：没有端到端测试验证 agent 执行 check-in 后，`memory/YYYY-MM-DD.md` 中是否真的出现 `## check-in` 块、四个字段是否齐全、source 是否正确标注 `heartbeat`/`cron`/`chat`。

**3. check-in 最多 3 轮限制**：没有多轮对话测试验证第 4 轮是否被截断，或深夜模式下 check-in 是否被降级。

**4. weekly_review 读取 diary + check-in 数据的整合**：现有 pytest 测试 `test_analyze_week_checkin_only` 只验证了纯 check-in 场景，没有测试 diary + check-in 混合时 source 字段是否正确区分、同一天多条 check-in 是否正确取最后一条。

**5. emotion_groups.json 的 6 族分类在 repeated_themes 中生效**：没有测试验证当情绪词是"紧张"而非"焦虑"时，weekly_review.py 是否正确将其归入焦虑族并计数。

**6. 偏好字段 6 个英文 field name 的完整 Schema**：adapter #40 只检查 ≥2 个，没有验证全部 6 个字段（`check_in_preference`、`diary_reminder_time`、`diary_reminder_status`、`heartbeat_preference`、`weekly_review_preference`、`growth_feedback_preference`）都存在且枚举值合法。

**7. 新用户过渡策略（对话次数 ≤5）**：adapter #43 只检查关键词存在，没有验证第 2 次对话时 Heartbeat/Cron 不触发、第 3 次后开始触发这一行为。

**8. growth_signals 检测逻辑**：四种信号（emotion_shift、topic_fade、new_positive、consistency）完全没有测试。

**9. weekly_cache 写入**：每次 weekly_review.py 执行后应写入 `memory/weekly_cache/YYYY-WNN.json`，没有测试验证该文件被正确创建和内容正确。

**10. Heartbeat 与 Cron 互斥规则**：同一天 Heartbeat 已发时 Cron 是否正确跳过，用户主动来聊后待发消息是否取消——没有任何测试。

**11. 连续拒绝降频规则**：用户连续 3 次拒绝周回顾 Poll 后，`weekly_review_refusal_count` 和 `weekly_review_downgrade_active` 是否被正确写入 USER.md，Heartbeat 是否改为隔周触发。

**12. Heartbeat 消息内容具体性**：常规关怀消息是否真的引用了 USER.md / people/*.md 的具体事件，而非发送"你还好吗"之类空洞内容——目前对话测试没有覆盖这一场景。

---

### 多轮测试场景

以下 9 个场景全部基于"验证功能真正生效"的原则设计，每个场景给出前置状态、输入序列、和需要直接检查的数据结果。

---

**场景 T01：Cron 状态机 active → paused（第一次暂停）**

前置：USER.md 中 `cron_state: active`、`consecutive_no_reply: 0`、`pause_count: 0`、`frequency: daily`

操作序列：
1. 模拟 Cron 触发（发送提醒消息）→ 用户无回复，session 超时
2. 重复上述步骤 3 次（连续 3 天不回复）

验证点：
- 读取 USER.md 的 `## Cron 调度状态` 区块
- `cron_state` 必须变为 `paused`
- `consecutive_no_reply` 必须为 3
- `pause_until` 必须等于触发日 + 3 天（不能是 null）
- `pause_count` 必须变为 1
- `frequency` 保持 `daily`（第一次暂停不降频）

---

**场景 T02：Cron 状态机 paused → active（自然恢复）**

前置：USER.md 中 `cron_state: paused`、`pause_until: 今天日期`（恰好到期）

操作序列：
1. 在 `pause_until` 当天触发 Cron

验证点：
- `cron_state` 必须变回 `active`
- `consecutive_no_reply` 必须归零
- Cron 正常发送提醒消息（不 SKIP）
- `pause_until` 必须变回 `null`

---

**场景 T03：Cron 状态机 active → off（用户主动关闭）**

前置：正常 active 状态

操作序列：
1. 用户在对话中说"别提醒我了"

验证点：
- 读取 USER.md 的 `## 偏好设置` 区块：`diary_reminder_status` 必须变为 `off`
- 读取 `## Cron 调度状态`：`cron_state` 必须变为 `off`
- 后续 Cron 触发时必须 SKIP，不发任何消息

---

**场景 T04：Cron 第二次暂停触发频率降级**

前置：USER.md 中 `cron_state: active`、`pause_count: 1`（已暂停过一次）、`frequency: daily`

操作序列：
1. 连续 3 天 Cron 触发，用户均无回复

验证点：
- `cron_state` 变为 `paused`
- `pause_until` 等于触发日 + 7 天（第二次暂停是 7 天，不是 3 天）
- `frequency` 必须变为 `every_2_days`（第一次和第二次不同）
- `pause_count` 必须变为 2

---

**场景 T05：check-in 完成后记录格式验证**

前置：正常对话中

操作序列：
1. Heartbeat 触发，附带 check-in 问"今天整体什么感觉？"
2. 用户选择"😢 有点低落"（或回答"有点难过"）
3. 可可问"怎么了？想说说吗？"
4. 用户说"不想说"
5. 可可收尾

验证点（直接读取文件）：
- `memory/YYYY-MM-DD.md` 中存在 `## check-in` 块
- `time` 字段格式为 `HH:MM`，且非空
- `emotion` 字段包含用户的原始情绪词（"有点低落"或"有点难过"），不能为空
- `source` 字段值为 `heartbeat`（不是 `cron` 也不是 `chat`）
- `note` 字段为空字符串（用户没有展开）

---

**场景 T06：check-in 最多 3 轮，第 4 轮截断**

前置：Cron 触发，进入 check-in 流程

操作序列：
1. 可可（第 1 轮）："今天怎么样？"
2. 用户："还行"
3. 可可（第 2 轮）："那挺好的。有什么开心的事吗？"
4. 用户："没什么事"
5. 可可（第 3 轮）收尾
6. 用户主动再问一句"那你觉得……"

验证点：
- 第 3 轮之后，若用户继续发消息，可可不再追问 check-in 相关问题
- 可可不对用户的追问重新启动 check-in 流程
- memory 文件中 check-in 块只有一条，不因用户追问而重复写入

---

**场景 T07：weekly_review.py 读取混合数据并正确归族**

前置：
- 本周 diary/ 有 3 条，情绪分别为"焦虑"、"紧张"（焦虑族）、"委屈"（悲伤族）
- memory/ 中有 2 条 check-in，情绪分别为"担心"（焦虑族）、"还不错"（开心族）

操作：
1. 直接执行 `python3 weekly_review.py <diary_dir> --memory-dir <memory_dir> --format json`

验证点（检查输出 JSON）：
- `emotion_summary` 中有 3 条 source=diary 条目和 2 条 source=check-in 条目，source 字段值正确区分
- `repeated_themes` 中焦虑族的 count 必须等于 3（焦虑 + 紧张 + 担心，语义合并）
- 悲伤族 count 等于 1（委屈）
- 开心族 count 等于 1（还不错）
- 焦虑族 count ≥ 3，触发重复主题（满足阈值条件）

---

**场景 T08：同一天多条 check-in，取最后一条**

前置：
- `memory/2026-03-30.md` 中包含两条 `## check-in` 块：第一条 `emotion: 有点烦`（time: 14:30），第二条 `emotion: 还不错`（time: 21:35）

操作：
1. 执行 weekly_review.py 读取该内存文件

验证点（检查 JSON 输出）：
- `emotion_summary` 中该日期只有一条条目（不是两条）
- 该条目的 `emotion` 值是"还不错"（最后一条），不是"有点烦"（第一条）
- `source` 为 `check-in`

---

**场景 T09：偏好字段写入 + 后续行为验证（多轮）**

前置：USER.md 偏好区块所有字段为默认值（normal/on）

操作序列：
1. 用户说"别老问我怎么样"
2. 可可回应"好，记住了"
3. 下一次 check-in 触发条件满足（Heartbeat 或 Cron）

验证点：
- 步骤 1 后，读取 USER.md 的 `## 偏好设置`：`check_in_preference` 必须变为 `dislike`（不能仍为 `normal`）
- 步骤 3 时，check-in 不被触发（agent 在触发前读取 `check_in_preference` 并 SKIP）
- 验证 6 个偏好字段均以英文 key 存储：`check_in_preference`、`diary_reminder_time`、`diary_reminder_status`、`heartbeat_preference`、`weekly_review_preference`、`growth_feedback_preference`——没有任何一个以中文 key 存在

---

### 关键发现

现有测试在 weekly_review.py 的**数据解析入口**覆盖尚可，但对其**下游功能正确性**缺乏验证：emotion_groups.json 加载后的族合并逻辑、同天多条 check-in 取最后一条的规则、growth_signals 四种检测规则，这些都是运行时真正产生错误的位置，目前没有任何 pytest 或 adapter 覆盖。

Cron 状态机是 F06 里唯一有复杂状态转移的组件（active/paused/off 三态、5 个字段联动），但目前对它的测试止步于"字段存在性检查"，没有验证任何转移条件。这是最高优先级的测试空白。

---

### 关键文件清单

- `/Users/jianghongwei/Documents/moodcoco/docs/product/product-experience-design.md`（第 3702-4763 行，F06 完整规格）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/AGENTS.md`（Cron 状态机定义于约 762-793 行，新用户过渡策略约 811-826 行）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/USER.md`（Cron 调度状态区块第 65-73 行，偏好设置区块第 55-63 行）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/check-in/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/weekly-reflection/SKILL.md`
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/weekly-reflection/scripts/weekly_review.py`（`_extract_checkin_blocks` 第 308-348 行，`parse_checkins_from_memory` 第 277-305 行，情绪族加载 `_load_emotion_groups` 第 68-82 行）
- `/Users/jianghongwei/Documents/moodcoco/ai-companion/skills/weekly-reflection/config/emotion_groups.json`
- `/Users/jianghongwei/Documents/moodcoco/docs/公众号/素材/v2-evolve-测试清单.md`（F06 现有覆盖在 adapter #39-43 和 pytest #30-33）