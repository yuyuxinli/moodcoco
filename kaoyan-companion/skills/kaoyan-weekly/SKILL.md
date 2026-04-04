---
name: kaoyan_weekly
description: 考研周报——每周日 20:00 基于 7 天打勾数据生成学习报告，先展示进步再温和提薄弱，输出下周建议供 F3 消费。触发方式：Cron 周日 20:00。
---

# 考研周报

把散落在 7 天打勾数据里的微小进步，汇聚成一个"我确实在往前走"的确定感。永远先说进步，再温和提薄弱。不是报表，是可可在跟她聊这周的情况。

## 触发条件

```
触发时间: 每周日 20:00（Cron）
前置条件: 本周 memory/kaoyan/tracker/ 目录中有 ≥ 3 天文件（含 done_none/bad_day）
不满足时: 不发周报。轻量关怀："这周辛苦了。下周想让我帮你盯着学习进度吗？"
全部 7 天 done_none/bad_day: 不发周报。走关怀："这周不容易吧。不想聊学习也行，聊聊别的？"
```

**退出机制：** 用户说"别搞这种总结" → "好，不发了。" → USER.md 标记 `kaoyan_weekly_preference: disabled`。

**连续拒绝降频：** 连续 3 次 Poll 选"看看就好"或不回复 → 降为隔周触发。用户主动选"想聊聊" → 恢复每周。

## Cron 配置

```json
{
  "name": "kaoyan-weekly-report",
  "schedule": { "kind": "cron", "expr": "0 20 * * 0", "tz": "Asia/Shanghai" },
  "sessionTarget": "main",
  "wakeMode": "now",
  "payload": {
    "kind": "systemEvent",
    "text": "[kaoyan-weekly] 周日 20:00，为用户生成本周学习报告。遍历 memory/kaoyan/tracker/{周一到周日}.md 本周数据 + weekly_cache 上周数据，按 SKILL.md 流程生成周报。"
  }
}
```

**与通用 weekly-reflection 的关系：** 考研用户周日 20:00 走 kaoyan-weekly，非考研用户走 weekly-reflection。同一时间槽，AGENTS.md 路由分流。

---

## 数据读取

```
# 1. 本周 tracker 数据（F4 写入）
遍历 memory/kaoyan/tracker/{本周一到本周日}.md
→ 7 个文件，不存在的 = missing_day

# 2. 上周缓存（本 skill 上次写入）
read memory/kaoyan/weekly_cache/{上周}.json

# 3. 用户档案
read USER.md → kaoyan_target_school, kaoyan_target_score, kaoyan_self_eval, kaoyan_daily_hours

# 4. 崩溃记录（可选）
read memory/kaoyan/crisis_log.md → 本周是否有崩溃事件
```

---

## 数据汇总规则

### Step 1：本周原始数据

```
打卡天数 = count(status != null)
有效学习天数 = count(status in [done_all, done_most, done_some])
完全完成天数 = count(status == done_all)
状态不好天数 = count(mood == "bad")
```

### Step 2：各科汇总

```
按 subject 分组（遍历所有 tracker 文件的 plan[] + completed[]）：

各科完成率:
  plan_count = count(plan[] where subject == 该科)
  done_count = count(completed[] where done==true 且对应 plan 的 subject == 该科)
  completion_rate = done_count / plan_count * 100
  last_week_rate = 从 weekly_cache.summary.subjects[科目名].completion_rate 读取（首周无数据标"首周"）

各科计划时长:
  estimated_minutes = sum(plan[].estimated_minutes where subject == 该科)

薄弱点:
  stuck_topics = group_by(stuck_points[].normalized_topic) → 按出现次数降序
```

### Step 3：进步检测

```python
def detect_progress(this_week, last_week):
    signals = []
    
    # 1. 完成率提升（按科目）
    for subject in this_week.subjects:
        if last_week and subject.completion_rate > last_week[subject].completion_rate:
            signals.append(type="completion_up", subject, delta)
    
    # 2. 学习量提升
    for subject in this_week.subjects:
        if last_week and subject.done_count > last_week[subject].done_count:
            signals.append(type="volume_up", subject)
    
    # 3. 连续性提升
    if last_week and this_week.active_days > last_week.active_days:
        signals.append(type="consistency_up")
    
    # 4. 坚韧信号
    if this_week.bad_days > 0 and this_week.active_days >= 3:
        signals.append(type="resilience")
    
    # 5. 首周
    if not last_week:
        signals.append(type="first_week")
    
    # 6. 薄弱点减少
    for topic in last_week.stuck_topics:
        if topic not in this_week.stuck_count or this_week.stuck_count[topic] == 0:
            signals.append(type="weakness_resolved", topic)
        elif this_week.stuck_count[topic] < last_week.stuck_count[topic]:
            signals.append(type="weakness_improving", topic)
    
    return signals
```

### Step 4：薄弱点检测

```python
def detect_weakness(this_week):
    weaknesses = []
    
    # 1. 完成率 < 50%
    for subject where completion_rate < 50:
        weaknesses.append(type="low_completion", subject)
    
    # 2. 同一 normalized_topic 出现 >= 2 次
    for topic where stuck_count >= 2:
        weaknesses.append(type="recurring_stuck", topic)
    
    # 3. 某科连续 2 天 task done=false
    for subject where consecutive_skip >= 2:
        weaknesses.append(type="skipped_subject", subject)
    
    return weaknesses
```

consecutive_skip 计算：遍历本周 tracker（按日期正序），该科 task done=false → skip_count+1，done=true → 重置。missing_day 不计入。取最大值。

---

## 周报输出（4 段 ai_message，分段发送）

### Part 1：开场 + 本周概览

```
场景 A（有进步）: "这周你学了 {active_days} 天，我帮你数了一下——"
场景 B（首周）: "你的第一份周报来了。虽然才一周，但数据已经开始有形状了——"
场景 C（数据少但触发）: "这周事情多吧？不过你还是来打了 {active_days} 天卡，这本身就挺好的——"
```

### Part 2：进步亮点

**永远至少找到一个正面信号。** 正面框架——同一组数据，强调好的那一面。

进步信号优先级（从上到下选第一个可用的）：
1. 完成率提升 → "{科目}任务完成率从上周的{last}%涨到了{this}%（+{delta}%）"
2. 薄弱点攻克 → "上周卡住的{topic}，这周没再出现"
3. 学习量提升 → "这周完成了{n}个{科目}任务，比上周多了{delta}个"
4. 连续性提升 → "这周打卡{n}天，比上周多了{delta}天"
5. 坚韧信号 → "这周有{bad_days}天状态不好，但你还是学了{active_days}天"
6. 首周保底 → "第一周就打了{n}天卡。下周我就能帮你看出更多了"

多个进步信号时全部展示：
```
"看看这周的变化——
· 数学：6 个任务完成了 5 个（83%），比上周多完成了 2 个
· 英语：4 个任务完成了 3 个（75%）
· 政治：马原读到了第 4 章，3 个任务全部完成"
```

### Part 3：薄弱点 + 行动指引

**薄弱点不超过 2 个，每个必须带具体行动。**

有薄弱点：
```
"有个地方值得注意——
{weakness_1}
{weakness_2（可选）}

下周建议：
· {action_1}
· {action_2（可选）}"
```

没有薄弱点：
```
"这周没有特别明显的短板。下周保持节奏就好，我会继续帮你盯着。"
```

**薄弱点表述规则（温和 + 具体）：**

| 类型 | 错误 | 正确 |
|------|------|------|
| 低完成率 | "你英语只完成40%，太低了" | "英语任务完成率还在爬坡（40%），下周帮你拆小一点" |
| 高频卡住 | "你极限又卡住了3次" | "极限的洛必达法则这周卡了3次，下周计划里加几道专项练习" |
| 科目缺勤 | "你这周政治完全没学" | "政治这周没顾上，下周哪怕每天15分钟也行，别断太久" |

**行动指引规则（具体 + 可执行）：**
1. 高频卡住知识点 → "下周数学计划里会加几道洛必达法则专项练习"
2. 低完成率 → "英语任务拆小一点，每个任务量减20%"
3. 缺勤科目 → "政治下周每天15分钟，先捡回节奏"
4. 完成率停滞 → "数学完成率两周没变，下周调整任务安排"

### Part 4：结尾 + Poll

```
标准: "下周的计划会根据这周的数据调整。加油，我盯着呢。"
状态差: "这周不容易，但你没放弃。下周我们轻一点来。"
特别好: "这周完成率都挺高的。下周见。"
```

Poll：
```json
{
  "tool": "message",
  "action": "poll",
  "pollQuestion": "这周有什么想跟我说的吗？",
  "pollOption": ["想聊聊", "看看就好"],
  "pollMulti": false
}
```

| 选择 | 走向 |
|------|------|
| "想聊聊" | 进入自由对话 |
| "看看就好" | "好，下周见。" |
| 不回复 | 不追问 |

---

## 进化感设计

周报不是每周格式一样只换数字。随数据积累，深度和个性化提升：

| 维度 | 第 1 周 | 第 2-3 周 | 第 4 周+ |
|------|--------|----------|---------|
| 数据对比 | 无基线 | 本周 vs 上周 | 多周趋势 |
| 进步表述 | "第一周就打了5天卡" | "完成率从60%涨到80%" | "数学完成率连续4周在涨，从50%到83%" |
| 薄弱点精度 | 科目级 | 知识点级 | 知识点+频次+跨周模式 |
| 行动指引 | 泛化 | 科目级 | 个性化策略 |
| 情绪洞察 | 无 | 有 | 跨周趋势 |
| 坦诚说明 | 有（"数据还不多"） | 有 | 无（进化已自证） |

```python
def get_report_depth(week_number):
    if week_number == 1:
        return { comparison: 'none', weakness: 'subject', action: 'general', emotion: False, disclaimer: True }
    elif week_number <= 3:
        return { comparison: 'binary', weakness: 'topic', action: 'targeted', emotion: True, disclaimer: True }
    else:
        return { comparison: 'trend', weakness: 'pattern', action: 'personalized', emotion: True, disclaimer: False }
```

### 首周特殊模板

```
"你的第一份周报来了。

这周你学了 {active_days} 天：
· 数学：安排了 {math_plan} 个任务，完成了 {math_done} 个
· 英语：安排了 {eng_plan} 个任务，完成了 {eng_done} 个
· 政治：{pol_summary}

这是起点。从下周开始，我就能帮你看出哪里在进步、哪里要加把劲了。
每周积累的数据越多，这份报告就越懂你。"
```

---

## 数据存储

### 周报缓存写入

`memory/kaoyan/weekly_cache/YYYY-WNN.json`

```json
{
  "week": "2026-W15",
  "date_range": "2026-04-07 ~ 2026-04-13",
  "week_number": 3,
  "summary": {
    "active_days": 6,
    "complete_days": 4,
    "bad_days": 0,
    "subjects": {
      "数学": {
        "plan_count": 6,
        "done_count": 5,
        "completion_rate": 83,
        "estimated_minutes": 540,
        "stuck_topics": { "极限-洛必达法则": 2, "极限-夹逼准则": 1 }
      },
      "英语": {
        "plan_count": 4,
        "done_count": 3,
        "completion_rate": 75,
        "estimated_minutes": 240,
        "stuck_topics": { "阅读理解": 1 }
      },
      "政治": {
        "plan_count": 3,
        "done_count": 3,
        "completion_rate": 100,
        "estimated_minutes": 180,
        "stuck_topics": {}
      }
    }
  },
  "progress_signals": [
    {"type": "completion_up", "subject": "数学", "delta": 23},
    {"type": "consistency_up", "this_week": 6, "last_week": 5}
  ],
  "weaknesses": [
    {"type": "recurring_stuck", "topic": "极限-洛必达法则", "count": 2}
  ],
  "recommendations": {
    "math_focus": "洛必达法则专项练习",
    "english_adjustment": "阅读任务拆小，每次 1 篇",
    "politics_minimum": "保持每天 30min",
    "plan_intensity": "normal"
  }
}
```

**`progress_signals[].type` 枚举值：** `completion_up` | `weakness_resolved` | `weakness_improving` | `volume_up` | `consistency_up` | `resilience` | `first_week`

**字段说明：**
- `summary.subjects` 使用中文科目名作为 key（"数学"/"英语"/"政治"），与 tracker 的 `plan[].subject` 一致
- `plan_count`/`done_count`/`completion_rate`：tracker 文件 plan[]+completed[] 聚合
- `estimated_minutes`：plan[].estimated_minutes 汇总
- `stuck_topics`：stuck_points[].normalized_topic 按出现次数聚合
- `progress_signals[].subject` 使用中文科目名（与 `summary.subjects` key 一致）
- **不含 accuracy/correct/error_types**——F4 不采集题目级正确率
- `recommendations`：JSON 格式，供 F3 机器消费。话术中以对话语气呈现同样内容

**运行时对象 → weekly_cache JSON 路径映射：**

| 运行时属性 | JSON 路径 |
|-----------|----------|
| `this_week.active_days` | `summary.active_days` |
| `this_week.complete_days` | `summary.complete_days` |
| `this_week.bad_days` | `summary.bad_days` |
| `this_week.subjects` | `summary.subjects` |
| `this_week[科目名].completion_rate` | `summary.subjects[科目名].completion_rate` |
| `this_week[科目名].plan_count` | `summary.subjects[科目名].plan_count` |
| `this_week[科目名].done_count` | `summary.subjects[科目名].done_count` |
| `this_week.stuck_topic_counts` | `summary.subjects[科目名].stuck_topics` |
| `last_week.*` | 上周 weekly_cache 同路径 |

**缓存保留：** 最近 8 周，超过的自动清理。

### F3 消费接口

F3 每日计划生成时读取最新 `weekly_cache/YYYY-WNN.json` 的 `recommendations`：
- `plan_intensity`：控制整体强度（normal/reduced/minimum）
- `math_focus`/`english_adjustment`/`politics_minimum`：影响每日任务分配

---

## 异常处理

| 场景 | 处理 |
|------|------|
| tracker < 3 天 | 不发周报。"这周辛苦了。下周想让我帮你盯着学习进度吗？" |
| 某科目 0 数据 | 略过该科。仅在行动指引温和提及 |
| 全部 done_none/bad_day | 不发周报。走关怀 |
| 首周无缓存 | 首周模板，不做对比 |
| 上周/本周维度不一致 | 仅对比有双周数据的科目 |
| 用户回复命中 RULE-ZERO P0/P1 精确关键词 | 立即中断周报，按 AGENTS.md §安全协议执行 RULE-ZERO 流程 |
| 用户反感 | 停止，标记 preference |
| tracker YAML 缺少必填字段（无 `status`、无 `plan`） | 跳过该天，视为 missing_day |
| `completed[].task_id` 找不到对应 `plan[].id` | 忽略该条 completed 记录 |
| `weekly_cache` JSON 格式损坏或缺字段 | 视为无上周数据，走首周逻辑 |
| `mood` 值不在枚举范围内 | 视为 `normal` |

---

## 硬规则

1. **永远先说进步**——第一个数据段永远正面。没有进步也找"没放弃"
2. **不做排名**——不跟其他用户比。社交比较对低绩效者有害
3. **不施压**——"你这周只学了2天"是禁句。"这周学了2天，有两天状态不太好，没事"才对
4. **薄弱点不超过 2 个**——注意力有限，多了等于没说
5. **行动指引必须具体**——不说"加强数学"，说"洛必达法则多做5道"
6. **对话语气**——不是报表，是可可在聊
7. **数据必须有基线**——"73%"没用，"比上周涨了8%"有用
8. **不为周报而周报**——数据不够就不发
9. **安全优先**——tracker 的 note 或用户回复中命中 RULE-ZERO P0/P1 精确关键词（见 AGENTS.md §安全协议）→ 立即中断周报，按 RULE-ZERO 流程处理
10. **recommendations 必须写入 memory**——周报不是终点，是 F3 下周的输入
11. **只陈述数据变化，不推因果、不预测结果**——"完成率从60%涨到83%"可以，"功夫没白费""后面会顺很多""完成率会更好"禁止

---

## HEARTBEAT.md 配置

```yaml
kaoyan_weekly:
  cron: "0 20 * * 0"
  condition: "user.kaoyan_target_school exists AND user.kaoyan_weekly_preference != 'disabled'"
  action: "遍历本周 tracker → 汇总 → 生成周报 → 写入 weekly_cache"
  note: "考研用户走这个，非考研用户走 weekly-reflection"
```

---

## 数据流

```
F4 tracker/YYYY-MM-DD.md ──读取──→ F5 汇总+分析 ──写入──→ weekly_cache/ ──读取──→ F3 调整下周
                                    │
USER.md ──────读取──→ 用户档案       │
                                    └── 危机信号 → F6
```
