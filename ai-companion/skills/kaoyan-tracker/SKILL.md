---
name: kaoyan_tracker
description: 每日学习打勾追踪——1次点击记录今日学习情况，积累数据支撑计划调整和周报。触发方式：Cron 22:00 推送 + 用户主动汇报。
---

# 考研每日打勾追踪

每天晚上 1 次点击完成打勾。核心打勾 ≤15 秒，全流程最长路径（含错题追问）≤60 秒。积累的数据供 F3 调整明天计划、F5 生成周报、F6 检测崩溃。

## 触发条件

| 触发方式 | 条件 |
|---------|------|
| Cron 22:00 | 用户有考研身份（`kaoyan_target_school` 存在）且 `kaoyan_tracker_preference != "dislike"` |
| 用户主动 | 消息匹配关键词：打勾/打卡/做完了/学完了/今天搞定了 且用户有考研身份 |

**与通用 check-in 的关系：** 考研用户的每日 check-in 统一由本 skill 在 22:00 处理，不再走通用 check-in 的 21:30 Cron。AGENTS.md 路由规则：`kaoyan_target_school` 存在 → 跳过 21:30 通用 check-in。考研用户只有 22:00 一个入口。

## 数据读取

```
# 打勾前：读取今日 F3 推送的计划（生成动态选项）
read memory/kaoyan/plan_history.md → 提取 today 的 plan[]

# 打勾时：读取最近 tracker 记录（计算 streak）
read memory/kaoyan/tracker/{yesterday}.md
read memory/kaoyan/tracker/{day_before_yesterday}.md
→ 计算 streak.consecutive_days / consecutive_complete / consecutive_none
```

---

## 核心打勾流程（≤15 秒，1 次点击）

### 1.1 Cron 发起

```
ai_message(messages=["今天辛苦了，来打个勾吧"])

ai_options(
  type="poll",
  question="今天学习怎么样？",
  options=[
    {"id": "done_all",  "text": "全部搞定"},
    {"id": "done_most", "text": "做了大部分"},
    {"id": "done_some", "text": "做了一点点"},
    {"id": "done_none", "text": "今天没学"},
    {"id": "bad_day",   "text": "状态不好"}
  ],
  multi=false
)
```

**用户主动打勾时**跳过"今天辛苦了"开场，直接进入 ai_options。

**当天已打过勾时**："今天已经打过勾了，要更新一下吗？" → 是 → 覆盖今日记录 / 否 → 结束。

**用户点击一次 → 核心打勾完成。** 以下所有追问都是可选的。

---

## 回应分支

每个分支回应必须满足：(1) 先肯定，不评判 (2) 每天不同

### 分支 A：全部搞定（done_all）

**回应规则：**
- 肯定完成，语气真诚不夸张
- 引用今日计划中的具体内容（如"极限那 10 道题都做了，厉害"）
- 连续 3 天全部完成 → 额外加进度感知（"连续三天全勾了，这周稳了"）

**追问：** 进入错题追问（可选）

### 分支 B：做了大部分（done_most）

**回应规则：**
- 肯定已完成的部分，不提未完成的
- 问一句哪个没做（为 F3 计划调整提供数据）

```
ai_message(messages=["做了大部分就很好了。哪个没来得及做？"])

ai_options(
  type="poll",
  question="",
  options=[
    // 动态生成：基于今日 F3 推送的具体任务列表
    {"id": "task_1", "text": "{今日任务1，如：数学极限10题}"},
    {"id": "task_2", "text": "{今日任务2，如：英语阅读2篇}"},
    {"id": "task_3", "text": "{今日任务3，如：政治马原第3章}"},
    {"id": "multiple", "text": "好几个都没做完"}
  ],
  multi=true
)
```

**追问：** 进入错题追问（可选）

### 分支 C：做了一点点（done_some）

**回应规则：**
- "做了就算数"——庆祝微小行为（BJ Fogg Tiny Habits）
- 不问"为什么没做完"
- 问做了什么（正向框架）

```
ai_message(messages=["做了一点也是做了。今天做了什么？"])

ai_options(
  type="poll",
  question="",
  options=[
    // 动态生成：基于今日 F3 任务列表
    {"id": "task_1", "text": "{今日任务1}"},
    {"id": "task_2", "text": "{今日任务2}"},
    {"id": "task_3", "text": "{今日任务3}"},
    {"id": "other", "text": "做了点别的"}
  ],
  multi=true
)
```

**不追问错题。** done_some 的用户今天已经很勉强了，不增加负担。

### done_most/done_some 追问跳过时 completed[] 补齐规则

用户跳过追问（不选具体任务/不回复/选"不想说了"）时自动补齐：

| 状态 | 补齐规则 |
|------|---------|
| done_most（跳过） | 所有 task `done=true`，最后一个 `done=false` |
| done_some（跳过） | 第一个 task `done=true`，其余 `done=false` |

理由：F3 和 F5 需要 completed[] 有值。保守估计宁可低估，不高估。

### 分支 D：今天没学（done_none）

**回应规则：**
- 零压力：不说"没关系明天补上"（暗示做错了），不说"休息也很重要"（敷衍）
- 给一个真实的、不带评判的回应
- 不追问原因

**回应方向（AI 生成，每天不同）：**
- "好，那今天就这样。明天我还在。"
- "嗯，一天不学不会怎样的。"
- "了解了。好好休息。"

**不追问任何东西。结束打勾。**

**连续 2 天 done_none：** 第 2 天回应加一句轻触（"连着两天没学，是不是最近有什么事？不想说也没事"）。

**连续 3 天 done_none（不含 done_some）：** 触发 F6 崩溃接住（被动触发）。

### 分支 E：状态不好（bad_day）

**立即路由到 kaoyan-crisis skill。** 打勾流程结束。

```
# 路由到 F6
ai_message(messages=["怎么了？想说说吗？"])
→ 等待用户回复
→ 进入 kaoyan-crisis Phase 1
```

数据记录：`status: bad_day`，由 F6 接管后续。

---

## 错题追问（可选，仅 done_all/done_most 触发）

目的：为 F5 周报薄弱点分析提供数据。用户随时可跳过。

```
ai_options(
  type="poll",
  question="今天做题有卡住的地方吗？",
  options=[
    {"id": "no_stuck",    "text": "没有，都还顺利"},
    {"id": "math_stuck",  "text": "数学有卡住"},
    {"id": "eng_stuck",   "text": "英语有卡住"},
    {"id": "pol_stuck",   "text": "政治有卡住"},
    {"id": "major_stuck", "text": "专业课有卡住"},
    {"id": "skip",        "text": "不想说了"}
  ],
  multi=true
)
```

如果选了具体科目：
```
ai_message(messages=["{科目}哪块卡住了？大概说一下就行，一句话就够"])
```
用户自由输入（如"极限洛必达那块""概率大题"）。AI 提取关键词存入 stuck_points。

如果选"不想说了"或"没有"：
```
ai_message(messages=["好，今天打勾完成。晚安。"])
```

---

## 话术变化机制（防模板化）

回应生成时必须考虑的上下文变量：

| 变量 | 来源 | 影响 |
|------|------|------|
| 今日周几 | 系统时间 | 周一鼓劲、周五轻松、周末弹性 |
| 连续完成天数 | streak 计算 | 连续 3 天+ → 强调连胜感 |
| 上次未完成科目 | 昨日 tracker | "昨天没做的英语今天补上了，不错" |
| 本周累计完成率 | memory 计算 | >80% → "这周效率很高" |
| 用户风险点 | USER.md kaoyan_risk_point | 针对性鼓励 |

**硬规则：**
- 连续 3 天开头句式不能相同
- 不使用"加油""你真棒""继续保持"等空洞鼓励词
- done_all 的回应必须引用今日具体任务内容

---

## 第一周坦诚期

- Day 1："这是你的第一次打勾。每天花 10 秒告诉我学了什么，一周后我就能给你更准的计划了。"
- Day 2："打勾第二天了。你告诉我的每一个信息，都在让明天的计划更适合你。"
- Day 3："第三天了，你已经比大部分人坚持得久了。"

Day 4 起不再附加说明。

---

## 用户主动打勾

用户在任何时候说"今天做完了""打个勾""今天学了XX"等，触发打勾流程。与 Cron 触发相同，但跳过开场。

如果用户不点选项而是直接打字（如"今天做完了，极限那块终于搞懂了"）：
- AI 从文本提取 status（"做完了" → done_all）
- AI 从文本提取 stuck_points 或正面反馈
- 正面反馈记入 note 字段
- 不强制走 ai_options 流程

---

## 数据存储

### 存储位置

`memory/kaoyan/tracker/YYYY-MM-DD.md`

一天一个文件。理由：单文件无限增长 token 消耗大；按天分文件便于 F5 日期范围查询。

### 数据格式（YAML）

```yaml
# memory/kaoyan/tracker/2026-04-05.md
---
date: "2026-04-05"
weekday: "Saturday"
check_in_time: "22:03"
trigger: "cron"  # cron | user_initiated
status: "done_most"  # done_all | done_most | done_some | done_none | bad_day

plan:
  - id: "task_1"
    subject: "数学"
    topic: "极限-洛必达法则"
    description: "张宇1000题 第96-105题"
    estimated_minutes: 90
  - id: "task_2"
    subject: "英语"
    topic: "阅读理解"
    description: "真题阅读2篇"
    estimated_minutes: 60
  - id: "task_3"
    subject: "政治"
    topic: "马原-第3章"
    description: "马原第3章精读"
    estimated_minutes: 30

completed:
  - task_id: "task_1"
    done: true
  - task_id: "task_2"
    done: false
  - task_id: "task_3"
    done: true

stuck_points:
  - subject: "数学"
    description: "极限洛必达那块"
    normalized_topic: "极限-洛必达法则"

mood: "normal"  # normal | tired | bad
note: ""

streak:
  consecutive_days: 3
  consecutive_complete: 2
  consecutive_none: 0
---
```

### 字段用途

| 字段 | 引用方 | 用途 |
|------|--------|------|
| status | F3/F5/F6 | F3:调整明天计划量; F5:计算完成率; F6:连续none检测 |
| plan[] | F5 | 与completed对比算各科完成率 |
| plan[].subject | F5 | 按科目汇总 |
| plan[].topic | F5 | 薄弱点分析精确到知识点 |
| plan[].estimated_minutes | F5 | 计算实际投入时间 |
| completed[] | F3/F5 | F3:未完成的明天补; F5:完成率统计 |
| stuck_points[] | F3/F5 | F3:卡住点加强练习; F5:薄弱点排行 |
| stuck_points[].normalized_topic | F5 | 跨天聚合同一知识点卡住次数 |
| mood | F3/F6 | F3:明天降级; F6:触发检测 |
| streak.consecutive_none | F6 | ≥2天触发主动关怀, ≥3天触发崩溃接住 |
| streak.consecutive_days | F4自身 | 回应话术引用连胜 |
| streak.consecutive_complete | F5 | 周报展示连续全勾天数 |

### F3 读取方式

F3 每日计划生成时（早 8:00）读取昨日 tracker：
```
读取 memory/kaoyan/tracker/{yesterday}.md
→ completed[].done == false 的 task → 纳入今日计划优先队列
→ stuck_points[].normalized_topic → 今日该 topic 增加练习量
→ mood == "tired" → 今日计划总量降级 20%
→ streak.consecutive_none >= 2 → 今日推送最小计划
```

### F5 读取方式

F5 周报生成时（周日 20:00）读取本周 7 天：
```
遍历 memory/kaoyan/tracker/{周一到周日}.md
→ 打卡天数 = count(文件存在且 status != null)
→ 各科完成率 = 各科 completed[done=true] / 各科 plan[] 总数
→ 薄弱点排行 = stuck_points[].normalized_topic 按出现次数降序
→ 进步对比 = 本周 vs 上周同科目完成率
→ 连续最长连胜 = max(streak.consecutive_days)
```

---

## 三种"未完成"状态的判断与下游影响

| 状态 | 定义 | tracker 文件 | 下游影响 |
|------|------|-------------|---------|
| **missing_day** | 用户未回复（Cron 推送后截至次日 06:00 无交互） | **不创建**（无文件 = missing_day） | F3:按 done_some 保守估计; F5:不计入打卡天数; F6:连续 2 天无文件→轻量探测 |
| **done_none** | 用户主动说"今天没学" | **创建**，`status: done_none` | F3:明天降级60%; F5:计入打卡但不计有效学习; F6:连续3天→崩溃接住 |
| **bad_day** | 用户情绪低/崩溃 | **创建**，`status: bad_day`, `mood: bad` | F3:明天降级60%+gentle话术; F6:立即接管 |

**连续计数规则：**
- `streak.consecutive_none` 只计 done_none，不计 missing_day
- F6 行为信号检测：连续 2 天无 tracker 文件 → 轻量探测；连续 3 天 done_none → 崩溃接住
- 两个计数器独立，不叠加

---

## 边界场景

| 场景 | 处理 |
|------|------|
| 用户超时不回复（missing_day） | 不补推，不追问。该天不创建 tracker |
| 凌晨回复（00:00-06:00） | 记到昨天的 tracker（date 取推送日期） |
| F3 当天未推送计划 | 打勾正常触发，plan[] 和 completed[] 为空，仅记 status+mood+note |
| 用户说"别每天问我" | 立即停止 Cron。写入 USER.md：`kaoyan_tracker_preference: "dislike"`。后续仅接受主动打勾 |

---

## HEARTBEAT.md 配置

```yaml
kaoyan_tracker:
  cron: "0 22 * * *"
  condition: "user.kaoyan_target_school exists AND user.kaoyan_tracker_preference != 'dislike'"
  action: "trigger kaoyan-tracker check-in flow"
  note: "替代通用 check-in 的 21:30 Cron（考研用户只走这一个入口）"

# 同时更新通用 check-in:
general_check_in:
  condition_add: "user.kaoyan_target_school NOT exists"
```

---

## Memory 写入

每次打勾完成后，调用 `diary_write(date="YYYY-MM-DD", type="kaoyan-tracker", entry=content)` 写入 tracker 文件。

streak 计算逻辑：
```
读取前 N 天 tracker 文件
consecutive_days = 从今天往前数，连续有 tracker 文件的天数
consecutive_complete = 从今天往前数，连续 status == done_all 的天数
consecutive_none = 从今天往前数，连续 status == done_none 的天数（不含 done_some/missing）
```
