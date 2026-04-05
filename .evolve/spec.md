# 心情可可「关系智能」需求文档

*2026-04-05 | 蒋宏伟*

## 一、产品定位升级

心情可可从"AI 心理陪伴系统"升级为**关系智能平台**。

**核心洞察：困住人的不是事情本身，而是人与事情的关系。**

心理学依据（三大循证框架共同指向同一结论）：
- **叙事疗法**（Michael White, 1990）：核心技术"外化对话"——不问"你为什么焦虑"，而问"你和焦虑的关系是什么"
- **ACT**（Steven Hayes, 2019）：*"changing your relationship to your thoughts and feelings rather than changing their content"*
- **Lazarus & Folkman 压力理论**（1984）：*"Psychological stress is a particular relationship between the person and the environment"*

"关系"不仅是人际关系，还包括三个维度：
- 我和**人**的关系（亲密关系、家庭、职场）
- 我和**事件**的关系（考研、缺钱、裁员——我怎么看待这件事）
- 我和**自己**的关系（自我价值、意义感）

---

## 二、五层产品架构

### 第 1 层：用户主动触发（推荐 + 场景入口）

本质是**推荐算法**。根据用户历史对话、高频话题、当前情绪，推荐她可能想聊的场景。

**三种入口来源：**

1. **系统预设场景**（冷启动用，所有用户都有，面向 18-24 岁女性高频场景）：

| 场景 | 用户心里想的 |
|------|------------|
| 恋爱 | "他不回消息了""我们吵架了""该不该分手" |
| 家人 | "我妈又催我了""跟父母观念不合" |
| 室友 | "室友关系好尴尬""感觉被孤立了" |
| 朋友 | "说错话了大家是不是觉得我蠢" |
| 考研 | "能考上吗""每天都在怀疑自己" |
| 考公 | "考不上怎么办""家里一直催" |
| 实习 | "什么都不会""被老板骂了" |
| 求职 | "海投简历没回应" |
| 毕业 | "不知道自己适合什么" |
| 学业 | "论文没思路 DDL 要到了" |
| 失眠 | "焦虑到失眠脑子停不下来" |
| 认识自己 | "我为什么总是讨好别人" |
| 容貌焦虑 | "觉得自己又胖又丑" |
| 随便聊聊 | "今天想说说话" |
| 🆘 SOS | "我现在很崩溃"（常驻按钮） |

2. **用户高频标签**（从第 5 层记忆中提取，用得越多越靠前）：妈妈、考研、男朋友、导师...

3. **智能推荐**（基于时间、情绪、未完结事件）："上次你提到周五跟导师谈，聊聊怎么样了？"

**演化逻辑：** 新用户看到预设场景（冷启动），聊得越多，预设场景逐渐被她自己的高频标签替代。最终她打开可可，看到的全是她自己的人和事。

**说明：** 情绪签到也在这一层，每次打开时快速记录当前情绪。大部分时间用户直接聊天，不需要选场景。

### 第 2 层：日记与关系智能展示

独立页面。核心是**日记流**——可可从每天的对话中自动生成日记，日记里自动关联人物和事件。用户翻日记的过程中，自然看到自己的关系全貌。

**日记流（按时间排序，最新在上）：**

```
4月5日 — "今天跟妈妈因为考研的事吵了一架，男朋友安慰了我"
  └── 关联：妈妈 · 男朋友 · 考研

4月3日 — "论文没思路，焦虑到失眠"
  └── 关联：考研 · 导师

4月1日 — "跟室友聊了很久，感觉好多了"
  └── 关联：室友
```

**日记生成机制：**
- 默认：凌晨自动把当天对话转成日记（每日一篇）
- 主动：用户随时可以触发生成，一天可以写多篇

**点击日记 → 详情页：**
- 完整日记内容 + 情绪标记
- 下方显示关联的人物和事件标签

**点击关联标签 → 关系详情页：**
- 点击「妈妈」→ 所有跟妈妈相关的日记 + 关系状态 + 可可的洞察
- 点击「考研」→ 所有跟考研相关的日记 + 事件进展 + 可可的洞察
- 点击「我的成长」→ 自我认知变化轨迹

**关联标签由第 5 层自动提取**——用户不需要手动打标签，可可从日记内容中自动识别人物和事件。用户可以编辑、删除、补充。

**关系智能不是另一个独立功能，它从日记里自然长出来。** 用户只是在翻日记，点了"妈妈"就看到了所有跟妈妈有关的事——关系的全貌和变化就在那里。

### 第 3 层：对话中程序主动触发

可可在对话中主动做的事，用户能感知到但不是用户发起的。

| 触发行为 | 触发条件 | 用户感知 | 示例 |
|---------|---------|---------|------|
| 情绪急救介入 | 情绪强度过高（大哭、愤怒、恐慌） | "可可知道我需要先冷静" | "等一下，我们先做个呼吸好吗？" |
| 模式洞察推送 | 同类话题 3+ 次，memory 有足够数据 | "可可看到了我没看到的" | "我注意到一个事情——你和男朋友的冲突每次都是在你很累的时候..." |
| 事件跟进 | 上次提到未解决的事，距今 >24h | "可可记得我上次说的" | "上次你说周五要跟导师谈，怎么样了？" |
| 定时 check-in | 每日固定时间或距上次对话 >48h | "可可在关心我" | "今天过得怎么样？" |
| 关系总结 | 一段密集对话结束时 | "可可帮我总结了" | "今天聊了好多，我帮你理一下..." |
| 成长提醒 | 用户状态有积极变化 | "我在变好" | "一个月前你还在纠结要不要分手，现在你已经能平静地谈了" |
| 危机干预 | P0 关键词（自杀、自残、不想活） | 被安全接住 | 立即启动 QPR，提供专业求助渠道 |

### 第 4 层：内部 Skills + 场景材料（用户无感，后台路由）

**这是交大团队的核心交付物。** 分两部分：通用 skill（引擎）和场景专属 reference（燃料）。

#### 4a. 通用 Skills（8 个引擎）

用户看不到这些名字，只感受到效果。每个 skill 声明触发条件，LLM 自主选择调用。

| Skill | 做什么 | 触发条件 | 心理学基础 | 优先级 |
|-------|--------|---------|-----------|--------|
| **listen** | 情绪承接与倾听。不分析不建议，就是在。 | 用户带着情绪来、需要有人听 | 以人为中心疗法、无条件积极关注 | P0 |
| **untangle** | 帮用户把混乱的事情理清楚。拆开人、事、情绪。 | 用户思绪混乱、多件事缠在一起 | 叙事疗法外化技术、Lazarus 压力评估 | P0 |
| **see-pattern** | 跨对话识别关系模式和行为规律 | 同类对话 3+ 次、memory 有足够数据 | 叙事疗法重写、CBT 模式识别 | P0 |
| **face-decision** | 帮用户面对选择、理清利弊，但不替她决定 | 用户面临选择、犹豫不决 | 动机式访谈、ACT 价值观澄清 | P1 |
| **know-myself** | 帮用户探索自我认知 | 用户没有具体事件，在想自己 | IFS 部分工作、ACT 自我觉察 | P1 |
| **crisis** | 危机干预。评估风险等级，提供专业转介 | P0 关键词或 P1 模糊信号累积 | QPR 技术（提问-劝说-转介） | P0（安全底线） |
| **calm-body** | 身体层面即时稳定：呼吸引导、感官着陆、助眠 | 焦虑发作、失眠、恐慌 | 循环叹息（Stanford RCT）、4-7-8、5-4-3-2-1 | P0 |
| **base-communication** | 所有 skill 的地基：承接/澄清/轻推动三组沟通技术 | 始终加载，不单独触发 | 临床心理基本技术 | P0（地基） |

#### 4b. 场景专属材料（15 个场景）

**Skill 是引擎，Scene 是燃料。** 同一个 `listen` skill，在恋爱场景和考研场景里调用的参考材料完全不同。

| 场景 | 调用的 skill 组合 | 场景专属 reference（交大团队填充） |
|------|-----------------|-------------------------------|
| 恋爱 | listen + relationship-coach + untangle | 依恋理论、亲密关系冲突模式、分手哀伤阶段 |
| 家人 | listen + untangle + see-pattern | 原生家庭动力学、代际沟通、分离个体化 |
| 室友 | listen + untangle | 宿舍人际边界、被动攻击识别 |
| 朋友 | listen + untangle | 社交焦虑、讨好型人格、友谊边界 |
| 考研 | listen + face-decision + calm-body | 备考倦怠、同辈比较、自我怀疑周期 |
| 考公 | listen + face-decision + calm-body | 体制内外选择、家庭期望压力 |
| 实习 | listen + untangle + face-decision | 职场新人适应、权力距离、犯错恐惧 |
| 求职 | listen + face-decision | 拒绝敏感、自我价值与外部评价 |
| 毕业 | listen + face-decision + know-myself | 身份转换焦虑、丧失感、未来不确定性 |
| 学业 | listen + face-decision + calm-body | 拖延心理学、完美主义、截止日期焦虑 |
| 失眠 | calm-body | 睡眠卫生、认知激活、放松训练 |
| 认识自己 | know-myself + see-pattern | 自我概念、价值观探索、内在批评者 |
| 容貌焦虑 | listen + know-myself | 身体意象、社会比较、自我接纳 |
| 随便聊聊 | listen | （无专属 reference，纯倾听） |
| SOS | crisis | QPR 评估标准、分级规则、转介资源 |

**交付结构：**

```
skills/                        ← 8 个通用 skill
├── listen/
│   ├── SKILL.md               ← 通用的倾听逻辑 + 触发条件 + 正确/错误示范
│   └── references/            ← 通用的倾听技术来源
├── untangle/
├── see-pattern/
├── ...

scenes/                        ← 15 个场景专属材料
├── 恋爱/
│   ├── SCENE.md               ← 调用哪些 skill + 场景特有规则
│   └── references/            ← 依恋理论、亲密关系冲突、分手哀伤...
├── 考研/
│   ├── SCENE.md
│   └── references/            ← 备考倦怠、同辈压力、自我怀疑...
├── 家人/
│   ├── SCENE.md
│   └── references/            ← 原生家庭、代际沟通、分离个体化...
├── ...其他 12 个场景
```

**现有 skill 处理：**
- **保留并升级**：calm-down（→ calm-body，补适用边界）、diary（补 SORC 理论）、relationship-coach（已达专业级）、sigh（已有 RCT 支撑）
- **废弃**：emotion-journal（被 diary 替代）、relationship-skills（被 relationship-coach 替代）

### 第 5 层：记忆自动整理

每次对话结束后，后台自动从对话中提取信息，更新三个维度的记忆。基于 [memU](https://github.com/NevaMind-AI/memU) 文件系统式记忆架构。

| 维度 | 提取什么 | 供谁使用 |
|------|---------|---------|
| **人物** | 关键人物、关系状态变化、互动事件 | 第 2 层展示 + 第 4 层 skill 读取 |
| **事件** | 事件进展、情绪变化、关联人物 | 第 2 层展示 + 第 4 层 skill 读取 |
| **自我** | 自我认知、反复出现的自我评价、价值观 | 第 2 层展示 + 第 4 层 skill 读取 |
| **索引** | 所有记忆的摘要索引 | LLM 检索时先读索引再读具体文件 |

**记忆原则：**
- 用户可见可编辑（第 2 层展示的数据来自这里，用户修改后同步）
- 最小必要（只记有意义的变化，不记所有对话细节）
- 后台异步（不阻塞对话，对话结束后执行）
- 现有线性记忆保留不动，三维提取是在线性记忆之上的结构化视图

---

## 三、五层之间的驱动关系

```
第 1 层（用户触发）───→ 第 4 层（skill 执行）
                              ↓
第 5 层（记忆整理）←─── 对话结束后提取
       ↓
第 2 层（界面展示）←─── 读取记忆，渲染给用户
       ↓
第 3 层（程序触发）←─── 基于记忆积累，判断该主动做什么
       ↓
      又回到第 4 层（执行 skill）
```

---

## 四、与交大团队架构（v1.0）的关系

交大团队的五层是**"心理学怎么做"**（方法论），我们的五层是**"产品做什么"**（需求）。两者不是替代关系，是两个视角看同一件事。

| 交大架构（方法论） | 我们的架构（需求） | 关系 |
|-----------------|-----------------|------|
| 第 0 层 治理与边界 | 贯穿所有层 | 安全红线不是单独一层，是所有层的底线 |
| 第 1 层 关系操作系统 | 第 5 层 + 第 3 层 + 第 2 层 | 线程管理→记忆整理；轻跟进→程序触发；陪伴协议→界面设置 |
| 第 2 层 基础互动协议 | 第 4 层 base-communication | 承接/澄清/轻推动是所有 skill 的地基 |
| 第 3 层 有效因素引擎 | 第 4 层各 skill 内部 | listen 里有情感宣泄，untangle 里有认知改变，see-pattern 里有希望建立 |
| 第 4 层 技能库 | 第 4 层 内部 skills | 一一对应 |
| 第 5 层 陪伴机制设计 | 第 3 层 + 第 2 层 | 部分保留（叙事→日记/回顾），部分克制（镜像模仿、间歇强化有依赖风险） |

**交大团队的交付物应同时体现两套架构：** 遵循他们的第 0-3 层原则（安全、以人为中心、循证），按我们的第 4 层格式交付（声明式触发条件、正确错误示范、references 目录）。

---

## 五、已完成的开发

以下已在 moodcoco/ai-companion 中实现，不需要重新开发：

```
moodcoco/ai-companion/
├── AGENTS.md              — 可可的行为规范
├── IDENTITY.md            — 身份定义
├── SOUL.md                — 人格内核
├── skills/                — 6 个 Skill（其中 2 个待废弃）
│   ├── calm-down/         — 情绪急救（待升级为 calm-body）
│   ├── diary/             — 日记（待升级理论框架）
│   ├── emotion-journal/   — ⚠️ 待废弃（被 diary 替代）
│   ├── relationship-coach/— 关系教练（已达专业级）
│   ├── relationship-skills/— ⚠️ 待废弃（被 relationship-coach 替代）
│   └── sigh/              — 叹气呼吸（已有 RCT 支撑）
└── docs/
    ├── product-knowledge-architecture-v1.0.md  — 交大团队原始架构
    └── references/competitive-research/        — 竞品调研资料
```

---

## 六、Reviewer 需要关注的

1. **阅读本文档**——理解五层架构和关系智能定位
2. **对照 `product-knowledge-architecture-v1.0.md`**——你们的架构和我们的需求怎么对齐（见第四节映射表）
3. **核心交付物是第 4 层**，分两部分：
   - **8 个通用 skill**（P0：listen、untangle、see-pattern、crisis、calm-body、base-communication；P1：face-decision、know-myself）
   - **15 个场景的专属 reference**（每个场景的心理学参考材料、禁忌清单、对话样本——reference 内容由你们填充，我们提供结构和 demo）
4. **第 5 层的三维记忆提取**——人物/事件/自我的提取规则需要心理学审核
5. **第 3 层的触发条件**——"什么时候该主动说什么"需要专业判断（特别是危机干预的分级标准）


---


# 心情可可 · 关系智能产品体验设计

*Version: 3.0 | 2026-04-05*
*基于 relationship-intelligence-upgrade.md 五层产品架构，17 个 Feature，逐条设计*

---

## 总览

### 产品定位

心情可可从"AI 心理陪伴系统"升级为**关系智能平台**。

核心洞察：困住人的不是事情本身，而是人与事情的关系。

三个关系维度：
- 我和**人**的关系（亲密关系、家庭、职场）
- 我和**事件**的关系（考研、缺钱、裁员——我怎么看待这件事）
- 我和**自己**的关系（自我价值、意义感）

### 技术基座

| 组件 | 方案 |
|------|------|
| 记忆引擎 | memU（fork 后修改，PostgreSQL 存储，向量检索暂不开） |
| 对话运行时 | OpenClaw（minimax-m2.7 via OpenRouter） |
| Skill 体系 | 8 个通用引擎 + 5 个运维 skill + 15 个场景 reference |
| 评估 | evolve O-B-C 流水线 |

### Feature 分组（3 Group，17 Feature）

**Group A：地基层（记忆 + 通用引擎）**

| Feature | 名称 | 架构层 |
|---------|------|--------|
| F01 | memU 记忆引擎集成 | 第 5 层 |
| F02 | base-communication（承接/澄清/轻推动） | 第 4 层 |
| F03 | listen（纯倾听） | 第 4 层 |
| F04 | untangle（拆解混乱） | 第 4 层 |
| F05 | crisis（危机干预） | 第 4 层 |
| F06 | calm-body（身体稳定） | 第 4 层 |

**Group B：高级引擎 + 运维 skill**

| Feature | 名称 | 架构层 |
|---------|------|--------|
| F07 | see-pattern（跨关系模式 + 成长叙事） | 第 4 层 |
| F08 | face-decision（决策支持 + 冷却） | 第 4 层 |
| F09 | know-myself（自我探索） | 第 4 层 |
| F10 | diary（日记重构，对接 memU） | 第 2+5 层 |
| F11 | onboarding（首次相遇，对接 memU） | 第 1 层 |
| F12 | farewell（告别仪式，对接 memU） | 第 3 层 |

**Group C：交互层 + 场景材料**

| Feature | 名称 | 架构层 |
|---------|------|--------|
| F13 | check-in + weekly-reflection（对接 memU） | 第 3 层 |
| F14 | 程序主动触发（洞察推送/跟进/成长提醒） | 第 3 层 |
| F15 | 场景路由 + 推荐（15 场景入口） | 第 1 层 |
| F16 | 15 个场景 reference 材料 | 第 4 层 |
| F17 | AGENTS.md 总重构（整合全部新 skill） | 贯穿 |

---

## F01 memU 记忆引擎集成

### 设计哲学

v2 的记忆以"人"为核心，用 .md 文件存结构化档案。v3 升级为"关系"为核心——不只是记住人，还要记住事件进展和自我认知变化。

核心变化：引入 memU 记忆引擎（fork 后修改），提供三层记忆架构（Resource → Item → Category）+ 自动提取 + 智能检索。

> **Reference**: memU 源码在 `/Users/jianghongwei/Documents/GitHub/memU/`，核心模块见 `src/memu/app/`（service.py, memorize.py, retrieve.py）。

### 1. 数据流

对话结束后，Skill 调用 memU 的 `memorize()` 接口，传入完整对话文本。memU 自动执行 7 步流水线：接收对话 → 格式化 → 4 种 prompt 分别提取记忆条目 → 去重 → 分配到三维 Category → 更新 Category 摘要 → 存入 PostgreSQL。

下次对话开始时，Skill 调用 memU 的 `retrieve()` 接口获取相关记忆上下文。当前使用 LLM 模式（不依赖向量检索），后续开通向量服务后切换到 RAG 模式。

### 2. 三维 Category 体系

memU 的 MemoryCategory 用于组织记忆，我们定义三个顶级维度：

**人物维度（`people/*`）** — 动态创建，每认识一个人就多一个 category。如 `people/妈妈`、`people/男朋友`、`people/导师`。

**事件维度（`events/*`）** — 动态创建，每出现新长周期事件就多一个。如 `events/考研`、`events/求职`。

**自我维度（`self/*`）** — 相对固定的 5 个子 category：
- `self/核心信念` — 如"我不值得被爱""我总是不够好"
- `self/行为模式` — 跨关系重复行为，如讨好、回避冲突
- `self/价值观` — 什么对用户重要
- `self/情绪触发点` — 什么情境容易触发强烈情绪
- `self/有效方法` — 哪些应对方式对用户有用

一条 MemoryItem 可以同时属于多个 Category（通过 CategoryItem 多对多关系）。例如"和妈妈因为考研吵架"同时属于 `people/妈妈` + `events/考研`。

每个 Category 有自动生成的 summary，替代了 v2 中 people/{name}.md 的档案功能。

> **建议**: Category 动态创建逻辑写在 memU 的 `categorize_items` 步骤中，当 LLM 返回的 category 名不存在时自动创建，命名规范为 `{dimension}/{entity}`。

### 3. 提取 Prompt 定制

memU 的 4 个提取 prompt（profile/event/behavior/knowledge）需要改写为心理陪伴场景：

| Prompt | 提取内容 | 分配到 |
|--------|---------|-------|
| profile | 用户基本信息、沟通偏好、画像变化 | self/* |
| event | 人物关系、事件进展、退出信号、关键事件 | people/* + events/* |
| behavior | 重复行为模式、有效方法、自我认知变化 | self/行为模式 + self/有效方法 |
| knowledge | 人际关系网络、时间节点、环境信息 | 最相关的 category |

核心原则：只提取用户明确说出的信息，不推测；保留用户原话（引号）；退出信号标注确定性（高/中/低）。

> **Reference**: 现有 prompt 模板在 `memU/src/memu/prompts/memory_type/`，每个 prompt 支持 block-based 自定义（objective/workflow/rules/category/output/examples/input）。

### 4. OpenClaw 兼容层（关键约束）

OpenClaw 的文件分两类，处理方式完全不同：

**首次读取文件（OpenClaw 启动时自动加载到 context，必须保持写入）：**

| 文件 | 加载时机 | 为什么必须保留 |
|------|---------|--------------|
| USER.md | 每次对话启动 | 核心上下文接口，AGENTS.md 30+ 处引用 |
| MEMORY.md | compaction 时 | 长期记忆锚点，不受时间衰减 |
| SOUL.md / IDENTITY.md | agent 启动 | 只读，人格内核 |
| HEARTBEAT.md | Heartbeat 触发 | 调度规则 |

**二次读取文件（Skill 按需读取，由 memU 替代）：**

| 文件 | v3 处理 |
|------|--------|
| people/*.md | 由 memU people/* category 替代，不再写入 |
| diary/*.md | 由 memU Resource + MemoryItem 替代，不再写入 |
| memory/*.md | 由 memU MemoryItem 替代，不再写入 |

**设计原则：首次读取文件保持写入（OpenClaw 硬依赖），二次读取文件由 memU 全权管理。**

### 5. 数据初始化

现有二次读取文件中的数据需要一次性灌入 memU（调 `memorize(modality="document")`）。灌入后这些 .md 文件不再写入。USER.md 和 MEMORY.md 继续正常读写。

### 6. memU 源码修改要点

| 修改点 | 说明 |
|-------|------|
| 4 个提取 prompt | 改写为心理陪伴场景（见 §3） |
| categorize_items 步骤 | 增加动态 category 创建逻辑 |
| 默认 category 配置 | 改为三维体系（5 个 self/* 子 category） |
| LLM 配置 | OpenRouter + minimax-m2.7（memU 已支持 OpenAI 协议） |
| 存储配置 | PostgreSQL，向量索引设为 none |

不需要修改：工作流引擎、数据模型、PostgreSQL 后端、retrieve 流水线、CRUD 操作。

### 7. 桥接脚本

新建 `memu_bridge.py` 作为 OpenClaw Skill 和 memU 的桥接入口，提供 4 个操作：memorize（存储对话记忆）、retrieve（检索记忆）、list_categories（列出用户的 category）、get_category_summary（获取 category 摘要）。

> **建议**: 参考现有 `pattern_engine.py` 的 CLI 接口模式，通过命令行参数调用。

---

## F02 base-communication（承接/澄清/轻推动）

### 设计哲学

不是独立触发的 skill，而是所有对话的地基。定义三组基础沟通技术，所有其他 skill 隐式加载。

来源：交大团队 v1.0 架构第 2 层"基础互动协议"。

### 三组技术

**承接组（Reception）** — 让用户感到被听到：
- 情感反映："听起来你现在很委屈"（不说"我理解你的感受"）
- 内容反映：用自己的话简述事实（不加评判）
- 正常化："换了谁等了三天没消息都会急"（不说"大家都这样"）
- 陪伴式重述：不分析只是在——"嗯，三天了。"
- **规则**：每次对话前 1-2 轮必须先承接。宁可多承接一轮不可少一轮。

**澄清组（Clarification）** — 帮用户把模糊变清楚：
- 开放式提问：用"什么""怎么"开头（不问"为什么"）
- 具体化：从抽象拉回具体——"他说了什么让你最难受？"
- 聚焦：多个话题选一个深入（不同时处理两个话题）
- 例外提问："有没有不一样的时候？"（不在情绪高时问）
- **规则**：一次只问一个问题。连续两次"说不清楚"就不再追问。

**轻推动组（Gentle Nudge）** — 帮她看到更多可能性：
- 多解读：同一件事给 2-3 种解读（不给单一判断）
- 视角转换："如果你是他，当时在想什么？"（不替对方辩护）
- 量表提问：1-10 量化感受（不在情绪爆发时用）
- 假设提问："如果不考虑妈妈的想法，你想怎么选？"
- **规则**：只在承接之后使用。用户抗拒就停，回到承接。

### 加载方式

在 AGENTS.md 中作为全局加载项，不声明触发条件。

> **Reference**: 以人为中心疗法（Rogers）、动机式访谈、临床心理基本沟通技术。

---

## F03 listen（纯倾听）

当用户带着情绪来、需要有人听的时候，可可的工作就是在。不分析、不建议、不引导。

**触发条件**：默认就是 listen。只有满足其他 skill 的触发条件才切走。

**核心动作**：在（短回应）、映射（说出感受）、保留空间（不填满停顿）、跟随（不拉回话题）、确认（"我听到了"而非"我理解"）。

**退出条件**：listen 不主动退出，由 AGENTS.md 路由层判断切换（用户说"搅在一起" → untangle，用户说"该怎么办" → face-decision，情绪过高 → calm-body/crisis 等）。

> **Reference**: 以人为中心疗法（Carl Rogers）——无条件积极关注、共情理解、真诚一致。

---

## F04 untangle（拆解混乱）

帮用户把缠在一起的事情理清楚。把"我很乱"变成"有几件事缠在一起了，我们一件一件看"。

**触发条件**：用户说"好多事搅在一起""脑子很乱"，或一段话混合 ≥3 个不同话题。

**4 阶段流程**：
1. 先接住（不急着拆）
2. 列清单（用用户的话外化："你刚才提到了这几件事..."）
3. 选一个聚焦（"哪个最让你难受？"——用户选，不是可可判断）
4. 深入选中的话题（切换到合适的 skill）

> **Reference**: 叙事疗法外化技术（Michael White）、Lazarus 压力评估、ACT 认知解离。

---

## F05 crisis（危机干预）

安全底线。检测到自伤/自杀风险时，一切其他 skill 让路。

**P0 触发（立即）**：明确的自我伤害意图表达（"不想活了""想死""自残"等）。

**P1 触发（累积）**：连续 2+ 个模糊信号（无望感、突然平静、告别式表达）。

**执行流程**：
1. 接住（"谢谢你告诉我"——不说"别这样想"）
2. 评估当前风险（"你现在安全吗？"）
3. 即时稳定（如需要，调 calm-body）
4. 转介专业资源（心理危机热线 400-161-9995 等）
5. 不松手——提供资源后不结束对话

**安全规则（不可违反）**：不给鸡汤、不替用户定义感受、不道德绑架、不在危机中做模式分析、不假装能替代专业帮助。

**memU 交互**：crisis 对话记录标记高敏感度，retrieve 时不主动返回危机细节。

> **Reference**: QPR 技术（Question-Persuade-Refer）、自杀风险评估标准。

---

## F06 calm-body（身体稳定）

处理身体层面的即时稳定——心跳加速、喘不上气、失眠、恐慌。不讲道理，用身体的方式帮身体冷下来。

来源：现有 breathing-ground skill 升级，新增助眠场景。

**触发条件**：身体症状描述、恐慌/焦虑发作、失眠。与 crisis 的分界：calm-body 处理"没有生命危险的身体不适"。

**5 种干预工具（按优先级）**：
1. 循环叹息 — 两次短吸 + 长呼，1-2 分钟（默认首选）
2. 4-7-8 呼吸 — 失眠场景
3. 方块呼吸 — 需要集中注意力
4. 5-4-3-2-1 感官着陆 — 解离/恐慌严重
5. 身体扫描 — 紧张但清醒

**执行原则**：一步一步引导，等用户回应再继续。完成后不解释为什么有效。

> **Reference**: Stanford 循环叹息 RCT、Andrew Weil 4-7-8、5-4-3-2-1 PTSD 急性干预标准技术。

---

## F07 see-pattern（跨关系模式 + 成长叙事）

可可最核心的差异化能力——帮用户看到跨关系的重复模式。

来源：pattern-mirror + growth-story 合并。

**触发条件（全部满足）**：memU 返回同一 category 下 ≥3 条相似记忆 + ≥5 次对话 + 当前情绪稳定（≥3 个稳定信号）+ 未超频率限制。

**7 阶段流程**：
1. **接住情绪** — 正常 listen，后台调 memU retrieve() 准备数据
2. **等待稳定信号** — 不稳定则停留在 listen
3. **搭桥** — 用户自己说"我每次都这样"直接接住 / 重复了之前的原话 / 请求许可
4. **呈现模式** — 用 memU 中的具体记忆，用用户原话，不加标签
5. **反应处理（⛔ 安全协议）**：
   - E3 情绪洪水 → 立即中止，回到 listen，14 天冷却
   - E1 否认 → 尊重，30 天冷却
   - E2 惊讶 → 给空间，不再加更多模式
   - E4 好奇 → 引导 IFS 探索
6. **意义整合** — 纯探索（IFS）或 + 成长叙事（有对比数据时）
7. **未来锚定** — "下次遇到这种感觉想怎么做？"

**频率保护**：每周最多 2 次，同一模式 14 天间隔，否认后 30 天冷却。通过 memU metadata 管理。

> **Reference**: 叙事疗法重写（Michael White）、CBT 模式识别、IFS 部分工作、创新时刻理论。

---

## F08 face-decision（决策支持 + 冷却）

帮用户面对选择，但永远不替她决定。来源：decision-cooling 扩展。

**双路径**：

**冲动型**（"我现在就去找他"）：
1. 接住冲动（不阻止）
2. EFT 重构："如果今天不做这个决定，明天的你会怎么看？"
3. 提议暂停，约明天再看 → 写入 memU 待跟进
4. 次日 Heartbeat 跟进，引用昨天的具体状态

**纠结型**（"该不该分手"）：
1. 接住纠结
2. 拆解选项（用户列，不是可可列）
3. ACT 价值观澄清："不考虑别人的想法，你心里更想要什么？"
4. 不替决定，允许不决定

> **Reference**: 动机式访谈（Miller & Rollnick）、ACT 价值观澄清、EFT 情绪聚焦重构。

---

## F09 know-myself（自我探索）

帮用户探索"我是谁"——当她说"我为什么总是这样""我是不是有问题"时，帮她看见自己。

**触发条件**：用户没有具体事件在想自己、质疑自我价值、探索身份。

**核心方法**：IFS 部分工作——"那个'讨好的你'在保护你什么？" 引导用户和"部分"对话而非消灭它。追踪自我叙事变化（调 memU retrieve self/核心信念 对比历史）。

**不做的**：不说"你不是太敏感"（替用户定义）、不贴标签（"回避型依恋"）。

> **Reference**: IFS 部分工作（Richard Schwartz）、ACT 自我觉察、内在批评者工作。

---

## F10 diary（日记重构，对接 memU）

用户体验不变——可可帮她记日记。底层切换到 memU。

**触发条件不变**："记一下""写日记""今天发生了"，或对话结束时邀请。

**核心变化**：
- 六元组引导流程不变（事件→情绪→强度→想法→应对→触发）
- 极简/深度模式判断不变（≤30 字 / 30-100 字 / >100 字）
- 情绪精细化 Poll 不变
- 存储：write USER.md（首次读取）+ memU memorize(对话全文)
- 不再写入 diary/*.md、people/*.md、memory/*.md（由 memU 管理）

---

## F11 onboarding（首次相遇，对接 memU）

用户体验不变——自然认识用户，不像填表。底层对接 memU。

**触发条件**：USER.md 不存在 = 新用户。

**7 节点流程不变**（Opening → Discovery → Hold Emotion → AI-unique → Trust Signals → 建档+告别）。

**核心变化**：建档从 write USER.md + write people/{name}.md 改为 write USER.md（首次读取）+ memU memorize()（人物由 memU 管理）。

---

## F12 farewell（告别仪式，对接 memU）

仪式性地封存记忆，提取模式级洞察。人物数据由 memU 管理。

**触发条件不变**：明确告别意图或反复表达封存意图 ≥3 次。

**执行流程**：
1. 确认意愿（不推动）
2. 选择仪式（烧日记/烧信念/时间胶囊/未寄出的信/自由形式）
3. 执行仪式
4. 归档序列：memU retrieve → 提取去名字的模式洞察 → write USER.md 模式级洞察段 + memU memorize → memU 标记 category 为 archived
5. 收尾（1-2 句，见证者角色）

---

## F13 check-in + weekly-reflection（对接 memU）

### check-in

**触发不变**：Heartbeat（24h+无对话）/ Cron（21:30）/ 自然对话。

**核心变化**：用户偏好仍读 USER.md（首次读取），签到记录和上下文改为 memU memorize/retrieve。

### weekly-reflection

**触发不变**：周日 20:00 + 本周 ≥3 条记忆。

**核心变化**：
- 获取本周数据：memU retrieve（替代读 diary/*.md + 跑 weekly_review.py）
- 情绪聚类：memU Category summary 自动聚合（替代 weekly_review.py）
- 成长信号：memU retrieve 对比 self/* 历史 summary（替代 growth_tracker.py）

---

## F14 程序主动触发

第 3 层的触发行为（除 F13 已覆盖的 check-in 和 weekly-reflection）：

| 触发行为 | 数据来源 | 触发条件 | 执行 skill |
|---------|---------|---------|-----------|
| 模式洞察推送 | memU retrieve() | 同类记忆 ≥3 条 + 稳定信号 | see-pattern |
| 事件跟进 | memU retrieve() | 未完结事件 >24h | face-decision |
| 成长提醒 | memU retrieve() | self/* summary 有积极变化 | see-pattern |
| 关系总结 | 当前对话密度 | 密集对话结束时 | diary |
| 情绪急救 / 危机干预 | AGENTS.md pre-check | P0 关键词 | crisis + calm-body |

两个入口：AGENTS.md pre-check（每轮）+ Heartbeat（定时）。

---

## F15 场景路由 + 推荐

15 个预设场景是冷启动入口，用得越多逐渐被用户自己的高频标签替代。

| 场景 | 路由到的 skill 组合 |
|------|-----------------|
| 恋爱 | listen + untangle + see-pattern |
| 家人 | listen + untangle + see-pattern |
| 室友 | listen + untangle |
| 朋友 | listen + untangle |
| 考研 | listen + face-decision + calm-body |
| 考公 | listen + face-decision + calm-body |
| 实习 | listen + untangle + face-decision |
| 求职 | listen + face-decision |
| 毕业 | listen + face-decision + know-myself |
| 学业 | listen + face-decision + calm-body |
| 失眠 | calm-body |
| 认识自己 | know-myself + see-pattern |
| 容貌焦虑 | listen + know-myself |
| 随便聊聊 | listen |
| SOS | crisis |

**推荐演化**：新用户 → 15 预设场景 → memU retrieve 获取高频 category → 按关联频次排序 → 最终全是用户自己的人和事。

**智能推荐**：Heartbeat 触发时，memU retrieve 检查未完结事件和情绪趋势，生成个性化推荐。

---

## F16 15 个场景 reference 材料

Skill 是引擎，Scene 是燃料。同一个 listen，在恋爱场景和考研场景调用不同参考材料。

每个场景一个 `SCENE.md`，声明：调用哪些 skill、场景特有规则/禁忌、高频子场景路由。`references/` 目录放心理学参考材料。

| 场景 | 核心 reference |
|------|---------------|
| 恋爱 | 依恋理论、亲密关系冲突模式、分手哀伤阶段、PUA/爱轰炸识别 |
| 家人 | 原生家庭动力学、代际沟通、分离个体化 |
| 室友 | 宿舍人际边界、被动攻击识别 |
| 朋友 | 社交焦虑、讨好型人格、友谊边界 |
| 考研 | 备考倦怠、同辈比较、自我怀疑周期 |
| 考公 | 体制内外选择、家庭期望压力 |
| 实习 | 职场新人适应、权力距离、犯错恐惧 |
| 求职 | 拒绝敏感、自我价值与外部评价 |
| 毕业 | 身份转换焦虑、丧失感、未来不确定性 |
| 学业 | 拖延心理学、完美主义、截止日期焦虑 |
| 失眠 | 睡眠卫生、认知激活、放松训练 |
| 认识自己 | 自我概念、价值观探索、内在批评者 |
| 容貌焦虑 | 身体意象、社会比较、自我接纳 |
| 随便聊聊 | 无专属 reference，纯 listen |
| SOS | QPR 评估标准、分级规则、转介资源 |

---

## F17 AGENTS.md 总重构

整合 13 个新 skill 的路由逻辑 + memU 集成 + 15 场景路由。

**主要变化**：
- RULE-ZERO：write USER.md + write MEMORY.md + memU memorize()
- Skill 路由：从 5 个扩展到 13 个 skill + 15 场景路由矩阵
- 安全 pre-check：保留现有 4 项检查
- 记忆操作：二次读取全部改为 memU retrieve()
- 时间规则、E-branch 等保持不变

---

## 附录 A：文件处置清单

### 首次读取文件（保留写入，OpenClaw 硬依赖）

| 文件 | 说明 |
|------|------|
| USER.md | 继续按现有 7 字段格式读写 |
| MEMORY.md | 继续作为 compaction 锚点 |
| SOUL.md / IDENTITY.md | 只读，不变 |
| HEARTBEAT.md | 更新内容以整合新 skill |

### 二次读取文件（由 memU 替代，不再写入）

| 文件/目录 | 说明 |
|----------|------|
| people/*.md | 数据灌入 memU 后不再写入 |
| diary/**/*.md | 数据灌入 memU 后不再写入 |
| memory/*.md | 数据灌入 memU 后不再写入 |

### Skill 重命名/合并

| 旧 Skill | 新 Skill |
|----------|---------|
| breathing-ground | → calm-body |
| pattern-mirror + growth-story | → see-pattern |
| decision-cooling | → face-decision |

### 脚本处置

| 旧脚本 | 处理 |
|-------|------|
| pattern_engine.py | 废弃，由 memU retrieve() 替代 |
| growth_tracker.py | 废弃，由 memU retrieve() + Category summary 替代 |
| weekly_review.py | 废弃，由 memU retrieve() 替代 |
| emotion_counter.py | 废弃，由 memU Category summary 替代 |
| crisis_detector.py | 逻辑移入 crisis skill |

## 附录 B：文件目录结构

```
ai-companion/
├── AGENTS.md              — 行为总纲（v3 重构）
├── IDENTITY.md            — 身份定义（不变）
├── SOUL.md                — 人格内核（不变）
├── HEARTBEAT.md           — 主动触发规则（v3 更新）
├── USER.md                — 用户画像（首次读取，保留写入）
├── MEMORY.md              — 长期记忆锚点（首次读取，保留写入）
│
├── skills/                — 13 个 Skill
│   ├── base-communication/    ← F02 新建
│   ├── listen/                ← F03 新建
│   ├── untangle/              ← F04 新建
│   ├── crisis/                ← F05 新建
│   ├── calm-body/             ← F06（原 breathing-ground）
│   ├── see-pattern/           ← F07（原 pattern-mirror + growth-story）
│   ├── face-decision/         ← F08（原 decision-cooling）
│   ├── know-myself/           ← F09 新建
│   ├── diary/                 ← F10 重写
│   ├── onboarding/            ← F11 重写
│   ├── farewell/              ← F12 重写
│   ├── check-in/              ← F13 小改
│   └── weekly-reflection/     ← F13 中改
│
├── scenes/                — 15 个场景 reference
│   ├── 恋爱/
│   ├── 家人/
│   ├── ...（共 15 个）
│   └── SOS/
│
├── scripts/
│   └── memu_bridge.py     — memU 桥接入口
│
└── memu/                  — memU 源码（fork）
    └── src/memu/
```
