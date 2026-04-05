# 记忆功能 + 系统融合验证 POA

*2026-04-05 | 蒋宏伟 → 毅卓团队（毅卓/怀宽/才学）*

## 一、背景

本次迁移涉及 259 个文件、49000+ 行改动，包括：
- workspace 合并（ai-companion + kaoyan-companion 统一底座）
- 三层 skill 路由方案
- 全部文件操作改为 Service Tool
- 自助课迁移到 selfhelp 入口
- 趣味测试独立为第四入口
- 新增 FORMAT_MINIPROGRAM.md（小程序输出格式规范）

**业务层（AGENTS.md + Skills）之前已通过 V3 全部 11 个 Feature 测试。但底层接口、数据库写入/读取、跨 Tab 数据通道在迁移后需要重新验证。**

---

## 二、人员分工

| 人 | 负责范围 | 重点 |
|---|---------|------|
| **毅卓** | 心情可可 Tab + "我的" Tab | 记忆写入/读取、Service Tool 稳定性、人物档案、日记生成 |
| **怀宽** | 成长 Tab | 课程流程、selfhelp 迁移后是否跑通 |
| **才学** | 成长 Tab + 考研 6 个 skill | 考研 skill 数据落库、跨 Tab 记忆互通 |
| **全员交叉** | 跨 Tab 验证 | 三人各跑一个端到端场景（见第五节） |

---

## 三、底层数据流（时序图）

### 3.1 单次对话完整链路

```
用户                小程序前端        OpenClaw 路由       Agent               Service Tool         数据库
 │                    │                 │                  │                    │                   │
 │── 发消息 ────────→│                 │                  │                    │                   │
 │                    │── API ────────→│                  │                    │                   │
 │                    │                 │── 路由 ────────→│                    │                   │
 │                    │                 │                  │                    │                   │
 │                    │                 │                  │── memory_search()→│── 查 memory 索引 →│
 │                    │                 │                  │←── 历史片段 ──────│←── 返回 ─────────│
 │                    │                 │                  │                    │                   │
 │                    │                 │                  │── user_profile    │                   │
 │                    │                 │                  │   _get() ────────→│── 查 user 表 ───→│
 │                    │                 │                  │←── 用户档案 ──────│←── 返回 ─────────│
 │                    │                 │                  │                    │                   │
 │                    │                 │                  │── person_get      │                   │
 │                    │                 │                  │   ("妈妈") ──────→│── 查 people 表 ──│
 │                    │                 │                  │←── 人物档案 ──────│←── 返回 ─────────│
 │                    │                 │                  │                    │                   │
 │                    │                 │                  │ [Skill 路由执行]   │                   │
 │                    │                 │                  │                    │                   │
 │←── ai_message() ──│←── 返回回复 ────│←─────────────────│                    │                   │
```

### 3.2 告别时强制写入（RULE-ZERO，最高优先级）

```
用户说"晚安"       Agent                             Service Tool             数据库
 │                  │                                   │                      │
 │                  │── ⚠️ 检测到告别词                  │                      │
 │                  │                                   │                      │
 │                  │── user_profile_get() ────────────→│── 读 user 表 ───────│
 │                  │←── 返回当前档案 ─────────────────│                      │
 │                  │                                   │                      │
 │                  │── user_profile_update             │                      │
 │                  │   (patch="## 核心困扰\n...") ───→│── 写 user 表 ───────│
 │                  │   7字段: 称呼/困扰/模式/方法      │                      │
 │                  │          /触发/关系/洞察           │                      │
 │                  │                                   │                      │
 │                  │── person_update                   │                      │
 │                  │   ("妈妈", patch="...") ─────────→│── 写 people 表 ─────│
 │                  │   （如对话中提到了人物）            │                      │
 │                  │                                   │                      │
 │                  │── 🔑 全部 tool call 完成后         │                      │
 │                  │      才生成告别文字                 │                      │
 │←── "晚安~" ─────│                                   │                      │
```

### 3.3 日记写入链路

```
对话结束后          Agent (farewell skill)            Service Tool             数据库
 │                  │                                   │                      │
 │                  │── diary_write                     │                      │
 │                  │   (date="2026-04-05",             │                      │
 │                  │    entry="六元组内容") ──────────→│── 写 diary 表 ──────│
 │                  │                                   │                      │
 │                  │── ✅ 验证：diary_read             │                      │
 │                  │   (date="2026-04-05") ──────────→│── 读 diary 表 ──────│
 │                  │←── 返回刚写的内容 ───────────────│                      │
```

### 3.4 ⚠️ 跨 Tab 数据流（当前状态：待确认）

```
成长课程 Tab                    数据库                      聊天 Tab
(course-dialogue)                                           (ai-companion)
     │                            │                              │
     │── 用户做了焦虑评估         │                              │
     │   diary_write? 还是        │                              │
     │   独立的 course 表?        │                              │
     │── ???????? ──────────────→│                              │
     │                            │                              │
     │                            │    ❓ 关键问题：              │
     │                            │    两个 Tab 共享同一个        │
     │                            │    user_profile 吗？          │
     │                            │    memory_search 能搜到       │
     │                            │    成长课的数据吗？            │
     │                            │                              │
     │                            │                         ──→ │── memory_search()
     │                            │                              │   能否命中成长课数据？
```

---

## 四、Service Tool 清单 + 验证要点

### 4.1 数据 Service Tool（7 个）

| Tool | 读/写 | 参数 | 数据格式 | ⚠️ 验证要点 |
|------|-------|------|---------|------------|
| `user_profile_get()` | 读 | 无 | Markdown（7字段：称呼/困扰/模式/方法/触发/关系/洞察） | 返回格式是否完整？字段是否都在？ |
| `user_profile_update(content/patch)` | 写 | content=覆写, patch=追加 | 同上 | **patch 是追加还是覆写？连续两次 patch 同一字段会不会丢数据？** |
| `person_get(name)` | 读 | name=人物名 | Markdown（关系类型/状态/阶段/感受/模式/事件/退出信号/跨关系匹配） | 人物不存在时返回什么？空字符串？null？错误？ |
| `person_update(name, content/patch)` | 写 | name + content=覆写/新建, patch=追加 | 同上。`[archived]`=封存, `[deleted]`=删除 | **新建时格式是否跟模板一致？** |
| `memory_search(query)` | 读 | query=关键词 | 返回匹配片段 | **索引范围包括哪些？diary + people + memory？成长课数据在不在索引里？** |
| `diary_read(date/list_month)` | 读 | date=指定日期, list_month=列月目录 | Markdown（六元组） | list_month 是否包含成长课产生的日记？ |
| `diary_write(date, entry)` | 写 | date + entry | Markdown 追加 | 同一天多次写入是否追加而非覆写？ |

### 4.2 高级分析 Tool（2 个，可失败降级）

| Tool | 功能 | 降级方案 | ⚠️ 验证要点 |
|------|------|---------|------------|
| `pattern_match(...)` | 跨关系模式匹配 | 降级为 person_get 手动对比 | **降级路径是否真的能跑通？用户无感知？** |
| `growth_track(since, im_types, format)` | 创新时刻检测 | 降级为 memory_search 时间线对比 | 同上 |

### 4.3 UI Tool（5 个，不涉及数据持久化）

| Tool | 功能 | 验证要点 |
|------|------|---------|
| `ai_message(content, emotion, ...)` | 发送消息到前端 | 格式是否符合 FORMAT_MINIPROGRAM.md |
| `ai_options(options)` | 展示选项卡 | 选项点击后是否正确回传 |
| `ai_mood_select(...)` | 情绪签到组件 | 签到结果是否写入 user_profile |
| `ai_mood_recovery(...)` | 情绪恢复组件 | 同上 |
| `ai_safety_brake(...)` | 安全制动 | 是否正确触发转介流程 |

---

## 五、测试矩阵

### 5.1 毅卓：心情可可 Tab + "我的" Tab

#### A. 记忆时间维度（跨 session 连续性）

| # | 测试案例 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|
| T1 | 基础记忆 | 第 1 次对话提到男友叫小白 → 告别 → 第 2 次打开 | 可可知道男友叫小白，开场白提到 | |
| T2 | 人物档案持久化 | 第 1 次提到小白 → 告别 → 检查 person_get("小白") | 返回完整人物档案，格式正确 | |
| T3 | 用户档案更新 | 连续 3 次对话，每次更新不同字段 → user_profile_get() | 3 次更新都保留，没有互相覆盖 | |
| T4 | 日记连续 | 连续 3 天对话 → diary_read(list_month="2026-04") | 列出 3 条日记，日期正确 | |
| T5 | 多人物档案 | 提到妈妈、男友、室友 3 个人 → 分别 person_get | 3 个独立档案，格式一致 | |

#### B. 跨模式维度（模式洞察）

| # | 测试案例 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|
| T6 | 模式识别 | 第 1 次跟妈妈吵架因为成绩 → 第 3 次又因为成绩 | 可可主动说"我发现每次都跟成绩有关" | |
| T7 | 模式日志写入 | 可可呈现跨关系模式后 → user_profile_get() | 模式日志段有记录，含日期和冷却期 | |
| T8 | 模式频率保护 | 呈现模式后 14 天内再次触发 | 可可不重复呈现（冷却期保护） | |
| T9 | pattern_match 降级 | 故意让 pattern_match 超时 | 降级为 person_get 对比，用户无感知 | |

#### C. 告别写入（RULE-ZERO）

| # | 测试案例 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|
| T10 | 基础告别写入 | 说"晚安" → 检查是否有 tool call | 先 user_profile_update 再输出文字 | |
| T11 | 含人物的告别 | 聊到小白后说"拜拜" | user_profile_update + person_update("小白") 都执行 | |
| T12 | 极短对话告别 | 只说"你好"然后"再见" | 仍然执行写入（最简版本） | |
| T13 | 多告别词 | 分别测试：再见/晚安/先走了/拜拜/去睡了/好一点了 | 全部触发写入 | |

#### D. Service Tool 稳定性

| # | 测试案例 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|
| T14 | patch 幂等性 | 两次 user_profile_update(patch=同一字段) | 两次更新都保留 | |
| T15 | person 新建 | 提到新人物"阿城" → person_get("阿城") | 新建档案，格式符合 diary SKILL.md 模板 | |
| T16 | person 消歧 | 提到同名不同人 → 确认后检查 | 创建消歧档案 person_update("小白(同事)") | |
| T17 | person 封存 | 分手后封存 → person_update(content="[archived]") | 封存成功，后续 memory_search 不再命中 | |
| T18 | growth_track 降级 | 让 growth_track 失败 | 降级为 memory_search，用户无感知 | |

### 5.2 怀宽 + 才学：成长 Tab

#### E. 课程流程

| # | 测试案例 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|
| T19 | 5 天课程完整跑通 | Day 1 → Day 5 每天三环节（学/练/聊） | 全流程无报错，进度正确 |  |
| T20 | selfhelp 迁移 | 自助课入口是否可用 | 课程列表正确展示 | |
| T21 | 趣味测试入口 | MBTI 等测试是否独立运行 | 第四入口正常跳转 | |
| T22 | course-dialogue 数据 | 课程对话中提到的内容 → 检查是否写入 | 数据落库（确认写到哪张表） | |

#### F. 考研 6 个 Skill — 🚫 不在本期需求中，暂不测试

### 5.3 全员交叉：跨 Tab 验证

| # | 测试案例 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|
| T29 | 成长→聊天 | 成长课做了焦虑评估 → 切到聊天 Tab → 跟可可聊 | 可可知道用户刚做了评估 | |
| T30 | 聊天→成长 | 聊天中提到考研焦虑 → 切到成长 Tab 开始课程 | 课程能读到聊天中的背景 | |
| T31 | 日记互通 | 聊天产生日记 + 成长课产生日记 → 日记页面 | 两边日记都出现，时间线正确 | |
| T32 | 人物互通 | 聊天建了"妈妈"档案 → 成长课提到妈妈 | 成长课能读到妈妈的档案 | |
| T33 | memory_search 跨 Tab | 在成长课聊了一个话题 → 聊天 Tab memory_search | 能搜到成长课的内容 | |

---

## 六、⚠️ 底层关键问题（优先搞清楚，否则业务层测试白做）

| # | 问题 | 为什么重要 | 怎么验证 |
|---|------|----------|---------|
| **Q1** | Service Tool 背后的数据库是什么？每个 tool 对应哪张表/哪个集合？ | 不知道写到哪就没法验证 | 后端文档或直接查数据库 |
| **Q2** | user_profile_update(patch=...) 连续两次 patch 同一个 `## 区块`，是追加还是覆写？ | 覆写 = 数据丢失 | T14 测试 |
| **Q3** | person_get 返回空时（人物不存在），返回值是什么？空字符串？null？错误码？ | Agent 行为依赖返回值判断新建还是更新 | 直接调用一个不存在的人名 |
| **Q4** | memory_search 的索引范围——diary/ + people/ + memory/ 以外的数据（成长课、考研）在不在索引里？ | 决定跨 Tab 是否能通 | T33 测试 |
| **Q5** | ai-companion 和 kaoyan-companion 是共享还是独立的 user_profile？ | 独立 = 两边数据互不可见 | 两边各写一次 user_profile → 互相 get |
| **Q6** | diary_write 的归属——两个 Tab 写的日记在同一个存储里吗？ | 独立 = 日记页面展示不全 | 两边各写一条 → diary_read(list_month) 看都在不在 |
| **Q7** | Skill 路由——三层路由方案中，什么条件路由到 ai-companion、什么条件路由到 kaoyan-companion？路由规则在哪配置的？ | 路由错了业务全错 | 查路由配置文件 + 用不同话题测试路由结果 |

**建议：先花半天搞清楚 Q1-Q7，再开始跑测试矩阵。**

---

## 七、各业务模块风险分析（6 维度深度审查）

### 7.1 可可对话（毅卓负责）

**已发现的 Bug：**
- ⚠️ **待回访数据写入矛盾**：decision-cooling 写 `memory/pending_followup.md`（旧路径），AGENTS.md 告别流程写 `user_profile_update(patch="## 待回访")`。**两个位置同时存在待回访数据，Heartbeat 读哪个？**
- ⚠️ **pattern-mirror 在优先级表中缺失**：skill 路由优先级表没有列出 pattern-mirror，可能与 growth-story 冲突

**风险点：**

| 风险 | 严重度 | 测试方法 |
|------|--------|---------|
| 告别写入中间步骤失败（如 person_get 返回空），后续写入跳过 | P0 | 模拟新人物名→告别，检查完整写入链 |
| 模式日志格式不一致（pattern-mirror / AGENTS.md E-branch / farewell 三处写入） | P0 | 连续触发 E1/E2/E3/E4，逐次检查日志格式 |
| decision-cooling 回访后路由到 relationship-guide 的边界不清晰 | P1 | 构造"冲动行动+跨关系退出信号"同时场景 |
| 深夜模式下 §0.6 退出信号标记的生命周期未定义 | P1 | 深夜发送退出信号→次日是否补呈现 |

### 7.2 成长页面（怀宽+才学负责）

**已发现的问题：**
- ⚠️ **course-dialogue skill 不存在**（P0）：仓库中找不到该 skill，"聊一聊"环节无法运行
- ⚠️ **selfhelp 目录不存在**（P1）：迁移后前端入口可能指向空
- ⚠️ **跨 Tab 数据隔离**（P0）：成长课数据是否对聊天 Tab 可见，完全未验证

**风险点：**

| 风险 | 严重度 | 测试方法 |
|------|--------|---------|
| 成长课数据不写入 memory，Tab1 可可不知道用户课程进展 | P0 | 成长课聊一个话题→切 Tab1→memory_search |
| Skill 路由规则不明：什么条件到 ai-companion、什么到 kaoyan-companion | P0 | 不同话题测试路由，查路由配置 |
| kaoyan-companion 的 skill 定义文件可能缺失 | P0 | 检查 develop 分支 kaoyan-companion/skills/*.md 是否存在 |

### 7.3 学一学 + 练一练 + 聊一聊（怀宽+才学负责）

**状态：✅ 已实现。** 三个阶段统一在 `course-dialogue` skill 中（248 行），有 8 个专属 Service Tool。

**8 个 Service Tool：**

| Tool | 阶段 | 功能 |
|------|------|------|
| `course_dialogue_start_lesson` | 学一学 | 开始微课，返回卡片列表（含 TTS） |
| `course_dialogue_next_card` | 学一学/练一练 | 获取下一张卡片/题目（含进度更新） |
| `course_dialogue_card_interaction` | 学一学 | 记录卡片互动选择 |
| `course_dialogue_card_reply_tts` | 学一学 | 生成卡片回复 TTS 音频 |
| `course_dialogue_start_practice` | 练一练 | 开始练习，返回 5 道题 |
| `course_dialogue_submit_answer` | 练一练 | 记录答案提交 |
| `course_dialogue_init` | 聊一聊 | 初始化课程对话（获取 Prompt + 上下文） |
| `course_dialogue_context` | 聊一聊 | 获取对话上下文（Prompt + 历史） |

**7 种事件路由：** `start_lesson` / `card_interaction` / `card_reply_tts` / `user_next_card` / `start_practice` / `submit_answer` / `init_dialogue`

**风险点：**

| 风险 | 严重度 | 测试方法 |
|------|--------|---------|
| 8 个 Service Tool 后端是否全部实现 | P0 | 逐个调用，检查返回值 |
| 卡片进度持久化（中途退出→重进是否接续） | P1 | 看到第 3 张退出→重进→检查 current_card_index |
| 练一练答题结果是否传递给聊一聊 | P1 | 做完 5 题→进入聊一聊→可可是否提到答题情况 |
| 课程对话的记忆是否写入共享 memory | P0 | 聊一聊中提到人物→切聊天 Tab→memory_search |
| TTS 音频生成是否正常 | P1 | card_reply_tts 返回的 URL 是否可播放 |
| 7 种事件路由是否正确分发 | P0 | 每种事件各触发一次，检查走的 Tool 对不对 |

### 7.6 我的页面（毅卓负责）

**已发现的问题：**
- ⚠️ **没有 `person_list` Tool**：前端想展示"我的关系人物"列表，但 Service Tool 只能按名字逐个 get，没有列举接口
- ⚠️ **FORMAT_MINIPROGRAM.md 可能未合入 main**：前端渲染规范文档缺失

**风险点：**

| 风险 | 严重度 | 测试方法 |
|------|--------|---------|
| 人物列表展示无接口 | P1 | 确认前端如何获取所有人物名单 |
| diary_read 返回 Markdown 但前端解析规范未定义 | P1 | 对比 diary_read 返回格式和前端期望格式 |
| growth_tracker.py 失败时「我的」页面无法降级 | P1 | 让脚本超时→检查页面是否报错 |
| patch 连续写入同一区块的幂等性 | P0 | 连续两次 patch 同字段→检查数据完整性 |

---

## 八、总结：当前可测 vs 不可测

| 模块 | 状态 | 可测？ |
|------|------|--------|
| 可可对话 | ✅ 已实现 | 可测，有 bug 需修 |
| 我的页面 | ✅ 已实现（部分） | 可测，缺 person_list 接口 |
| 学一学 | ✅ 已实现（course-dialogue skill） | 可测，需验证 8 个 Service Tool 后端 |
| 练一练 | ✅ 已实现（course-dialogue skill） | 可测，重点验证答题结果传递 |
| 聊一聊 | ✅ 已实现（course-dialogue skill） | 可测，重点验证记忆写入共享 |
| 成长页面框架 | ✅ 已实现 | 可测（selfhelp 迁移 + 入口） |
| 跨 Tab 数据通道 | ❓ 未验证 | 先回答 Q1-Q7 |
| 考研 6 个 skill | 🚫 暂不测试 | 排期后再测 |

**建议执行顺序：**
1. 先花半天回答 Q1-Q7（底层确认）
2. 测可可对话（T1-T18, T34-T48）
3. 测学一学/练一练/聊一聊（重点：8 个 Service Tool 是否全部可用）
4. 测我的页面（T56-T67）
5. 测跨 Tab（T29-T33, T49-T55）

---

## 九、补充测试用例（深度风险覆盖）

### 9.1 可可对话补充用例（毅卓，T34-T48）

#### 待回访双写冲突

| # | 测试案例 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|---------|
| T34 | 待回访写入路径确认 | 用户有情绪事件对话 | 触发 decision-cooling → 对话结束 → 检查 `memory/pending_followup.md` 和 `user_profile ## 待回访` | 确认数据写到了哪里。**已知矛盾：两处可能都有数据** | |
| T35 | Heartbeat 读取源验证 | T34 完成，两处都有待回访数据 | 等 24h Heartbeat 触发 → 回访完成后检查两处数据是否都被清理 | HEARTBEAT.md 只读 `memory/pending_followup.md`。user_profile 的待回访可能永远不被清理 | |
| T36 | 仅写 user_profile 时回访丢失 | decision-cooling 只写了 user_profile | 等 Heartbeat 触发 | Heartbeat 读 pending_followup.md 为空 → 回访丢失 | |

#### 模式日志格式一致性

| # | 测试案例 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|---------|
| T37 | pattern-mirror 写入格式 | ≥2 段关系 + ≥5 次对话 + 情绪稳定 | 触发 pattern-mirror → Phase 4 呈现 → 检查模式日志 | 格式：`- {日期}: {类型} \| 涉及: {人物} \| status: presented \| cooldown_until: {+14天}` | |
| T38 | AGENTS.md E-branch 写入格式 | 跨关系模式对话 | 用户反应 E1 否认 → 检查模式日志 | 格式应与 T37 一致。**风险：AGENTS.md 未指定模式类型字段** | |
| T39 | farewell 收尾写入格式 | pattern-mirror 完成后告别 | "晚安" → 检查 farewell 写入的模式日志 vs pattern-mirror 写入的 | farewell 写 `## 模式级洞察`（去名字），pattern-mirror 写 `## 模式日志`。两者不同区块，互不干扰 | |

#### pattern-mirror 优先级冲突

| # | 测试案例 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|---------|
| T40 | pattern-mirror vs growth-story 同时触发 | ≥30 天 + ≥2 关系 + ≥5 对话 + growth_tracker 有 IM | 用户说"我每次都这样" → 观察路由 | growth-story 在优先级表 P2.5，pattern-mirror 不在表中。实际路由到哪个？ | |
| T41 | 共享频率配额 | 本周已触发 1 次 growth-story | 同周内触发 pattern-mirror → 检查频率保护 | 两者共享周配额（最多 2 次）。pattern-mirror 能否读到 growth-story 已用的配额？ | |

#### 深夜模式退出信号

| # | 测试案例 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|---------|
| T42 | 深夜退出信号延后呈现 | 23:00 用户发消息 | "他好像没那么喜欢我了" → §0.6 标记 → 深夜禁止呈现 → 次日回来 | 次日是否补呈现？**风险：标记可能只在 session 内存中，跨 session 丢失** | |
| T43 | 深夜退出信号 + decision-cooling 交叉 | 23:30 用户发消息 | "他不在乎我了，我现在就去找他" → 同时触发 §0.6 + decision-cooling | decision-cooling 应触发（安全优先）。§0.6 标记的生命周期？ | |
| T44 | pattern_match_pending 持久化 | 深夜退出信号被延后 | 检查 `pattern_match_pending: true` 写入位置 | **已知问题：pattern-mirror 提到写 memory/ 但无对应 Service Tool** | |

#### 告别写入链路完整性

| # | 测试案例 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|---------|
| T45 | person_get 返回空时新建 | 首次提到"阿城" | "阿城又不回消息了，拜拜" → person_get 返回空 | 应自动 person_update 新建档案，不跳过 | |
| T46 | user_profile_update 失败后续处理 | 有对话+提到人物 | 模拟 user_profile_update 失败 → person_update 是否仍执行 | 后续步骤应独立尝试，不因前一步失败全部跳过 | |
| T47 | 多人物部分写入失败 | 提到 3 个人物（妈妈/小白/室友） | 模拟 person_update("小白") 失败 → 检查 person_update("室友") 是否执行 | 3 个写入应独立，某个失败不影响其他 | |
| T48 | farewell 封存中间步骤失败 | 用户选择仪式化封存 | 模拟 person_update([archived]) 失败 → 检查 user_profile_update 是否仍执行 | 封存失败但洞察已写入 → 数据不一致（人物未封存但用户收到"封存了"确认） | |

### 9.2 成长页面补充用例（怀宽+才学，T49-T55，去掉考研）

| # | 测试案例 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|---------|
| T49 | selfhelp 目录文件完整性 | develop 分支 | 检查 selfhelp 目录是否有课程数据文件 | 不能为空目录 | |
| T50 | course-dialogue SKILL.md 存在性 | develop 分支 | 磁盘检查 ai-companion/skills/course-dialogue/SKILL.md | 文件存在且非空；缺失则为 P0 | |
| T51 | mood-flow + motivation-guide 存在性 | develop 分支 | 磁盘检查两个 SKILL.md | 存在则成长课可路由；缺失则学一学/聊一聊无法运行 | |
| T52 | 自助课前端入口跳转 | develop 分支部署到测试环境 | 成长 Tab 点"自助课"入口 | 跳转到课程列表，展示可用课程 | |
| T53 | 成长课→聊天 Tab 数据流 | 在成长课完成一节 | 成长课中提到"跟妈妈因为考研吵架" → 切聊天 Tab | 可可 memory_search 能命中成长课内容 | |
| T54 | 聊天 Tab→成长课数据流 | 聊天 Tab 聊过焦虑 | 切到成长 Tab 开始课程 | 课程能读到聊天中的背景 | |
| T55 | MBTI 趣味测试独立运行 | develop 分支 | 成长 Tab 第四入口→选 MBTI→完成 | 测试流程完整，结果正确，不影响其他数据 | |

### 9.3 我的页面补充用例（毅卓，T56-T67）

| # | 测试案例 | 前置条件 | 操作步骤 | 预期结果 | 实际结果 |
|---|---------|---------|---------|---------|---------|
| T56 | 日记列表按月展示 | 本月 ≥3 天日记 | diary_read(list_month="2026-04") | 返回所有日记，日期正确、六元组字段齐全 | |
| T57 | 日记 Markdown 前端渲染 | 日记含人物链接和引用块 | diary_read → 交前端渲染 | 人物链接可点击、引用块有区分。**需确认 FORMAT_MINIPROGRAM.md 是否合入** | |
| T58 | 同一天多条日记 | 同天 2 次对话 | diary_read(date) | 返回 2 条，按时间排列，不互相覆盖 | |
| T59 | 人物列表展示 | 3 个人物（含 1 个已封存） | 进入"我的"→ 人物列表 | **已知缺陷：无 person_list Tool。** 确认前端替代方案 | |
| T60 | 封存人物不在活跃列表 | 赵磊已 [archived] | 检查人物列表 | 封存人物不出现在活跃列表 | |
| T61 | 人物详情页完整性 | 小凯档案完整（8 区块） | person_get("小凯") | 8 个区块都在，格式正确 | |
| T62 | 周回顾正常触发 | 本周 diary ≥3 条 | 周日 20:00 Heartbeat 触发 | 生成 JSON，缓存到 weekly_cache | |
| T63 | 周回顾数据不足降级 | 本周 diary 仅 2 条 | 周日 Heartbeat | 不触发周回顾，降级为常规关怀 | |
| T64 | 成长故事正常触发 | ≥30 天 + ≥2 周日记 + growth_tracker 有 IM | 用户自我否定 | 触发成长叙事，引用用户原话做前后对比 | |
| T65 | growth_tracker 失败降级 | 模拟脚本超时 | 检查页面 | **已知风险：页面可能无法降级。** 预期：不报错不白屏 | |
| T66 | 用户编辑个人信息 | USER.md 完整 7 字段 | 修改称呼（阿瑶→瑶瑶）→ patch → get | 称呼更新，其余字段不变 | |
| T67 | patch 连续写入幂等性 | 核心困扰已有 3 条 | 连续 2 次 patch 追加新困扰 → get | 原 3 条 + 新 2 条全部保留。若只剩最后一次 = P0 数据丢失 | |

---

## 十、覆盖度分析：已有自动化测试 vs POA 用例

psychologists 仓库已有 **100+ 个自动化测试文件**，分布在后端和前端。以下对照 POA 67 个用例，标注哪些已被覆盖、哪些需要手动测。

### 已有自动化测试覆盖的模块

| 模块 | 已有测试文件 | 覆盖的 POA 用例 | 说明 |
|------|------------|----------------|------|
| **记忆系统** | `test_memorize_service.py` `test_memory_loader.py` `test_hotword_service.py` `test_boundary_cases.py` `test_daily_memorize_task.py` `test_integration.py` `test_migration_complete.py` | T1-T5（部分） | 记忆写入/读取的单元测试已有，但**跨 session 连续性**（T1 用户第二次来能接上）需手动测 |
| **成长课程** | `test_course_dialogue_agent.py` `test_micro_lesson_agent.py` `test_quiz_practice_agent.py` `test_micro_lesson_progress_api.py` `test_practice_init_api.py` 等 20+ 个 | T19（部分）、T22 | 课程三环节的 API 和 Agent 有测试，但**端到端 5 天完整流程**需手动测 |
| **情绪/心情** | `test_mood_agent.py` `test_mood_socketio_flow.py` `test_mood_tool_tts_edgecases.py` `test_mood_session_transaction.py` | — | mood-flow 有覆盖，POA 中未单列 |
| **成长页面** | `test_growth_home_api.py` `test_growth_progress_api.py` `test_graduation_service.py` `test_growth_home_service.py` | T20（部分） | 成长首页和进度 API 有测试 |
| **Tool 架构** | `test_tool_architecture.py` `test_tool_migration.py` `test_tool_monitoring.py` `test_tool_metadata.py` | Q1（部分） | Service Tool 迁移的架构测试已有 |
| **前端** | 30+ 个前端测试（growth/micro-lesson/practice/chat） | T19-T22（前端部分） | 卡片渲染、流式解析、导航布局等 |

### ⚠️ 未被自动化覆盖、需要手动测的（重点）

| 用例范围 | 为什么不能自动化 | 手动测试建议 |
|---------|----------------|------------|
| **T1-T5 跨 session 记忆** | 需要真实的多轮对话+关闭+重开 | 真机测试：聊一轮→关小程序→重开→看可可是否记得 |
| **T6-T9 模式识别** | 需要积累 3+ 次同类对话，LLM 行为不确定 | 模拟 3 轮"跟妈妈因为成绩吵架"→观察第 3 次可可是否主动洞察 |
| **T10-T13 告别写入** | 需要验证 LLM 输出顺序（先 tool call 后文字） | 真机测试，用抓包工具看 WebSocket 消息顺序 |
| **T29-T33 跨 Tab** | 需要在两个 Tab 之间切换并验证数据共享 | 真机：成长课聊内容→切聊天 Tab→看可可是否知道 |
| **T34-T36 待回访双写** | 涉及 Heartbeat 定时触发 + 数据清理 | 手动触发 decision-cooling→等 Heartbeat→检查两处数据 |
| **T37-T39 模式日志格式** | 需要对比三处写入的格式是否一致 | 触发 pattern-mirror / E-branch / farewell 各一次→对比日志 |
| **T40-T41 优先级冲突** | 需要同时满足 pattern-mirror 和 growth-story 条件 | 构造高密度数据（≥30天+≥2关系+≥5对话+IM）→观察路由 |
| **T42-T44 深夜模式** | 需要在 23:00 后测试 | 手动：深夜发退出信号→次日看是否补呈现 |
| **T45-T48 告别链路失败** | 需要模拟 Service Tool 失败 | 可写自动化：mock Service Tool 返回错误→检查 Agent 行为 |
| **T56-T58 日记展示** | 需要验证前端渲染效果 | 真机：看日记页面六元组是否正确显示 |
| **T59-T61 人物列表** | 缺 person_list 接口 | 先确认前端替代方案，再验证 |
| **T62-T63 周回顾** | 需要 Heartbeat 定时触发 | 手动触发或等周日 20:00 |
| **T66-T67 patch 幂等性** | 关键数据安全测试 | **可写自动化**：连续 patch→读→断言 |

### 建议：可以补写自动化测试的用例

以下用例值得投入时间写成自动化测试（一次写好反复用）：

| 用例 | 测试类型 | 建议文件位置 |
|------|---------|------------|
| **T14/T67 patch 幂等性** | 单元测试 | `backend/tests/unit/test_user_profile_patch.py` |
| **T15 person 新建格式** | 单元测试 | `backend/tests/unit/test_person_create_format.py` |
| **T45-T48 告别链路失败** | 集成测试（mock） | `backend/tests/integration/test_farewell_error_handling.py` |
| **T34-T36 待回访一致性** | 集成测试 | `backend/tests/integration/test_pending_followup_consistency.py` |
| **T50-T51 skill 文件存在性** | CI 检查 | `backend/tests/unit/test_skill_files_exist.py` |

### 不能自动化、只能手动的

| 用例 | 为什么只能手动 |
|------|-------------|
| T1-T5 跨 session 记忆 | 需要真实 LLM 对话 + session 生命周期 |
| T6-T9 模式识别 | 需要多轮真实对话积累，LLM 行为不确定 |
| T29-T33 跨 Tab | 需要小程序两个 Tab 切换 |
| T40-T41 优先级冲突 | 需要精心构造的高密度用户数据 |
| T42-T44 深夜模式 | 需要在特定时间测试 |
| T56-T61 我的页面展示 | 需要真机验证 UI 渲染效果 |

---

## 十一、交付物

毅卓团队完成测试后，需要交付：

1. **测试矩阵填写完成**（本文档第五节的"实际结果"列）
2. **Q1-Q7 的答案**（底层架构确认）
3. **时序图补充**——如果实际数据流跟第三节的时序图不一致，画出真实的数据流
4. **Bug 清单**——每个 bug 标注严重等级（P0 数据丢失 / P1 功能异常 / P2 体验问题）
5. **跨 Tab 方案**——如果 T29-T33 验证发现跨 Tab 不通，需要提出解决方案

**时间要求：** 1 周内完成 Q1-Q7 + 测试矩阵。Bug 修复按严重等级排期。
