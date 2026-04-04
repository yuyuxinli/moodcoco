---
name: kaoyan_daily_plan
description: 考研每日计划推送——每天早 8 点基于遗忘曲线 + 提分 ROI + 昨日完成情况动态生成当日学习计划。触发方式：Cron 08:00 自动推送 + 用户主动要求"帮我排计划"。
---

# 考研每日计划推送（2027 考研）

每天早 8 点推到微信里的动态学习计划。基于昨天做了什么、哪里卡住、遗忘成本、各科提分 ROI 自动生成。不是静态日程表，是每天都在变的执行指令。

**全程中文输出。** 所有推送消息、回复均使用中文。

## 触发条件

| 触发方式 | 条件 |
|---------|------|
| Cron 08:00 | 用户有考研身份（`kaoyan_diagnosis_date` 非空）且 `kaoyan_plan_active != false` |
| Cron 07:00 | 在职考生（`kaoyan_hard_indicators.identity == "working"`） |
| 用户主动 | "帮我排计划""今天学什么""给我安排" 等 |

**前置条件：** 用户必须做过 F2 诊断（`kaoyan_diagnosis_date` 非空）。未做诊断时不推送计划，改为引导："你还没做过备考诊断，先花 3 分钟测一下，我才能帮你排计划。"

## 数据读取

每次计划生成前，用以下工具加载数据：

```
# 1. 用户档案（F2 诊断写入）
read USER.md
→ 提取 kaoyan_* 字段：target_school, target_major, retest_line, self_eval,
   estimated_scores, daily_hours, start_date, risk_point, required_daily_hours,
   gap, hard_indicators.identity, subject_scores, target_scores,
   single_subject_line, plan_adjustment, plan_day_count, plan_state, plan_context

# 2. 昨日打勾数据（F4 写入）
read memory/kaoyan/tracker/{yesterday}.md
→ 提取 status, completed[], stuck_points[], mood, streak

# 3. 计划历史（本 skill 写入）
read memory/kaoyan/plan_history.md
→ 最近 14 天计划记录

# 4. 周报建议（F5 写入，可选）
read memory/kaoyan/weekly_cache/{latest}.json
→ 提取 recommendations: math_focus, english_adjustment, politics_minimum, plan_intensity

# 5. 崩溃记录（F6 写入，可选）
read memory/kaoyan/crisis_log.md
→ 检查是否处于崩溃后锁定期（最近 3 天内有崩溃事件）
```

## 备考阶段判定

根据距考试剩余天数（exam_date = 2026-12-19）自动判定：

| 阶段 | 条件 | 特点 |
|------|------|------|
| 基础期 | remaining_days > 180 | 重概念理解，数学权重高 |
| 强化期 | 90 < remaining_days <= 180 | 重做题，限时训练 |
| 冲刺期 | 30 < remaining_days <= 90 | 重真题，查漏补缺 |
| 考前期 | remaining_days <= 30 | 重政治背诵，保持手感 |

各阶段科目时间权重（分配 daily_hours 中除保底外的剩余时间）：

| 科目 | 基础期 | 强化期 | 冲刺期 | 考前期 |
|------|--------|--------|--------|--------|
| 数学 | 45% | 40% | 30% | 20% |
| 英语 | 30% | 25% | 25% | 20% |
| 政治 | 5% | 15% | 25% | 35% |
| 专业课 | 20% | 20% | 20% | 25% |

无数学的专业按（英语30%/政治10%/专业课一30%/专业课二30%）等比重分。

---

## 变量来源声明

| 变量 | 来源 | 说明 |
|------|------|------|
| `exam_subjects` | USER.md `kaoyan_subject_scores` 的 key 列表 | F2 诊断写入的科目代码列表（如 101, 201, 301） |
| `current_phase` | 由 `remaining_days`（距 2026-12-19）计算 | 见"备考阶段判定"表 |
| `subject.type` | 科目代码映射 | 101→政治、201/204→英语、3xx→专业课、301/302/303→数学 |
| `last_studied_content` | 最近一天该科 tracker 的 `plan[].topic` 字段 | 用于遗忘复习的任务描述 |
| `weekly_recommendations` | `memory/kaoyan/weekly_cache/{latest}.json` 的 `recommendations` 对象 | F5 周报写入 |
| `politics_minimum` | `weekly_recommendations.politics_minimum` | 字符串格式（如"保持每天 30min"），F3 仅作为 focus_hint 引用原文，不解析为数值 |

---

## 计划生成算法（4 步）

### Step 1：确定今日可用时间（available_hours）

```
base = user.kaoyan_daily_hours

# 读取 memory/kaoyan/tracker/{yesterday}.md
if 昨天 status == "bad_day" or mood == "tired":
  available_hours = base * 0.6
elif streak.consecutive_complete >= 3:
  available_hours = base * 1.0    # 不加码
elif streak.consecutive_none >= 2:
  available_hours = min(base * 0.4, 2.0)  # 最小行动模式
else:
  available_hours = base

# F5 周报建议覆盖（plan_intensity → 乘数映射）
# normal → ×1.0 | reduced → ×0.8 | minimum → ×0.6
if weekly_recommendations.plan_intensity == "reduced":
  available_hours *= 0.8
elif weekly_recommendations.plan_intensity == "minimum":
  available_hours *= 0.6

# 用户反馈系数
available_hours *= kaoyan_plan_adjustment  # 默认 1.0，范围 0.64-1.32

# F6 崩溃锁定期（最近 3 天内有崩溃事件）
if 处于崩溃后锁定期:
  available_hours = min(base * 0.4, 2.0)  # 强制 minimal
```

### Step 2：各科时间分配

**唯一算法路径：** 阶段权重（phase_weight）是 ROI 公式的因子之一，不是独立的分配路径。最终分配由 normalize(roi_score) 决定。

```
for each subject in exam_subjects:
  # ROI 分配（phase_weight 是 ROI 公式的因子）
  phase_weight = PHASE_WEIGHTS[current_phase][subject.type]  # 见"备考阶段判定"表
  roi_score = gap_factor * marginal_factor * phase_weight
  base_hours = available_hours * normalize(roi_score)  # normalize = roi_score[s] / sum(roi_score)

  # 薄弱点加权（基于 tracker 近 7 天 stuck_points）
  recent_stuck = count(近 7 天 stuck_points[].normalized_topic 匹配 subject)
  if recent_stuck > 3:
    weakness_boost = 0.3
  elif recent_stuck > 0:
    weakness_boost = 0.15
  else:
    weakness_boost = 0

  # 遗忘成本（距上次学习该科的天数）
  days_since_last = 距上次学习该科的天数
  review_count = 过去 14 天学习该科的天数
  half_life = 3 * (1 + review_count * 0.5)
  forgetting_ratio = 1 - e^(-days_since_last / half_life)
  if forgetting_ratio > 0.5:
    forgetting_penalty = 0.4   # 遗忘严重
  elif forgetting_ratio > 0.25:
    forgetting_penalty = 0.2   # 需要复习
  else:
    forgetting_penalty = 0

  raw_hours = base_hours * (1 + weakness_boost + forgetting_penalty)

# 归一化使所有科目 raw_hours 之和 == available_hours
total_raw = sum(all raw_hours)
for each subject:
  subject.hours = raw_hours / total_raw * available_hours
  subject.hours = round_to_half(subject.hours)  # 四舍五入到 0.5h
  subject.hours = max(subject.hours, MIN_DAILY[subject.type])

# MIN_DAILY（每科每日最低时长）:
#   数学: 0.5h | 英语: 0.5h | 政治: 0h（基础期可跳过，冲刺/考前 0.5h）| 专业课: 0.5h
# round_to_half() 最小非零值 = 0.5h。若算法输出 < 0.5h 且 MIN_DAILY > 0 → 向上取 0.5h
# 若 MIN_DAILY == 0（基础期政治）→ 不分配时间

# 若保底修正后总和 > available_hours，从 ROI 最低科目依次减时间（0.5h 步长）直到 sum == available_hours
# 若某科已在 MIN_DAILY 保底线上，跳过该科，从下一个 ROI 最低科目减
redistribute_overflow(subjects, available_hours)
```

**提分 ROI 公式：**

```
gap_factor = (target_score - estimated_score) / subject_max_score
  # gap_factor <= 0（已达标）→ 设为 0.1（保底维持）

marginal_factor:
  estimated_ratio < 0.5  → 1.3（低分段，提分快）
  0.5 <= ratio < 0.7     → 1.0
  ratio >= 0.7           → 0.7（高分段，边际递减）

roi_score = gap_factor * marginal_factor * phase_weight
normalize(roi_score) = roi_score[s] / sum(roi_score)
```

### Step 3：生成任务描述

```
for each subject:
  if 有 tracker 近 3 天 stuck_points[].normalized_topic:
    task = "复习{normalized_topic}，再做 N 道同类型"
    priority = "复习"
  elif forgetting_penalty > 0:
    # last_studied_content = 该科最近一天 tracker 中 plan[].topic（如"极限-洛必达法则"）
    task = "快速回顾{last_studied_content}，然后继续新内容"
    priority = "回顾+新学"
  else:
    task = 根据阶段+进度生成具体任务（见任务模板）
    priority = "新学"
```

**任务模板（按阶段）：**

基础期：
| 科目 | 模板 |
|------|------|
| 数学 | "高数第N章{知识点}，看完例题 + 做课后题M道" |
| 英语 | "背单词N个（复习M个旧词）+ 精读真题阅读1篇" |
| 政治 | "马原第N章，看完做配套选择题" |
| 专业课 | "教材第N章，做笔记 + 课后习题" |

强化期：
| 科目 | 模板 |
|------|------|
| 数学 | "{习题集名}第N-M题（{题型}），限时T分钟" |
| 英语 | "真题阅读N篇限时做 + 逐句精析错题" |
| 政治 | "1000题{章节}选择题 + 错题标记" |
| 专业课 | "真题{年份}{题型}，限时作答 + 对答案" |

冲刺期：
| 科目 | 模板 |
|------|------|
| 数学 | "真题{年份}套卷限时3h + 错题归类" |
| 英语 | "作文模板练习1篇 + 真题完形1篇" |
| 政治 | "肖八/肖四第N套选择题 + 大题背诵" |
| 专业课 | "模拟套卷限时 + 薄弱知识点补漏" |

**注意：** AI 不知道用户在用哪本书、做到哪页。第一周任务描述基于通用推荐。后续根据 F4 打勾反馈逐步精确化——第一周是通用建议，第四周是基于真实进度的精确指令。用户主动说"我在用 XX 书""做到第 N 页"时，记入 USER.md 的 `kaoyan_plan_context` 并后续引用。

### Step 4：排序与时段建议

```
排序规则：
  1. 数学/专业课放上午（认知负荷高 → 精力最好时段）
  2. 英语阅读放下午
  3. 政治/英语单词放晚上或碎片时间
  4. 复习类任务插在新学之前

# 在职考生特殊处理
if identity == "working":
  将大块任务拆成 30min-1h 碎片
  标注"通勤可做""午休可做"
```

---

## target_score 科目拆解（F3 首次运行时计算）

如果 USER.md 中 `kaoyan_target_scores` 为空（F2 只写了总分线），F3 首次运行时计算并写入：

```
Step 1: estimated_score[s] = self_eval[s] / 10 * max_score[s]
Step 2: total_gap = retest_line - sum(estimated_score)
Step 3: 按边际提分难度反比分配 gap
  estimated_ratio <= 0.5 → ease_factor = 1.5
  0.5 < ratio < 0.7     → ease_factor = 1.0
  ratio >= 0.7           → ease_factor = 0.5
  raw_gap[s] = ease_factor * max_score[s]
  gap[s] = raw_gap[s] / sum(raw_gap) * total_gap
  target_score[s] = estimated_score[s] + gap[s]
  target_score[s] = min(target_score[s], max_score[s] * 0.9)  # 90%封顶
Step 4: redistribute_overflow()（封顶后溢出重分配到未封顶科目）
Step 5: 单科线约束 target_score[s] = max(target_score[s], single_subject_line[s])
Step 6: 写入 USER.md kaoyan_target_scores + kaoyan_target_achievable + kaoyan_target_total
```

如果 sum(cap) < retest_line（所有科目 90% 封顶后总分仍不够）：
- 写入 USER.md：`kaoyan_target_achievable: false`
- 在首次推送的**第 1 条消息末尾**附加目标缺口提示（仅首次，不每天重复）：

```
目标缺口提示模板：
"按当前水平，所有科目拉到 90% 的上限是 {sum_cap} 分，离 {retest_line} 分的复试线还差 {retest_line - sum_cap} 分。不是说一定够不到——先把每科基础打扎实，后面再看要不要调整目标院校。"
```

---

## 推送消息格式

推送分 **2 条 ai_message**，不合成一条。

### 第 1 条：开场 + 状态感知

根据用户状态选择开场，同一句 7 天内不重复。

**开场去重机制：** 每条 plan_history 记录中包含 `opening_id` 字段（如 `"first_day"`、`"mon"`、`"done_all"`、`"bad_day_recovery"` 等）。生成开场时，读取 plan_history 最近 7 天的 `opening_id` 列表，排除已使用的。若所有候选都在 7 天内用过，从最早使用的开始复用。

**通用开场（无特殊状态时按周几轮换）：**

- 周一："新的一周，咱重新开始算。上周的事不纠结了，今天往前走就行。"
- 周二到周四（任选）："今天任务不多，一件一件来。" / "昨天做得挺好的，今天接着这个节奏。" / "你已经连续学了{N}天了。今天继续。"
- 周五："快周末了。今天把该做的做完，明天可以稍微松口气。"
- 周六："周六。想休息就休息，想学就按这个来，都行。"
- 周日："周日了。如果这周有没补完的，今天可以补一下。不补也行，下周重新来。"

**状态感知开场（优先匹配）：**

| 状态 | 开场 |
|------|------|
| 昨天全部完成 | "昨天全做完了，不错。今天照着来。" |
| 昨天部分完成 | "昨天{done}做了，{skip}没来得及。没事，今天把{skip}补回来。" |
| 昨天没学 | "昨天歇了一天。没事，今天轻一点，先找回手感。" |
| 连续 2 天没回复 | "好几天没收到你的消息了。如果在忙就别管我，等你回来我再排计划。如果是学不动了——没事，我帮你排一个 30 分钟的最低版。做完就算赢。" |
| 连续 5 天全完成 | "你连续 5 天全做完了。不吹不黑，这个执行力已经超过大多数人了。今天正常来。" |
| 崩溃恢复（崩溃锁定期内） | "昨天辛苦了。今天不用多想，就做一件事就好。" |
| 考前 30 天 | "倒计时{N}天。这个阶段不求多，求稳。今天的重点是——不在已经会的题上浪费时间。" |
| 第一天 | "这是你的第一份每日计划。说实话，第一周的计划不会特别准——我还在了解你。你每天告诉我做了什么之后，下周会更懂你的节奏。先跑起来，比什么都重要。" |

### 第 2 条：今日计划

**正常模式（available_hours >= 用户设定的 60%）：**

```
今天的计划（{available_hours}h）：

1. {subject_1}（{hours_1}h）{priority_tag}
   → {task_description_1}

2. {subject_2}（{hours_2}h）{priority_tag}
   → {task_description_2}

3. {subject_3}（{hours_3}h）{priority_tag}
   → {task_description_3}

今天重点：{focus_hint}
做完了告诉我一声
```

priority_tag：复习（遗忘成本触发）/ 补漏（昨天未完成）/ 无标记（常规新学）

focus_hint 生成规则：
- 有复习任务："先复习再新学，不然白学。"
- 最大 ROI 科目："数学极限是你提分空间最大的地方。"
- 薄弱科目有错题："上次{topic}错了，今天重点攻这个。"
- 无特殊："按顺序来就行。"

**轻松模式（昨天 bad_day/tired）：**

```
今天轻一点，不逼你。

1. {subject_1}（{hours_1}h）
   → {简化任务：只做最核心部分}

做了就是赢。做不完也没关系。
```

**最小行动模式（连续 2 天没学）：**

```
今天只需要做一件事：

→ {单一任务，30 分钟以内}

做完了告诉我。不做也行，我明天还会发。
```

**在职考生碎片模板：**

```
今天的计划（碎片时间版，共{available_hours}h）：

通勤（30min）：背单词{N}个
午休（30min）：政治选择题{N}道
下班后（{remaining}h）：
   1. {subject}（{hours}h）→ {task}
   2. {subject}（{hours}h）→ {task}

碎片时间也是时间。今天能做多少做多少。
```

---

## 用户状态机

```
           ┌─────────────────────────────────────┐
           │                                     │
           v                                     │
┌──────────────┐    done_all x3     ┌──────────────┐
│   normal     │ ────────────────→  │   momentum   │
│  100%        │ ←────────────────  │   100%       │
└──────────────┘  done_most/some/   └──────────────┘
     │    ^       done_none              │
     │    │                              │ done_most/
     │    │ done_all/most/some           │ some/none
     v    │                              v
┌──────────────┐                  ┌──────────────┐
│   easy       │                  │   normal     │
│  60%         │                  └──────────────┘
└──────────────┘
     │
     │ done_none x2
     v
┌──────────────┐
│   minimal    │ ←── 崩溃降级可从任何状态强制跳入
│  40% / 2h max│     （锁 3 天 → Day 4 切 easy）
└──────────────┘
     │
     │ 2天无回复（非崩溃锁定期）
     v
┌──────────────┐
│   dormant    │
│  停止推送    │
└──────────────┘
     │
     │ 用户主动发消息
     v
┌──────────────┐
│   easy       │
│  60%         │
└──────────────┘
```

| 当前状态 | 触发条件 | 转向 | 计划量 |
|---------|---------|------|--------|
| normal | 连续 3 天 done_all | momentum | 100%（不加量） |
| normal | bad_day 或 mood==tired | easy | 60% |
| normal | done_none | easy | 60% |
| momentum | done_most / done_some / done_none | normal | 100% |
| momentum | bad_day 或 mood==tired | easy | 60% |
| easy | done_all / done_most / done_some | normal | 100% |
| easy | 连续 2 天 done_none | minimal | 40%（最多 2h） |
| minimal | done_all | easy | 60% |
| minimal | 用户主动发消息（非崩溃锁定期） | easy | 60% |
| minimal | 连续 2 天无回复（非崩溃锁定期） | dormant | 停止推送 |
| dormant | 用户主动发消息 | easy | 60% |

**补充规则：**
- "2天无回复"仅在 `minimal` 状态生效——其他状态有 Cron 推送，不存在"无回复"概念。
- `dormant` 停止所有 Cron 推送，done_*/mood 输入不适用。
- bad_day 且 mood==bad 时，F4 先执行状态转换，然后额外路由到 F6 进行崩溃评估（两个动作不互斥）。
- F6 崩溃降级可从**任何状态**强制覆盖为 minimal（锁 3 天），见下方"F6 崩溃降级优先级"。

**关键：momentum 模式不加量。** 加码 = 惩罚表现好的人 = 导致放弃。

**F6 崩溃降级优先级（覆盖规则）：** F6 崩溃降级 > F3 自身状态机。

1. **强制覆盖**：无论当前状态是什么，立即切为 `minimal`
2. **锁定 3 天**：锁定期内状态机转换条件挂起，不响应 done_all 等信号
3. **Day 4 自动解除**：切为 `easy`（60%）
4. **提前解除**：用户主动说"准备好了""我没事了"等 → 提前解除，切为 `easy`

**锁定期判定逻辑：**
```
读取 memory/kaoyan/crisis_log.md
提取最近一条崩溃记录的日期 last_crisis_date

if today - last_crisis_date <= 3 days:
  → 处于崩溃锁定期
  → kaoyan_plan_state 强制为 "minimal"
  → available_hours = min(base * 0.4, 2.0)
  → 计划只含 1 个任务
  → 状态转换挂起

if today - last_crisis_date == 4 days:
  → 解除锁定
  → kaoyan_plan_state 切为 "easy"
```

---

## 第一周坦诚期

- Day 1：首次推送话术（见开场），计划基于诊断数据生成
- Day 2-3：开场带反馈请求："昨天的计划量怎么样？太多还是太少？你可以直接说'太多了'或'刚好'，我下次调。"
- Day 4-7：不再强调"还在了解你"，仍允许反馈
- Week 2 起：正常模式。反馈过"太多" → 全局 ×0.8；反馈过"太少" → ×1.15

---

## 用户反馈调节

| 用户反馈 | 响应 | 存储 |
|---------|------|------|
| "太多了"/"做不完" | "好，从明天起每天少一点。" | kaoyan_plan_adjustment *= 0.8 |
| "太少了"/"还能加" | "好，明天多给你一点。" | kaoyan_plan_adjustment *= 1.15 |
| "不想学英语" | "好，今天英语先跳过。但下周还是得学。" | 当天跳过，不改长期权重 |
| "今天只有1小时" | "那今天只做一件事。" → 生成 minimal | 仅当天 |
| "我换书了"/"做到XX了" | "好，记下了，之后按新进度来。" | 更新 plan_context |

---

## 阶段切换提醒

跨越阶段时（如基础→强化），当天计划开场增加：
> 从今天开始进入强化期了。接下来的重点从"看懂"变成"做对"——题量会增加，每道题限时。别慌，一步一步来。

---

## Memory 写入

### plan_history.md（每日追加）

```yaml
# memory/kaoyan/plan_history.md
---
- date: "2026-04-05"
  day_number: 1
  mode: "normal"
  available_hours: 4.5
  opening_id: "first_day"
  plan:
    - id: "task_1"
      subject_code: "101"
      subject: "政治"
      topic: "马原-唯物辩证法"
      hours: 0.5
      estimated_minutes: 30
      priority: "新学"
      description: "马原第1章，看完做配套选择题"
    - id: "task_2"
      subject_code: "201"
      subject: "英语"
      topic: "阅读理解-主旨题"
      hours: 1.5
      estimated_minutes: 90
      priority: "新学"
      description: "背单词50个 + 精读真题阅读1篇"
    - id: "task_3"
      subject_code: "347"
      subject: "专业课"
      topic: "教材第1章-基础概念"
      hours: 2.5
      estimated_minutes: 150
      priority: "新学"
      description: "教材第1章，做笔记 + 课后习题"
  focus: "专业课分值最大，今天重点在这。"
  push_time: "08:00"
---
```

**plan_history 字段说明：**
- `id`：任务 ID（如 `task_1`），F4 tracker 复制此字段做打勾关联
- `topic`：知识点标签（如 `马原-唯物辩证法`），F4 tracker 和 F5 周报引用此字段
- `estimated_minutes`：预估时间（分钟）= hours × 60，F4/F5 引用此字段做统计
- `opening_id`：本次使用的开场话术 ID，用于 7 天去重（见下方开场去重机制）

仅保留最近 30 天记录，更早的每次写入时自动删除。

### USER.md 扩展字段

F3 在 F2 写入的基础上新增：

```yaml
kaoyan_plan_adjustment: 1.0    # 反馈调节系数（0.64-1.32）
kaoyan_plan_day_count: 15      # 已推送天数
kaoyan_plan_state: "normal"    # 当前状态机状态
kaoyan_plan_context:           # 用户主动提及时更新
  math_textbook: "张宇高数18讲"
  math_progress: "第5章"
  english_wordbook: "恋练有词"
  english_progress: "Unit 12"
kaoyan_target_scores:          # F3 首次运行时计算并写入
  101: 90
  201: 90
  301: 135
kaoyan_target_achievable: true  # sum(target) >= retest_line
kaoyan_target_total: 315
```

---

## HEARTBEAT.md 配置

```yaml
kaoyan_daily_plan:
  cron: "0 8 * * *"
  cron_working: "0 7 * * *"
  condition: "user.kaoyan_diagnosis_date exists AND user.kaoyan_plan_active != false"
  action: "读取数据 → 运行计划生成引擎 → ai_message 推送 → 写入 plan_history"
```

---

## 与其他 Skill 的数据流

```
F2 诊断 ──USER.md──→ F3 每日计划 ──plan_history──→ F4 打勾追踪
                        ↑                              │
                        │ tracker/{yesterday}.md        │
                        └──────────────────────────────┘
                        ↑
F5 周报 ──weekly_cache──→ recommendations
                        ↑
F6 崩溃 ──crisis_log──→ 锁定期判断
```

---

## 退出机制

用户说"别发了""不想收到计划" → 停止推送 + 写入 USER.md：`kaoyan_plan_active: false`。

---

## 内部术语不暴露

以下术语仅用于 SKILL 内部逻辑，**绝不出现在推送给用户的消息中**：
- 状态机名称：normal、momentum、easy、minimal、dormant
- 技术字段名：plan_history、tracker、crisis_log、plan_adjustment、ROI、phase_weight
- Skill 名称：F3、F4、F5、F6、SKILL.md、RULE-ZERO

用户看到的只有自然语言。例如：
- 不说"进入 easy 模式" → 说"今天轻一点"
- 不说"minimal 计划" → 说"今天只需要做一件事"
- 不说"你的 ROI 分配" → 说"提分空间最大的地方"

---

## 边界与不做的事

| 不做 | 原因 |
|------|------|
| 不做题目推送/内嵌题库 | 用户在纸上做题，不在微信里做 |
| 不做番茄钟/计时 | 微信不适合做计时器 |
| 不自动加量 | momentum 模式不加码，保持节奏比优化效率重要 |
| 不做排行榜 | 排行榜制造焦虑 |
| 不推送超过 2 条消息 | 微信推送太多 = 骚扰 |
| 不预测"能不能考上" | 只给执行计划，不做判断 |

---

## P0 安全信号中断规则

**仅当用户消息包含以下精确关键词时触发。** 使用精确子串匹配，不依赖 AI 判断。

P0 关键词（立即中断计划对话 → RULE-ZERO）：不想活了、想死、去死、自杀、结束生命、活着没意思、不如死了、死了算了、没有我更好、考不上就去死、考不上就不想活了、考不上活着没意义、活着好累不如算了、割自己、伤害自己、想伤害自己、打自己、撞墙、想割腕、想从高处跳下去

P1 关键词（进入安全确认流程）：活着好累、不想醒来、消失就好了、世界没有我、如果我不在了、彻底崩溃、完全失控、撑不住了

**以下不是安全信号，不触发中断**：什么都不想做、不想学了、好烦、好累、不想考了、我是个废物、状态很差。这些走正常的状态机流程（bad_day 或 easy 模式）。

触发 P0 时：
1. 立即中断计划对话
2. 路由到 RULE-ZERO 安全流程
3. 不继续讨论学习计划

触发 P1 时：
1. 进入安全确认流程（"你现在有没有想伤害自己的念头？"）
2. 根据回复决定走 RULE-ZERO 还是恢复计划对话
