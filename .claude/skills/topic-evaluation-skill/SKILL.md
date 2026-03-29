---
name: topic-evaluation
description: Evaluate topic ideas for 心情可可 WeChat public account using data-driven criteria. Use when brainstorming content topics, evaluating whether a topic is worth pursuing, or when the user mentions '选题', '选题评分', '这个话题行不行', 'topic evaluation', '评估选题', or wants to assess a content idea before writing.
---

# Topic Evaluation

Evaluate content topic ideas for 心情可可 public account against data-driven criteria derived from competitor analysis.

## Context

Read `.claude/product-marketing-context.md` for product positioning and target audience.

- **Target platform**: 微信公众号
- **Target audience**: 18-24 岁高敏感女性
- **Content positioning**: 上层娱乐，底层心理学（Entertainment on surface, psychology underneath）

## References

### 视频类竞品 (YouTube: Psych2Go + TSOL)
- [content-pillars-video.md](references/content-pillars-video.md) — 6 content pillars with sub-topics and mix ratios
- [psych-drivers-video.md](references/psych-drivers-video.md) — Psychological drivers, 7-dimension checklist, emotion triggers
- [title-templates-video.md](references/title-templates-video.md) — 18 title templates with formulas and examples

### 图文类竞品 (Instagram: The Holistic Psychologist)
- [content-pillars-instagram.md](references/content-pillars-instagram.md) — Instagram 图文帖内容支柱与互动效率
- [psych-drivers-instagram.md](references/psych-drivers-instagram.md) — 图文形式下的心理驱动力与互动模式
- [title-templates-instagram.md](references/title-templates-instagram.md) — Instagram caption 开头句式与图片文案模板

## Workflow

```
Input: A topic idea (e.g., "讨好型人格", "为什么深夜容易 emo")
                          ↓
Step 1 — PILLAR MATCH: Identify which content pillar this belongs to
Step 2 — ANGLE SEARCH: Find the most compelling angle using psych drivers
Step 3 — PSYCH CHECK: Run 7-dimension evaluation
Step 4 — TITLE DRAFT: Generate 3-5 title candidates
Step 5 — VERDICT: Go / Optimize / Kill
```

### Step 1: Pillar Match

Read [content-pillars.md](references/content-pillars.md). Map the topic to one of the 6 pillars:

| Pillar | Core Theme | Searchable/Shareable |
|--------|-----------|---------------------|
| A | 情绪自我觉察 | Both |
| B | 恋爱心理解码 | Shareable 为主 |
| C | 社交能量管理 | Shareable 为主 |
| D | 趣味心理测试 | Shareable 为主 |
| E | 成长叙事 | Shareable 为主 |
| F | 原生家庭与依恋模式 | Both |

**If no pillar matches**: Flag as off-strategy. Can still proceed but note the risk.

**Check monthly mix**: Is this pillar already over-represented this month? Reference the target ratio: A:B:C:D:E:F = 20:25:10:15:15:15.

### Step 2: Angle Search

Read [psych-drivers.md](references/psych-drivers.md). For the given topic, identify:

**1. Primary psychological driver** — Which of the 5 driver categories best fits?

| Category | Core Mechanism | Boom Potential | Stability |
|----------|---------------|---------------|-----------|
| A. 自我发现型 | Barnum effect, self-serving bias | ★★★★★ | ★★★ |
| B. 好奇心驱动型 | Information gap, counter-intuitive truth | ★★★★★ | ★★★★ |
| C. 情绪共鸣型 | Pain-point naming, cognitive reframing | ★★★ | ★★★★★ |
| D. 关系洞察型 | Romantic signal reading, toxic relationship awakening | ★★★★ | ★★★ |
| E. 赋能型 | DIY solutions, counter-conventional advice | ★★★ | ★★★★ |

**2. Angle optimization** — Apply these data-backed rules:

- **揭示 > 建议**: Frame as "revealing something hidden" not "giving advice"
- **反直觉 > 正面陈述**: Find the counter-intuitive angle ("你的缺点其实是...")
- **发现框架 > 教育框架**: "You already are X" beats "You should be X"
- **具体行为 > 抽象概念**: Anchor in observable behavior, not abstract traits

**3. Three-layer check** — Which layer does this content serve?

| Layer | Function | Key Triggers | WeChat Metric |
|-------|----------|-------------|---------------|
| 引流层 | Acquisition | Curiosity gap + self-tests | 打开率 |
| 传播层 | Sharing | Identity recognition + emotional resonance | 转发 + 在看 |
| 留存层 | Retention | Cognitive reframing + deep resonance | 完读率 + 关注 |

### Step 3: 7-Dimension Psych Check

Score each dimension. Read [psych-drivers.md](references/psych-drivers.md) for detailed criteria.

| # | Dimension | Pass Criteria | Required? |
|---|-----------|--------------|-----------|
| 1 | 好奇心缺口 | Title creates an information gap the reader can't fill without clicking | **Mandatory** |
| 2 | 自我相关性 | Reader thinks "is this about me?" within 2 seconds | **Mandatory** |
| 3 | 情绪激活 | Triggers at least one emotion: curiosity, resonance, surprise, belonging | Optional |
| 4 | 身份安全性 | Sharing won't damage the reader's social image | Optional |
| 5 | 反直觉性 | Contains at least one "I thought A but actually B" element | Optional |
| 6 | 群体发现感 | Makes reader feel "I'm not the only one" | Optional |
| 7 | 框架正确性 | Uses "discovery" frame, not "education" frame | Optional |

**Scoring**:
- 5+ pass (including #1 and #2) → **Go**
- 3-4 pass → **Optimize** (provide specific fix for each failing dimension)
- <3 pass → **Kill** (suggest alternative angle or different topic)

### Step 4: Title Draft

Read [title-templates.md](references/title-templates.md).

1. Select 2-3 matching templates from the 18 available
2. Generate 3-5 title candidates
3. For each candidate, annotate:
   - Template used
   - Primary psychological hook
   - Expected emotion trigger

**Title quality check** (7 points, from title-templates.md):
- [ ] Has curiosity gap?
- [ ] Has "about me" feeling?
- [ ] Has specificity (concrete behavior/scene, not abstract concept)?
- [ ] Has counter-intuitive or surprise element?
- [ ] Has emotional temperature?
- [ ] Uses natural language (not academic jargon)?
- [ ] Would the target user share this?

**Avoid these low-efficiency patterns**:
- Pure "How to" without constraints
- Brand self-talk ("我们的第一篇...")
- Compilation/collection format
- Correct but boring statements ("心理健康很重要")
- Motivational slogans ("这是你离开的信号")

### Step 5: Verdict

Output a structured evaluation card:

```
## 选题评分卡

**选题**: [original topic]
**推荐角度**: [optimized angle from Step 2]
**所属支柱**: [pillar letter + name] — [searchable/shareable]
**服务层级**: [引流/传播/留存]
**心理驱动**: [primary driver category + specific trigger]

### 7 维评分
| 维度 | 评分 | 说明 |
|------|------|------|
| 1. 好奇心缺口 | ✓/✗ | [brief note] |
| 2. 自我相关性 | ✓/✗ | [brief note] |
| 3. 情绪激活 | ✓/✗ | [brief note] |
| 4. 身份安全性 | ✓/✗ | [brief note] |
| 5. 反直觉性 | ✓/✗ | [brief note] |
| 6. 群体发现感 | ✓/✗ | [brief note] |
| 7. 框架正确性 | ✓/✗ | [brief note] |

**总分**: X/7
**判定**: Go / Optimize / Kill

### 备选标题
1. [title] — [template] — [hook]
2. ...
3. ...

### 优化建议（if Optimize）
- [specific fix for each failing dimension]

### 产品衔接点
- [how this topic naturally connects to 心情可可 mini-program]
```

## Data Sources

Current reference data is derived from:
- **Psych2Go**: 1200 YouTube videos (full channel archive, views 8.2K–4M, avg 190K)
- **The School of Life (TSOL)**: 156 YouTube videos (2-year window, 2024-02 to 2026-02, avg 301K)

Future updates planned:
- Dr. Nicole LePera / The Holistic Psychologist
- KnowYourself / 壹心理 (国内竞品)

When new competitor data is added, update the relevant reference files. The workflow (this file) should remain stable.

## Important Notes

- Example titles in reference files are **illustrative templates**. Actual publication must use fresh, original copy.
- This skill evaluates topics; it does not write full articles. Use `copywriting` or `social-content` skills for content creation after a topic passes evaluation.
- The 7-dimension checklist is calibrated for 微信公众号. Other platforms (YouTube, TikTok, 小红书) may weight dimensions differently.
- Psych2Go data is based on 1200 videos (full channel archive); TSOL on 156 videos (2-year window). Treat as directional guidance, not absolute rules.
- **Platform-specific insight**: On WeChat, emotional resonance > curiosity gap for sharing (social-chain distribution vs search/recommendation). Optimize for 转发 and 在看, not just 打开率.
