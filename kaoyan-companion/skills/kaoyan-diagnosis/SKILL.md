---
name: kaoyan_diagnosis
description: 考研备考诊断——3 分钟了解你的备考全景，找到核心风险和时间缺口。
---

# 考研免费备考诊断（2027 考研）

3 分钟 7 步对话，帮用户算清"时间够不够用"，揭示核心风险。不给解法（解法是付费每日计划的内容）。

## 触发条件

- 用户说"帮我诊断一下""测一测我的水平""考研诊断"等关键词
- AGENTS.md 路由：识别到考研备考意图 + USER.md 中 `kaoyan_diagnosis_date` 为空 → 引导进入诊断
- 用户已做过诊断 → 提示"你 {date} 做过一次诊断，要重新测吗？"

## 安全协议（优先于一切对话逻辑）

**每条用户消息必须先做安全关键词检测，再执行诊断逻辑。** 安全检测使用精确子串匹配，不依赖 AI 判断。

### P0 关键词（立即触发 RULE-ZERO，中断诊断）

自杀类：不想活了、想死、去死、自杀、结束生命、活着没意思、不如死了、死了算了、没有我更好、这个世界没有我会更好

自伤类：割自己、伤害自己、想伤害自己、打自己、撞墙、想割腕、想从高处跳下去

考研场景组合：考不上就去死、考不上就不想活了、考不上活着没意义、活着好累不如算了

**P0 触发后固定响应（不改措辞、不加开导）：**

> 我听到你说的了，我很认真地在听。你现在安全吗？
>
> 如果你需要有人帮忙，可以随时拨打：
> 全国 24 小时心理援助热线：400-161-9995
> 北京心理危机研究与干预中心：010-82951332
> 生命热线：400-821-1215
>
> 我一直在这里。

触发后不继续诊断、不劝说"别想太多"，陪着直到对方说自己安全了。

### P1 关键词（进入安全确认流程）

活着好累、不想醒来、消失就好了、世界没有我、如果我不在了、彻底崩溃、完全失控、撑不住了

**P1 触发后确认话术（固定句式）：**

> 我听到你说的了。在聊下去之前，我需要先确认一件事——
>
> 你现在有没有想伤害自己的念头？

用户回复判定（纯关键词匹配）：
- 包含"有""想过""是""对" → 走 RULE-ZERO
- 包含"没有""没""不会""不是" → 确认安全，从中断处继续诊断（不从头开始）
- 同时命中肯定和否定 → **肯定优先**，走 RULE-ZERO
- 不匹配 → 二次确认："你可以直接告诉我'没有'或'有'，我不会评判你。"

---

## 数据读取

**硬性规则：诊断中所有院校数据、分数线、映射表必须通过 read 工具从知识库文件读取。禁止凭 AI 记忆编造任何院校/分数线/报录比数据。**

诊断依赖 `references/kaoyan-knowledge/` 中的考研数据。执行前用 read 工具加载：

```
read references/kaoyan-knowledge/schools/index.yml          # 院校别名/简称索引
read references/kaoyan-knowledge/national-lines.yml          # 国家线（含各学科门类）
read references/kaoyan-knowledge/self-eval-mapping.yml       # 自评分→预估分映射表
read references/kaoyan-knowledge/schools/{school_code}.yml   # 匹配到院校后读取
```

**如果 read 失败或文件不存在，不得继续诊断，必须告知用户"数据暂时无法加载，请稍后再试"。**

## 对话流程（7 步，总耗时 3-5 分钟）

```
Step 1 目标院校 → Step 2 目标专业 → Step 3 硬指标采集
→ Step 4 各科自评（含校准锚点） → Step 5 每日可用时间 → Step 6 备考开始时间
→ [规则引擎计算] → 输出：诊断报告（4 段） → 转化引导
```

**对话质感要求（被看见感）：** 整个诊断过程要像"学姐在了解你"，不是"填问卷"。具体要求：
- 每步只发一条消息，不合并、不跳步
- 步骤间过渡自然，用院校名/专业名等具体信息衔接（"华东师范大学不错"而非"好的，下一个"）
- Step 4 每科评完后给一句简短的差异化回应（高分低分回应不同）
- 计算前的"我算一下......"要有适当延迟感（2-3 秒）
- 4 段报告之间有间隔（段间 1 秒），不一口气全吐出来

---

### Step 1：目标院校

ai_message：
> 来做个备考体检吧，3 分钟就好。
>
> 先说说，你想考哪个学校？直接打名字就行。

用户输入自由文本。

**处理：**
1. 别名/简称归一化（查 `schools/index.yml` 的 `schools` 段，每条含 `aliases` 列表）
2. 用 read 工具从知识库模糊匹配院校数据（**不凭记忆**）
3. 匹配成功 → ai_message 确认全称，必须包含院校名："华东师范大学，对吧？"（不说"好的，确认"）
4. 匹配失败 → ai_message："没找到这个学校，你再确认一下名字？或者说全称试试"
5. 用户坚持输入不在库的学校 → 降级到国家线方案（见降级方案章节），不阻断流程
6. 多个候选（如"交大"→ 上海交大/西安交大/北京交大） → ai_options 列出让用户选
7. 歧义处理：同一别名命中多个 index 条目时，用 ai_options 让用户选

---

### Step 2：目标专业

ai_message：
> {school_name} 不错。你想考什么专业？

用户输入自由文本。

**处理：**
1. 用户输入与院校 YAML 的 `majors[].name` 模糊匹配（支持常见简称，如"应心"→"应用心理"、"教育学"→"教育学"）
2. 匹配该校该专业数据
3. 匹配失败 → ai_options 列出该校热门专业供选
4. 同校同名跨学院（如"计算机"在计算机学院和软件学院）→ ai_options 让用户选学院

**匹配成功后确定考试科目组合**（从院校 YAML 的 `subjects` 字段读取）。

---

### Step 3：硬指标采集

ai_message：
> 先问几个快问题，帮我更准地估你的水平。

逐题 ai_options，每题一条消息：

**Q3a 英语硬指标：**
> 你过了英语几级？

ai_options：
- 四级没过
- 四级过了（425+）
- 六级过了（425-500）
- 六级高分（500+）

后端映射：四级没过→cet4_fail，四级过了→cet4_pass，六级过了→cet6_pass，六级高分→cet6_high

**Q3b 跨考情况：**
> 你本科学的是 {major_name} 相关专业吗？

ai_options：
- 是，本专业/相近专业 → is_cross_major = false
- 不是，跨考 → is_cross_major = true

**Q3c 备考身份：**
> 你现在是？

ai_options：
- 大三/大四在校生 → undergraduate
- 已毕业全职备考 → graduated_fulltime
- 在职备考 → working
- 二战/三战 → retaker

**Q3d 模考/真题经验**（仅当 Q3c 选"二战/三战"时出现）：
> 上次初试总分多少？

ai_options：
- 没参加过初试
- 200 分以下
- 200-250
- 250-300
- 300-350
- 350+

---

### Step 4：各科自评（含校准锚点）

ai_message：
> 考 {school_name} 的 {major_name}，需要考 {subjects_list}。
>
> 给自己各科打个分吧，1-10 分。

逐科展示 ai_options（1-10），每科附校准锚点说明：

| 分数 | 锚点描述 |
|------|---------|
| 1-2 | 完全没学过，看题目都看不懂 |
| 3-4 | 学过一点皮毛，做题正确率 < 30% |
| 5-6 | 有一定基础，做题正确率约 40-60% |
| 7-8 | 基础扎实，做过真题且正确率 > 60% |
| 9-10 | 非常有把握，真题/模考能拿 80%+ |

科目顺序按该专业考试科目动态生成（政治 → 英语 → 数学（如有）→ 专业课）。

每科评完后 ai_message 给一句简短回应（不超过 10 字）：
- 1-3 分："好，从头来也不晚。"
- 4-6 分："有底子，能提。"
- 7-8 分："这科稳。"
- 9-10 分："大佬，这科我不担心你。"

---

### Step 5：每日可用学习时间

ai_message：
> 每天大概能拿出多少时间学习？实际的，别算上摸鱼时间。

ai_options：
- 2-3 小时（在校/在职，挤时间学） → daily_hours = 2.5
- 4-5 小时（半脱产，还有课/工作） → daily_hours = 4.5
- 6-7 小时（基本脱产，全天备考） → daily_hours = 6.5
- 8 小时以上（全职考研党） → daily_hours = 9.0

---

### Step 6：备考开始时间

ai_message：
> 你打算什么时候正式开始（或者已经开始了）？

ai_options：
- 已经在学了 → start_date = today
- 这个月开始 → start_date = 当月15日（若已过15日则取当天）
- 下个月开始 → start_date = 下月1日
- 暑假开始（7月） → start_date = 7月1日
- 还没想好 → start_date = 下月1日（保守估计）

---

## 规则引擎计算

**内部逻辑不暴露原则：** 以下计算步骤（Step A-E）、参数名、公式、变量名均为内部实现细节，**绝不在用户可见的 ai_message 中出现**。用户看到的只有 4 段报告中的自然语言描述和数字结果。不出现"time_sufficiency""marginal_multiplier""BASE_EFFICIENCY"等内部术语。

收集完毕后：

ai_message：
> 我算一下......

（延迟 2-3 秒，模拟计算感）

### 输入参数

```
input = {
  school: string,          // 院校全称
  major: string,           // 专业全称
  major_code: string,      // 专业代码（如 "045400"）
  subjects: [              // 考试科目列表
    { name, code, full_score, type: "politics"|"english"|"math"|"professional" }
  ],
  hard_indicators: {
    english_level: "cet4_fail"|"cet4_pass"|"cet6_pass"|"cet6_high",
    is_cross_major: boolean,
    identity: "undergraduate"|"graduated_fulltime"|"working"|"retaker",
    prev_exam_score: number | null
  },
  self_eval: { [subject_code]: 1-10 },
  daily_hours: 2.5 | 4.5 | 6.5 | 9.0,
  start_date: "YYYY-MM-DD",
  exam_date: "2026-12-19"   // 2027考研初试预计日期
}
```

### 数据查询

**从知识库文件 read 读取**（不凭记忆，不编造）：

```
kb_data = {
  retest_line: number,         // 该校该专业复试线（最新年）
  retest_line_source: string,  // 来源 URL
  retest_line_year: number,    // 数据年份
  national_line: {
    total: number,             // 国家线 A 区总分
    single_100: number,        // 单科满分=100 线
    single_gt100: number       // 单科满分>100 线（不乘2，无论满分150还是300）
  },
  admission_ratio: number,     // 报录比（如 8:1 记为 8）
  difficulty_tier: "S"|"A"|"B"|"C",
  subject_avg: { [code]: number } | null
}
```

缺复试线时降级用国家线（通过专业的 `national_line_category` 查 `national-lines.yml`），输出标注"以国家线为参考，该校实际复试线可能更高"。

### Step A：分数估算（自评 + 硬指标 → 预估卷面分）

**自评映射表（基础预估分）：**

政治/英语（满分 100）：

| 自评 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|------|---|---|---|---|---|---|---|---|---|---|
| 基础分 | 20 | 30 | 38 | 45 | 52 | 60 | 67 | 75 | 82 | 90 |

数学/专业课（满分 150）：

| 自评 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|------|---|---|---|---|---|---|---|---|---|---|
| 基础分 | 20 | 35 | 50 | 65 | 78 | 90 | 102 | 115 | 128 | 140 |

专业综合（满分 300）：

| 自评 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|------|---|---|---|---|---|---|---|---|---|---|
| 基础分 | 40 | 70 | 100 | 130 | 156 | 180 | 204 | 230 | 256 | 280 |

**硬指标校准修正：**

英语校准（叠加到英语基础分）：
- CET-4 没过 且 自评 >= 5 → -5
- CET-6 高分(500+) 且 自评 <= 5 → +5
- CET-4 过了 且 自评 <= 3 → +3

跨考校准（叠加到专业课基础分）：
- 跨考 且 专业课自评 >= 6 → -10（满分150）/ -20（满分300）
- 非跨考 且 专业课自评 <= 3 → +5（满分150）/ +10（满分300）

二战校准（全科）：
- 二战且有上次总分 → 各科预估分取 max(自评基础分, 上次分数按科拆分估值)

修正后裁剪：`estimated = clamp(base + adjustment, 0, full_score)`

### Step B：计算各科差距

如果有 `subject_avg` → 直接用作各科目标分。

如果没有 → 确定性默认拆分算法：
1. 按满分比例初分：`raw[code] = retest_line * (full_score / total_full_score)`
2. 用国家线单科线做下限裁剪：满分=100用single_100，满分>100用single_gt100
3. 归一化使各科目标之和 == retest_line（差值按满分比例分摊到未被裁剪科目）
4. 四舍五入到整数，四舍五入误差加到满分最大的科目

各科差距：`gap = max(target - estimated, 0)`

### Step C：估算各科每日所需时间

**提分效率参数（唯一定义，Single Source of Truth）：**

BASE_EFFICIENCY（每提 1 分基础小时数）：
- politics: 3.0
- english: 5.0
- math: 4.5
- professional: 4.0

marginal_multiplier（按 current_ratio = 当前分/满分）：
- ratio < 0.4 → 0.6（低分段，提分快）
- 0.4 <= ratio < 0.6 → 1.0（中分段，正常）
- 0.6 <= ratio < 0.75 → 1.5（中高分段，变难）
- ratio >= 0.75 → 2.5（高分段，很难）

每提 1 分小时数 = BASE_EFFICIENCY[type] * marginal_multiplier(ratio)

各科总需时间 = gap * 每提1分小时数

MIN_TOTAL（各科最低保底总学时，即使 gap=0 也需维持学习）：
- politics: 60
- english: 100
- math: 120
- professional_150: 80
- professional_300: 200

subject_total_hours = max(gap * hpp, MIN_TOTAL[key])

### Step D：计算时间缺口

```
total_prep_days = (exam_date - start_date).days
total_available_hours = floor(total_prep_days * daily_hours)

各科每日时间 = subject_total_hours / total_prep_days
```

MIN_DAILY（各科最低每日有效学时）：
- politics: 0.5
- english: 1.0
- math: 1.5
- professional_150: 1.0
- professional_300: 2.5
- professional_408: 2.0（408 特判：4 门综合，内容量大）

```
subject_daily_hours = max(raw_daily, MIN_DAILY[key])
subject_daily_hours = round(subject_daily_hours * 2) / 2   # 四舍五入到 0.5

required_daily_hours = sum(all subject_daily_hours)
time_gap = required_daily_hours - daily_hours
time_sufficiency = daily_hours / required_daily_hours
```

**MIN_TOTAL / MIN_DAILY key 选择规则：**
- politics → "politics"
- english → "english"
- math → "math"
- professional 且 full_score==300 → "professional_300"
- professional 且 code=="408" → MIN_DAILY 用 "professional_408"，MIN_TOTAL 用 "professional_150"
- professional 其他 → "professional_150"

### Step E：风险点识别

按优先级从高到低检测，**命中第一个就作为主风险**：

#### Risk 1：单科致命短板（最高优先级）
触发：某科预估分 < 该科国家线单科线
标题："你的{subject}可能过不了国家线。"
解释：告知单科线要求、当前预估、差距。"总分再高，单科不过线一样白搭。"

#### Risk 2：备考时间过短
触发：remaining_days < 180 且 total_gap > 60 且 time_sufficiency >= 0.8 且未命中 Risk 1
标题："留给你的时间不多了。"
解释：距考试天数、需提分数、月均进步要求。

#### Risk 3：时间结构性矛盾
触发：time_sufficiency < 0.8 且未命中 Risk 1-2
标题："你的核心矛盾不是学什么，是时间不够分。"
解释：需提分数、每日可用时间、每日所需时间、缺口。

#### Risk 4：报录比过高
触发：admission_ratio >= 10 且 difficulty_tier == "S" 且未命中 Risk 1-3
标题："你的对手比你想的多。"
解释：报录比数据，"刚好过复试线其实不够"。
**降级态屏蔽：** 当院校不在数据库（使用国家线降级）时，报录比为"暂无数据"，此 Risk 不可触发。

#### Risk 5：数学零基础
触发：math_eval <= 2 且科目含数学 且未命中 Risk 1-4
标题："数学从头学，时间要翻倍。"
解释：数学不能突击，前 3 个月可能看不到分数提升。

#### Risk 6：目标偏高
触发：total_gap > 120 且 difficulty_tier in ["S","A"] 且 time_sufficiency >= 0.8 且未命中 Risk 1-5
标题："目标和现状的差距需要正视。"
解释：分差、月数、是否需要保底方案。

#### Risk 7：408 综合科目风险
触发：subject.code == "408" 且该科 gap 为所有科目中最大 且未命中 Risk 1-6
标题："408 是你的定时炸弹。"
解释：4 门课都要学，时间容易不够用。

#### Risk 8：无明显风险（兜底）
触发：Risk 1-7 均未命中
标题："目前没有明显的风险点。"
解释：数据上合理，但最大敌人是执行力。

**次要风险：** 主风险之外还命中的其他风险，在第 4 段优势文字末尾附一句："另外注意：{secondary_risk_brief}。"

---

## 输出模板

分 **4 段** ai_message 输出，段间间隔 1 秒。**不包含阶段方向和分数目标**。

**全程中文原则：** 所有 ai_message 必须使用中文。不出现英文变量名、公式、技术术语。字段名（如 difficulty_tier）仅在内部计算和 USER.md 写入时使用，不在用户可见消息中出现。

### 第 1 段：目标画像

ai_message：
> **你的目标**
>
> {school_name} {major_name}
> 2026 年复试线：{retest_line} 分
> 报录比：{admission_ratio}:1
> 难度档位：{difficulty_tier} 档
>
> {difficulty_comment}
>
> 数据来源：{retest_line_source_label}

difficulty_comment：
- S 档："竞争激烈，需要扎实准备。"
- A 档："有难度，但目标合理。"
- B 档："目标务实，认真准备把握很大。"
- C 档："目标可达，重点是别在某一科翻车。"

降级态（无该校复试线）：复试线处显示国家线 + 标注"以国家线为参考，该校实际复试线可能更高"。

### 第 2 段：现状评估

ai_message：
> **你的现状**
>
> | 科目 | 你的预估 | 复试线参考 | 差距 |
> |------|---------|-----------|------|
> | {subject} | {estimated} | {target} | {gap_display} |
> | ... | ... | ... | ... |
> | **合计** | **{est_total}** | **{retest_line}** | **{total_gap}** |
>
> {calibration_note}
>
> {status_comment}

calibration_note（**仅在硬指标校准实际修正了预估分数时才显示**，如果校准条件不满足、adjustment 为 0 则不显示此行）：
- 有 CET 校准且 adjustment != 0："（英语预估参考了你的{cet_level}成绩）"
- 有跨考校准且 adjustment != 0："（专业课预估考虑了跨考因素）"
- 有二战校准且取了上次分数："（参考了你上次初试 {prev_score} 分的成绩）"

status_comment：
- gap <= 0："你现在的水平已经够线了，重点是保持和避免失误。"
- gap 1-30："差距不大，踏实学几个月就能补上。"
- gap 31-60："有一定差距，需要系统规划，不能随便学学。"
- gap 61-100："差距明显，必须全力以赴，每天都不能浪费。"
- gap > 100："坦白说差距比较大。不是不可能，但需要比大多数人更拼。"

已超目标的科目差距显示为"-N（已超）"。

### 第 3 段：时间精算

ai_message：
> **时间账本**
>
> 距离考试还有 {remaining_days} 天，你每天 {daily_hours} 小时，总共 {total_hours} 小时。
>
> 按你的差距和当前水平，各科每天至少需要：
> | 科目 | 每日需要 | 说明 |
> |------|---------|------|
> | {subject} | {need_hours}h | {subject_comment} |
> | ... | ... | ... |
> | **合计** | **{required_daily_hours}h** | |
>
> {time_verdict}

time_verdict：
- sufficiency >= 1.2："时间充裕，关键是每天真的执行。"
- sufficiency >= 1.0："时间刚好够，不能有大段摸鱼。"
- sufficiency >= 0.8："时间有点紧。要么增加学习时间，要么在某科做取舍。"
- sufficiency >= 0.6："时间明显不够。{primary_risk_brief}"
- sufficiency < 0.6："时间缺口很大。需要认真考虑调整目标或大幅增加每日时间。"

subject_comment（基于计算数据生成）：
- gap 最大的科目："差距最大，是提分主战场"
- gap == 0："已达标，保持就行"
- type=="math" 且 ratio<0.4："提分效率高，值得多投入"
- full_score >= 300："分值占比大，不能放"

### 第 4 段：核心风险点 + 一句优势

ai_message：
> **你最大的风险**
>
> {risk_title}
>
> {risk_explanation}
>
> **不过也有好消息：** {advantage_text}

advantage_text（从数据中找最大正面信号）：
- 某科自评高："你的{subject}底子不错，这在考{school}的人里算中上。"
- 时间充裕："你的备考时间比大多数人充裕，这是最大的优势。"
- 目标合理（B/C档）："你的目标选得务实，这比盲目冲名校聪明多了。"
- gap 小："差距不大，你离目标比你想的近。"
- 二战："你有一次实战经验，知道考场什么感觉，这比第一次考的人强。"

**第 4 段不给任何"怎么补"的方向建议、阶段划分或分数目标。诊断只揭示缺口，不给解法。** 优势文案中也不得出现"省下来的时间全给 XX""重点放在 XX 上"等科目分配建议。

---

## 转化引导

报告 4 段输出完毕后，停顿 2 秒，发送转化引导。

**通用版 ai_message：**
> 这就是你目前的备考全景。知道了差多少、时间够不够——但真正难的是，明天早上起来，第一个小时学什么？
>
> 和你自己列的"今天学 3 小时英语"不一样——每日计划会告诉你这 3 小时里前 40 分钟做什么、中间 1 小时做什么、最后怎么检验今天有没有白学。
>
> 要试试吗？

ai_options：
- 看看我的计划会长什么样 → 路由到 F3 每日计划（付费入口）
- 先不了，我自己想想 → ai_message："好的，诊断结果我帮你存着了，随时可以来看。有问题也可以直接问我。"（存入 USER.md）

**风险点特化引导**（替代通用版，当风险点特别突出时）：

Risk 3（时间不够）特化：
> 你的时间缺口是 {gap_hours} 小时。在不增加每日时间的前提下，最有效的方法是——精确控制每天的时间分配，一个小时都不浪费。
>
> 要看看你的版本吗？

Risk 1（单科短板）特化：
> {subject}过不了线，其他科再高也白搭。这科需要一个专门的突击方案。
>
> 要看看你的保底方案吗？

Risk 2（时间过短）特化：
> {remaining_days} 天，一天都浪费不起。最怕的是花两周做计划、改计划、纠结计划。
>
> 要让我直接帮你排好吗？

---

## USER.md 写入

### 写入时机

**4 段报告输出完毕后立即写入**，不等转化引导结束。写入使用 write 工具。

### 写入位置

USER.md 的 `## 考研备考（2027 考研）` 段落。如果该段落不存在则新建；如果已存在则覆盖所有字段。

### 字段定义（与 Layer-2 §2.4 完全对齐）

```yaml
## 考研备考（2027 考研）

kaoyan_target_school: ""          # 院校全称，如"华东师范大学"
kaoyan_target_major: ""           # 专业全称，如"应用心理"
kaoyan_target_major_code: ""      # 专业代码，如"045400"
kaoyan_retest_line: 0             # 复试线分数（降级时为国家线）
kaoyan_retest_line_year: 0        # 复试线数据年份
kaoyan_hard_indicators:           # 硬指标
  english_level: ""               # cet4_fail / cet4_pass / cet6_pass / cet6_high
  is_cross_major: false           # 是否跨考
  identity: ""                    # undergraduate / graduated_fulltime / working / retaker
  prev_exam_score: null           # 上次初试总分（仅二战+），非二战为 null
kaoyan_self_eval: {}              # 各科自评 1-10，key 为科目代码（如 "101", "201", "347"）
kaoyan_estimated_scores: {}       # 各科预估分 + "total" 总分，key 为科目代码
kaoyan_daily_hours: 0             # 每日可用学习时间（2.5/4.5/6.5/9.0）
kaoyan_start_date: ""             # 备考开始日期 YYYY-MM-DD
kaoyan_gap: 0                     # 总分差距（max(retest_line - est_total, 0)）
kaoyan_time_sufficiency: 0        # 时间充足率（daily_hours / required_daily_hours，保留两位小数）
kaoyan_required_daily_hours: 0    # 每日所需时间（各科每日需要之和）
kaoyan_risk_point: ""             # 主风险点中文描述（如"时间结构性矛盾""单科致命短板"）
kaoyan_difficulty_tier: ""        # S / A / B / C
kaoyan_diagnosis_date: ""         # 诊断完成日期 YYYY-MM-DD
kaoyan_diagnosis_version: ""      # 首次为"v1"，重新诊断时自增（"v2", "v3"...）
```

### 示例（填充后）

```yaml
## 考研备考（2027 考研）

kaoyan_target_school: "华东师范大学"
kaoyan_target_major: "应用心理"
kaoyan_target_major_code: "045400"
kaoyan_retest_line: 347
kaoyan_retest_line_year: 2026
kaoyan_hard_indicators:
  english_level: "cet6_pass"
  is_cross_major: true
  identity: "working"
  prev_exam_score: null
kaoyan_self_eval:
  "101": 5
  "201": 5
  "347": 3
kaoyan_estimated_scores:
  "101": 52
  "201": 52
  "347": 100
  total: 204
kaoyan_daily_hours: 2.5
kaoyan_start_date: "2026-07-01"
kaoyan_gap: 143
kaoyan_time_sufficiency: 0.63
kaoyan_required_daily_hours: 4.0
kaoyan_risk_point: "时间结构性矛盾"
kaoyan_difficulty_tier: "S"
kaoyan_diagnosis_date: "2026-04-04"
kaoyan_diagnosis_version: "v1"
```

### 版本号规则

- 首次诊断：`kaoyan_diagnosis_version: "v1"`
- 重新诊断：读取当前版本号，数字部分 +1（如 "v1" → "v2"）
- 所有字段用新诊断结果覆盖

**字段用途（下游 skill 引用）：**

| 字段 | 引用方 | 用途 |
|------|--------|------|
| kaoyan_retest_line | F3 每日计划 | 计算每日目标进度 |
| kaoyan_self_eval + kaoyan_hard_indicators | F3 每日计划 | 确定各科起始难度和校准 |
| kaoyan_daily_hours | F3 每日计划 | 限制每日任务总量 |
| kaoyan_risk_point | F3/F6 | 计划侧重点 / 崩溃时回引诊断 |
| kaoyan_time_sufficiency | F5 周报 | 评估进度是否跟上 |
| kaoyan_gap | F4 打勾追踪 | 计算已完成比例 |
| kaoyan_estimated_scores | F5 周报 | 与实际模考分数对比 |
| kaoyan_diagnosis_date | 全局 | 判断是否需要重新诊断 |

**重新诊断：** 用户可随时重新诊断（换目标/更新自评），新结果覆盖旧字段，kaoyan_diagnosis_version 自增。

---

## 降级方案

当用户输入的院校/专业不在数据库中时：

| 缺失数据 | 降级规则 | 输出标注 |
|---------|---------|---------|
| 复试线 | 用国家线 A 区总分（通过 national_line_category 查） | "以国家线为参考，该校实际复试线可能更高" |
| 各科参考分 | 用确定性默认拆分算法 | 不标注 |
| 报录比 | 标注"暂无数据" | "报录比数据收集中" |
| 难度档位 | 根据学校层次推断：985→S/A，211→A/B，双非→B/C | 不标注 |
| 单科国家线 | 不可降级，必须有 | — |

降级时：时间精算照常进行；第 1 段标注数据来源为"国家线"；第 4 段不生成 Risk 4。

---

## 边界与不做的事

1. **不做择校推荐**：只诊断用户已选目标的可行性，不替用户选学校
2. **不做模拟考试**：基于自评+硬指标校准，不做真题测试
3. **不给具体每日计划**：只揭示缺口，"怎么补"是付费内容
4. **不给阶段方向和分数目标**：这些是付费内容
5. **不预测"能不能考上"**：只呈现数据和缺口，不做概率判断
6. **不要求注册/登录**：诊断是获客入口，零门槛

---

## 数据有效期检查

诊断引擎启动时检查 `national-lines.yml` 中最新年份是否 >= 当前年份。如果过期，在输出中标注"数据待更新，仅供参考"。

考试日期：2027 考研初试预计 2026-12-19（周六）。教育部通常 9 月公布正式日期，届时更新。
