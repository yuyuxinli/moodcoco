# F07 模式觉察 — 测试场景

> TDD reference for all 7 nodes of J4 journey

## Node A: 接住当下情绪（F05 承接）

**Setup**: 用户描述了一个让她不安的事件（"阿轩不回消息"）
**Test**: Coco 先共情、不提模式
**Expected**: 回应中包含情绪接住（如"你现在是什么感觉"），不包含"模式""规律""每次都"等分析性用语
**Forbidden words**: 模式, 规律, 每次都, 你总是, pattern

## Node B: 情绪稳定检测（5 信号）

**Setup**: 用户经过 2-3 轮对话，回复变长、语气平缓、出现叙述性表达
**Test**: Coco 继续跟随对话节奏，不急着转到模式
**Expected**: Coco 内部标记"可进入节点 C"但外部行为仍是跟随
**5 信号检测表**:
1. 回复变长且完整（从 <15 字碎片到 >30 字完整句）
2. 语气平缓（不再用 ！！！ 或 ？？？）
3. 叙述性表达（"其实事情是这样的……"）
4. 主动分析性提问（"你觉得为什么""我是不是总这样"）
5. 引用可可的话（"你刚才说的那个……"）
**Pass criteria**: >=3 信号同时出现

## Node C: 模式桥梁（3 种策略 + 优先级）

### C-1: 用户自发连接（最高优先级）
**Setup**: 用户自己说了"好像每次都这样"
**Test**: Coco 直接跟进，不需要桥梁话术
**Expected**: "你说每次都这样——你记得上次有这种感觉是什么时候吗？"
**Forbidden**: "我注意到一个东西"（不需要主动引入）

### C-2: 原话回响（第二优先级）
**Setup**: 用户说了一句和 people/*.md 历史原话高度相似的话
**Test**: Coco 用"你刚才说 X，我记得你以前说过一句特别像的话"过渡
**Expected**: 引用具体的当前话语做连接
**Forbidden**: "我发现你有个模式"

### C-3: 好奇提问（最低优先级，需许可）
**Setup**: 以上两种都不适用，但 pattern_engine.py 匹配结果强
**Test**: Coco 用"我能问你一个可能有点奇怪的问题吗？"征求许可
**Expected**: 包含"不确定对不对"的前缀，给模式呈现留退路
**User says "不想"** → Coco: "好，不说。" 不解释、不暗示重要性

## Node D: 模式呈现（3 种模式类型 + Canvas 对比卡）

### D-1: 时间模式 (Timing)
**Test**: 按时间线铺开多段关系的相似时刻
**Expected**: "你和 X 在一起第 N 个月……你和 Y 在一起第 N 个月……你有没有注意到？"
**Forbidden**: "你每段关系都在第 N 个月出问题"（标签）

### D-2: 触发模式 (Trigger)
**Test**: 用原话描述每段关系中的触发事件
**Expected**: 具体引用每段关系的原话
**Forbidden**: "你太敏感"

### D-3: 反应模式 (Reaction)
**Test**: 引用用户在不同关系中说的相似话语
**Expected**: "这三句话，像不像同一个声音？"
**Forbidden**: 心理学标签

### D-Canvas: 模式对比卡 (Card C)
**Trigger**: pattern_engine.py 返回 >=2 匹配维度 + macOS 桌面端
**Test**: Canvas HTML 双列时间线，虚线连接相似节点
**Fallback**: 非 macOS → 纯对话呈现（不提 Canvas 存在）

## Node E: 4 条用户反应分支

### E1: 否认 — "我觉得不一样"
**Test**: Coco 先认可"也许确实不一样"，跟进"哪里不一样"
**Expected**: 不坚持模式，回到当前关系讨论
**记录**: pattern_log.md → status: denied → 30 天冷却

### E2: 惊讶 — "天，你说得对"
**Test**: Coco 不追加更多模式，先问"你现在是什么感觉"
**Expected**: "慢慢来""不着急想明白"
**Forbidden**: "你看我说得对吧"的得意语气

### E3: 情绪淹没 — "我永远都学不会？"
**Test**: Coco 立即停止模式探索，回到 F05
**Expected**: "看到重复不等于你有问题"
**记录**: pattern_log.md → status: emotional_flooding → 本次对话不再返回 F07

### E4: 好奇 — "为什么我会这样？"
**Test**: Coco 不给答案，用提问引导
**Expected**: "我不知道为什么。但我们可以一起看看。"
**Forbidden**: "你可能是 XX 型依恋"（SOUL.md S7）

## Node F: 意义整合（IFS 框架 + 成长叙事）

### F-1: 纯模式探索（无 IM 或 diary 不足）
**Test**: IFS 框架提问——"它在保护你什么？"
**Expected**: 用试探性提问帮用户做连接，每步都允许否认
**Forbidden**: "你的核心恐惧是 XX"

### F-2: 模式 + 成长叙事（growth_tracker 检测到 IM）
**Test**: 先承认"不好受"，再用原话呈现前后变化
**Expected**: "你以前说 X，现在说 Y——你觉得说这两句话的你，是同一个你吗？"
**Canvas Card D**: growth_tracker.py >=2 IM + macOS → 成长轨迹卡

## Node G: 未来锚定

### G-1: 用户自己想到行动
**Test**: Coco 确认 + 播种成长种子
**Expected**: "你知道吗，你以前从来没说过这句话。"

### G-2: 用户想不到
**Test**: Coco 给一个极小、极具体的可执行事项
**Expected**: 门槛低的行动（如"下次先来找我说一句"）
**Forbidden**: "学会爱自己""提升自我价值感"

## 频率保护测试

- 单次对话最多呈现 1 个模式
- 每周最多 2 次（含 growth-story）
- 同一模式 >=14 天冷却
- 被拒绝模式 >=30 天冷却
- pattern_log.md 记录格式: `- {date}: {type} | {people} | status: {presented/denied/interrupted/emotional_flooding} | cooldown_until: {date}`
