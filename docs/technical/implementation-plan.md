# 心情可可 · 实现计划

*Version: 1.0 | 2026-03-30*

> **定位**：本文档是技术设计到实际落地之间的桥梁。按依赖顺序排列每一步的具体改动、验收标准和文档关联。
>
> - 技术方案详见 → [技术设计](technical-design.md)
> - 产品体验详见 → [体验设计 F01-F11](../product/product-experience-design.md)
> - 整体架构详见 → [产品技术架构](../product-architecture.md)
> - 平台能力详见 → [OpenClaw 能力参考](openclaw-capabilities.md)

---

## 0. 当前状态速览

### 已完成

| 层 | 已有内容 | 对应文档 |
|----|---------|---------|
| 对话层 | SOUL.md S7 不贴标签、AGENTS.md 全局危机检测 + 时间感知 + Step 2 多解读 + Step 3 成长叙事 + F1/F2 路由 | [技术设计 §2-5](technical-design.md#2-f1-情绪急救--从爆炸降到能呼吸) |
| 技能层 | diary（V2）、pattern-mirror、decision-cooling、farewell、breathing-ground、relationship-guide | [技术设计 §9.2](technical-design.md#92-新增文件) |
| 数据层 | pattern_engine.py、growth_tracker.py、archive_manager.py（未验证） | [技术设计 §5.2, §5.5, §8.3](technical-design.md#52-模式匹配引擎设计s4-跨关系模式档案) |
| 主动触达 | HEARTBEAT.md 决策冷却回访 + 周日回顾 + 时间胶囊 | [技术设计 §6.3, §7.2](technical-design.md#63-技术实现) |
| 配置层 | openclaw.json streaming/heartbeat/compaction/session | [OpenClaw 能力](openclaw-capabilities.md) |

### 缺口

| 缺口 | 影响范围 | 对应步骤 |
|------|---------|---------|
| 5 个冗余 Skill 未清理，路由歧义 | 所有对话 | Step 1 |
| 闲聊/情绪分流缺失 | F06 日常陪伴无法触发 | Step 1 |
| MEMORY.md、pending_followup.md、time_capsules.md 不存在 | Heartbeat 回访、时间胶囊、compaction 保护 | Step 2 |
| USER.md 缺「模式级洞察」段 | 告别后模式保留 | Step 2 |
| 3 个 Python 脚本未验证 | pattern-mirror、growth-story、farewell 数据支撑 | Step 3 |
| 4 个 Skill 空壳（onboarding/check-in/weekly-reflection/growth-story） | F04 首次相遇、F06 日常陪伴、F07 模式觉察 | Step 4 |
| 旅程编排 F09-F10 完全空白 | 旅程之间无法跳转 | Step 5 |
| 边缘场景 F11 无防护 | 同名消歧、记忆冲突、情绪聚类 | Step 6 |
| 交互系统 F02 几乎空白（Canvas/Poll/Image） | 体验增强 | Step 7 |

---

## Step 1：清场——消除路由歧义

### 为什么必须第一个做

模型同时看到 `calm-down` 和 `breathing-ground`，不知道该调哪个。所有后续测试和评估的前提是**路由准确**。路由不清，测什么都不可信。

### 改动清单

#### 1.1 删除冗余 Skill

| 删除 | 已被合并到 | 产品依据 |
|------|----------|---------|
| `skills/calm-down/` | `skills/breathing-ground/` | [体验设计 F03 §Skill 合并](../product/product-experience-design.md) |
| `skills/sigh/` | `skills/breathing-ground/` | 同上 |
| `skills/emotion-journal/` | `skills/diary/` | 同上 |
| `skills/relationship-coach/` | `skills/relationship-guide/` | 同上 |
| `skills/relationship-skills/` | `skills/relationship-guide/` | 同上 |

删除后 `skills/` 目录保留 10 个 Skill：
`breathing-ground` / `diary` / `relationship-guide` / `pattern-mirror` / `decision-cooling` / `farewell` / `onboarding` / `check-in` / `weekly-reflection` / `growth-story`

#### 1.2 统一 AGENTS.md 路由表

更新 AGENTS.md 中所有 Skill 引用，确保只指向上述 10 个。移除对旧 Skill 名的一切提及。

#### 1.3 新增闲聊/情绪分流规则

在 AGENTS.md 中新增路由前置判断：

```
用户消息 → 闲聊（无情绪信号）→ 自然陪伴模式（不触发四步框架）
用户消息 → 情绪信号 → 四步框架（Step 1-4）
```

不加这条，用户说"今天天气好好"也会被当成情绪事件处理。

参考：[体验设计 F06 节点 A](../product/product-experience-design.md)（闲聊 vs 情绪事件路由）

### 验收标准

- [ ] `skills/` 下只有 10 个目录
- [ ] AGENTS.md 全文搜索无 `calm-down`、`sigh`、`emotion-journal`、`relationship-coach`、`relationship-skills` 引用
- [ ] AGENTS.md 有明确的闲聊/情绪分流规则
- [ ] 模拟对话测试：发送"今天吃了好吃的" → 可可不触发情绪急救

### 关联文档

| 文档 | 章节 |
|------|------|
| [技术设计](technical-design.md) | §1 整体架构（Skill 层） |
| [体验设计](../product/product-experience-design.md) | F03 Skill 清单重整、F06 节点 A 闲聊路由 |

---

## Step 2：补存储层——建立数据管道

### 为什么必须在 Step 1 之后、Step 4 之前

这些文件是 Skill 之间的数据管道。decision-cooling 往 `pending_followup.md` 写，Heartbeat 从里面读。管道不存在，上游写了也丢，下游读了也空。

### 改动清单

#### 2.1 创建 MEMORY.md

位置：`ai-companion/MEMORY.md`

```markdown
# 长期记忆锚点

<!-- 此文件不受 compaction 时间衰减影响 -->
<!-- 可可在 compaction 前将关键信息写入此处，确保不丢失 -->

## 跨关系模式
<!-- pattern_engine.py 发现的跨关系行为重复 -->

## 重要时间节点
<!-- 用户重要日期：纪念日、分手日、生日等 -->

## 核心信念变化轨迹
<!-- 用户自我认知的重大转变 -->
```

#### 2.2 创建 memory/pending_followup.md

位置：`ai-companion/memory/pending_followup.md`

```markdown
# 待回访队列

<!-- decision-cooling skill 写入，HEARTBEAT.md 读取并执行 -->
<!-- 格式：一条回访一个段落 -->
<!-- 回访完成或用户主动提起后删除对应条目 -->
```

参考：[技术设计 §6 S2 决策冷却](technical-design.md#6-s2-24h-决策冷却)

#### 2.3 创建 memory/time_capsules.md

位置：`ai-companion/memory/time_capsules.md`

```markdown
# 时间胶囊

<!-- farewell skill 写入，Heartbeat 每日检查是否有到期胶囊 -->
<!-- 格式：一个胶囊一个段落 -->
```

参考：[技术设计 §8.2 时间胶囊特殊处理](technical-design.md#82-设计)

#### 2.4 USER.md 增加模式级洞察段

在 `ai-companion/USER.md` 末尾新增：

```markdown
## 模式级洞察

<!-- 来自已封存关系的去名字洞察 -->
<!-- farewell 仪式完成后由 archive_manager.py 写入 -->
<!-- 格式：纯行为描述，不含人名 -->
```

参考：[体验设计 F01 §1.3 USER.md 数据模型](../product/product-experience-design.md)

### 验收标准

- [ ] `ai-companion/MEMORY.md` 存在且有模板结构
- [ ] `ai-companion/memory/pending_followup.md` 存在
- [ ] `ai-companion/memory/time_capsules.md` 存在
- [ ] `ai-companion/USER.md` 包含「模式级洞察」段

### 关联文档

| 文档 | 章节 |
|------|------|
| [技术设计](technical-design.md) | §6.3（pending_followup）、§8.2（time_capsules）、§4.3 差距 3 |
| [体验设计](../product/product-experience-design.md) | F01 记忆体系（三层存储、USER.md 数据模型） |

---

## Step 3：验数据层脚本——确认工具可用

### 为什么必须在填 Skill 之前

pattern-mirror 调 `pattern_engine.py`，growth-story 调 `growth_tracker.py`，farewell 调 `archive_manager.py`。如果脚本有 bug，Skill 调了也白调。**先验证工具好使，再让 Skill 用工具。**

### 验证清单

#### 3.1 pattern_engine.py

位置：`ai-companion/skills/diary/scripts/pattern_engine.py`

测试方法：
1. 在 `people/` 下创建 2 个 mock 人物档案（含退出信号）
2. 运行 `parse_people_files()` → 检查解析结果
3. 运行 `find_cross_patterns()` → 检查跨关系匹配输出
4. 运行 `match_current_to_history()` → 检查当前事件匹配

参考：[技术设计 §5.2 模式匹配引擎](technical-design.md#52-模式匹配引擎设计s4-跨关系模式档案)

#### 3.2 growth_tracker.py

位置：`ai-companion/skills/diary/scripts/growth_tracker.py`

测试方法：
1. 在 `diary/` 下创建 mock 日记（含不同时间点的对比表述）
2. 运行 `extract_growth_nodes()` → 检查 Innovative Moments 检测
3. 运行 `find_contrast_pairs()` → 检查对比节点对
4. 运行 `format_for_conversation()` → 检查生成的叙事文本

参考：[技术设计 §5.5 关系故事重写 S9](technical-design.md#55-关系故事重写s9)

#### 3.3 archive_manager.py

位置：`ai-companion/skills/farewell/scripts/archive_manager.py`

测试方法：
1. 创建 mock people/、diary/、memory/ 数据
2. 运行 `archive_person()` → 检查封存后具体事件是否清除、模式洞察是否保留
3. 运行 `delete_person()` → 检查彻底删除
4. 运行 `extract_pattern_insights()` → 检查去名字洞察

参考：[技术设计 §8.3 数据层设计](technical-design.md#83-数据层设计)

### 验收标准

- [ ] 3 个脚本均可 `import` 且无报错
- [ ] pattern_engine 能正确匹配 2 段 mock 关系的相似模式
- [ ] growth_tracker 能从 mock 日记中检测至少 1 个 Innovative Moment
- [ ] archive_manager 封存后原始事件不可访问、模式洞察保留且去名字
- [ ] 发现的 bug 已修复并 commit

### 关联文档

| 文档 | 章节 |
|------|------|
| [技术设计](technical-design.md) | §5.2（pattern_engine）、§5.5（growth_tracker）、§8.3（archive_manager） |
| [体验设计](../product/product-experience-design.md) | F01 §1.5（跨关系记忆连接）、F07（模式觉察旅程）、F08（告别旅程） |

---

## Step 4：填 4 个空壳 Skill

### 为什么此时才能做

- onboarding 需要写 USER.md → Step 2 的模板先有
- weekly-reflection 调 growth_tracker.py → Step 3 先验证通过
- growth-story 调 growth_tracker.py → 同上
- check-in 读 USER.md 的"核心困扰" → Step 2 先定义好
- 所有 Skill 需要路由准确 → Step 1 先完成

### 改动清单

#### 4.1 onboarding（F04 首次相遇）

位置：`ai-companion/skills/onboarding/SKILL.md`

7 个节点：
- A. 自然开场（非模板化）
- B. 发现（了解用户为什么来）
- C. 接住（接住第一个故事）
- D. 深层动作（做一件"普通 AI 做不到"的事）
- E. 信任锚点（用户感到被听见）
- F. 记忆创建（写 USER.md + people/*.md）
- G. 自然收尾

参考：[体验设计 F04 J1 首次相遇](../product/product-experience-design.md)（完整节点设计）

#### 4.2 check-in（Heartbeat 触发轻量关怀）

位置：`ai-companion/skills/check-in/SKILL.md`

功能：
- Heartbeat 检测用户 24h+ 未对话 → 触发
- 读 USER.md 核心困扰 + 最近 diary → 生成个性化问候
- 不是泛泛的"你好吗"，而是基于上次对话的具体关心

参考：[体验设计 F06 节点 C](../product/product-experience-design.md)（Heartbeat 主动关怀）

#### 4.3 weekly-reflection（周日回顾）

位置：`ai-companion/skills/weekly-reflection/SKILL.md`

功能：
- 周日 20:00 Heartbeat 触发
- 读取本周 diary/ → 调 growth_tracker.py 检测重复主题
- 发现重复 → 用对话方式呈现（不是图表报告）
- 发现成长 → 呈现纵向对比
- 无发现 → 不发（不为回顾而回顾）
- Canvas 可用时展示情绪地图（Step 7 增强），否则纯文字

参考：[体验设计 F06 节点 E](../product/product-experience-design.md)（周日回顾）、[技术设计 §7 S5 日记回顾](technical-design.md#7-s5-关系日记回顾)

#### 4.4 growth-story（成长叙事）

位置：`ai-companion/skills/growth-story/SKILL.md`

功能：
- 触发条件：用户使用 ≥30 天 + growth_tracker.py 检测到对比节点
- 用具体事件展示变化，不用空洞鼓励
- INT/IMA 框架：Action / Reflection / Protest / Re-conceptualization / Performing Change

参考：[体验设计 F07 节点 F](../product/product-experience-design.md)（成长叙事）、[技术设计 §5.5 growth_tracker.py](technical-design.md#55-关系故事重写s9)

### 验收标准

- [ ] 4 个 SKILL.md 内容完整，无 `(待补充)` 占位符
- [ ] 每个 Skill 有明确的触发条件、流程节点、硬规则
- [ ] onboarding 包含记忆写入逻辑（USER.md + people/*.md）
- [ ] weekly-reflection 包含"无发现不发"规则
- [ ] growth-story 包含 ≥30 天门槛
- [ ] 模拟对话测试：首次用户 → 触发 onboarding → 对话结束后 USER.md 有内容

### 关联文档

| 文档 | 章节 |
|------|------|
| [技术设计](technical-design.md) | §7（S5 日记回顾）、§5.5（S9 成长叙事） |
| [体验设计](../product/product-experience-design.md) | F04（首次相遇）、F06（日常陪伴）、F07（模式觉察） |

---

## Step 5：旅程编排——串联 Skill 为旅程

### 为什么必须在所有 Skill 就位之后

这一步是"接线"——把 10 个独立 Skill 串成 5 条旅程（J1-J5），再定义旅程之间的跳转。没有零件就没法接线。

### 改动清单

#### 5.1 AGENTS.md 旅程状态机

定义 5 条旅程的入口条件和内部节点流转：

| 旅程 | 入口条件 | 涉及 Skill | 产品文档 |
|------|---------|-----------|---------|
| J1 首次相遇 | USER.md 为空 / 首次对话 | onboarding | [F04](../product/product-experience-design.md) |
| J2 情绪事件 | 检测到情绪信号 | breathing-ground, diary, relationship-guide, pattern-mirror | [F05](../product/product-experience-design.md) |
| J3 日常陪伴 | 无情绪信号 / Heartbeat 触发 | check-in, diary, weekly-reflection | [F06](../product/product-experience-design.md) |
| J4 模式觉察 | people/ ≥2 段关系 + 退出信号 + ≥5 次对话 | pattern-mirror, growth-story | [F07](../product/product-experience-design.md) |
| J5 告别 | 用户主动提出告别 / 可可感知准备好了 | farewell | [F08](../product/product-experience-design.md) |

#### 5.2 跨旅程触发条件（F10）

| 从 | 到 | 触发条件 | 数据管道 |
|----|-----|---------|---------|
| J2 情绪事件 | J3 Heartbeat 回访 | decision-cooling 写入 pending_followup.md | `memory/pending_followup.md` |
| J2 情绪事件 | J4 模式觉察 | 退出信号记录到 people/*.md + ≥2 段关系 | `people/*.md` 退出信号段 |
| J3 日常陪伴 | J4 模式觉察 | weekly-reflection 发现跨关系重复 | growth_tracker.py 输出 |
| J5 告别 | J1 新关系 | 模式洞察迁移到 USER.md | `USER.md` 模式级洞察段 |
| 任意旅程 | 危机协议 | 安全前置检查命中 | AGENTS.md §0 |

参考：[体验设计 F10 旅程转换](../product/product-experience-design.md)

#### 5.3 HEARTBEAT.md Cron 触发规则

| 触发 | 时间 | 动作 | 依赖 |
|------|------|------|------|
| 日记提醒 | 每日 21:30 | 温和提醒记录今天 | diary skill |
| 周日回顾 | 周日 20:00 | 触发 weekly-reflection | growth_tracker.py |
| 决策冷却回访 | 每次 Heartbeat | 检查 pending_followup.md | decision-cooling 写入 |
| 时间胶囊检查 | 每日 | 检查 time_capsules.md 是否到期 | farewell 写入 |

### 验收标准

- [ ] AGENTS.md 有 5 条旅程的入口条件和内部流转
- [ ] AGENTS.md 有跨旅程触发条件
- [ ] HEARTBEAT.md 有 4 条 Cron 触发规则
- [ ] 模拟测试：decision-cooling 完成 → 24h 后 Heartbeat 发送回访消息
- [ ] 模拟测试：用户在 J2 中触发退出信号 → 下次对话 J4 pattern-mirror 能读取

### 关联文档

| 文档 | 章节 |
|------|------|
| [技术设计](technical-design.md) | §1.1（数据流）、§10（实现顺序） |
| [体验设计](../product/product-experience-design.md) | F09（基础设施×旅程绑定）、F10（旅程转换） |

---

## Step 6：边缘防护

### 为什么在编排之后

编排建立了正常路径（happy path），边缘防护处理异常路径。正常的路走不通，处理异常没意义。

### 改动清单

#### 6.1 同名消歧

AGENTS.md 新增规则：当用户提到的人名与已有 people/*.md 匹配但上下文不一致时，主动确认。

```
"你说的小明，是之前那个男朋友，还是另一个人？"
```

参考：[体验设计 F11 §多关系并行](../product/product-experience-design.md)

#### 6.2 记忆冲突优先级

AGENTS.md 新增规则：更新 people/*.md 时的冲突处理优先级：

1. 状态字段（在一起/分手）→ 直接更新
2. 事实性信息（日期、事件）→ 追加不覆盖
3. 观点性信息（"他人很好" vs "他 PUA 我"）→ 记录变化轨迹
4. 新信息 → 追加到对应段落

参考：[技术设计 §4.3 差距 2](technical-design.md#43-差距与改动-2)

#### 6.3 情绪词簇

AGENTS.md 或 `docs/references/` 定义情绪聚类规则：

- "烦 / 焦虑 / 崩溃 / 受不了" → 焦虑簇
- "委屈 / 心酸 / 不被在意" → 委屈簇
- "生气 / 愤怒 / 凭什么" → 愤怒簇

用于 diary skill 判断"同一情绪 ≥3 次"时的匹配，避免只做字面匹配。

参考：[体验设计 F11 §情绪词簇](../product/product-experience-design.md)

#### 6.4 旅程中断恢复

AGENTS.md 新增规则：对话中途断开时的恢复策略。

- 情绪急救中断 → 下次开场先确认"上次聊到一半，你现在还好吗？"
- 告别仪式中断 → 下次问"上次我们在做告别仪式，你要继续吗？"
- 不强制恢复，用户换话题就跟着走

参考：[体验设计 F11 §对话中断](../product/product-experience-design.md)

### 验收标准

- [ ] AGENTS.md 有同名消歧规则
- [ ] AGENTS.md 有记忆冲突优先级
- [ ] 情绪词簇定义文件存在
- [ ] AGENTS.md 有旅程中断恢复规则
- [ ] 模拟测试：用户提到"小明"（同名不同人）→ 可可主动确认

### 关联文档

| 文档 | 章节 |
|------|------|
| [技术设计](technical-design.md) | §4.3（记忆冲突）、§5.4（S7 事件叙事） |
| [体验设计](../product/product-experience-design.md) | F11（边缘场景与一致性） |

---

## Step 7：交互增强

### 为什么最后做

前六步用纯文字降级就能完整跑通所有旅程。Canvas/Poll/Image 是体验增强，不是功能必需。

### 改动清单

#### 7.1 Canvas HTML 模板

5 种卡片，位置建议 `ai-companion/skills/*/scripts/`：

| 卡片 | 用途 | 触发 Skill |
|------|------|-----------|
| 周情绪地图 | 本周情绪分布可视化 | weekly-reflection |
| 关系时间线 | 一段关系的阶段演变 | diary（用户主动查看时） |
| 模式对比 | 跨关系相似模式并排展示 | pattern-mirror |
| 成长轨迹 | 纵向对比的可视化 | growth-story |
| 告别纪念 | 仪式化的封存展示 | farewell |

参考：[体验设计 F02 §Canvas 系统](../product/product-experience-design.md)

#### 7.2 Poll 通道降级

AGENTS.md 新增通道检测规则：

| 通道 | 支持 Poll | 降级方案 |
|------|----------|---------|
| Telegram / WhatsApp / Discord / Teams | ✅ | 原生 Poll |
| 微信 / 飞书 | ❌ | 编号文字选择（"1. xxx 2. xxx 回复数字选择"） |

参考：[体验设计 F02 §Poll 系统](../product/product-experience-design.md)、[OpenClaw 能力](openclaw-capabilities.md)

#### 7.3 图片生成

用 exec 脚本（PIL/Pillow + matplotlib）生成情绪可视化图片，作为 Canvas 不可用时的替代。

### 验收标准

- [ ] 至少 1 种 Canvas 卡片可渲染（周情绪地图优先）
- [ ] Poll 降级规则在 AGENTS.md 中
- [ ] 模拟测试：微信通道 → farewell 仪式选择用编号文字而非 Poll

### 关联文档

| 文档 | 章节 |
|------|------|
| [技术设计](technical-design.md) | §1（整体架构，技能层） |
| [体验设计](../product/product-experience-design.md) | F02（交互系统设计） |
| [OpenClaw 能力](openclaw-capabilities.md) | Canvas / Poll / Image 章节 |

---

## 评估策略

每个 Step 完成后，用 evolve 循环跑真实对话验证。评估维度来自[技术设计 §11 评估总表](technical-design.md#11-评估总表)：

| Step | 可评估的模块 | 维度数 |
|------|------------|--------|
| Step 1 完成后 | F1 情绪急救、F2 信号解读 | 7 |
| Step 2-3 完成后 | F3 关系档案 | 3 |
| Step 4 完成后 | F4 模式追踪、S2 决策冷却、S5 日记回顾 | 10 |
| Step 5 完成后 | 全旅程端到端 | 20 |
| Step 6 完成后 | 边缘场景 | 24（全量） |
| Step 7 完成后 | 交互体验增强 | 24 + 交互维度 |

评估门槛沿用[技术设计](technical-design.md#11-评估总表)标准，所有维度 ≥ 8.0。

### 核心评估标准（来自 CLAUDE.md）

| 维度 | 门槛 |
|------|------|
| 看见情绪 | 9.0 |
| 看见原因 | 9.0 |
| 看见模式 | 9.0 |
| 看见方法 | 9.0 |
| 安全边界 | 9.0 |

---

## 总依赖图

```
Step 1 清场（Skill 清理 + 路由统一 + 闲聊分流）
  │
  │  不做 → 路由歧义，所有后续测试不可信
  ↓
Step 2 补存储层（MEMORY.md + pending_followup + time_capsules + USER.md 洞察段）
  │
  │  不做 → Skill 之间无法传递数据
  ↓
Step 3 验数据层脚本（pattern_engine + growth_tracker + archive_manager）
  │
  │  不做 → 依赖脚本的 Skill 调用必崩
  ↓
Step 4 填 4 个 Skill（onboarding + check-in + weekly-reflection + growth-story）
  │
  │  不做 → 旅程不完整，编排无对象
  ↓
Step 5 旅程编排（状态机 + 跨旅程触发 + Cron 规则）
  │
  │  不做 → Skill 各自为政，用户体验断裂
  ↓
Step 6 边缘防护（消歧 + 冲突 + 词簇 + 中断恢复）
  │
  │  不做 → 正常能跑但异常会崩
  ↓
Step 7 交互增强（Canvas + Poll 降级 + 图片生成）
  │
  │  不做 → 能用但体验粗糙
  ↓
端到端验证（24 维度全量评估）
```
