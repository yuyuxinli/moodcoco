# ClawWork 调研报告

> 来源：https://github.com/HKUDS/ClawWork  
> 调研日期：2026-04-05  
> 调研目的：评估 ClawWork 的任务执行框架是否适用于心情可可的主动触发场景

---

## 1. 项目定位

ClawWork 是香港大学 HKUDS 团队的开源项目，核心思路是**把 AI 助手变成 AI 同事**——通过经济压力倒逼 agent 产出高质量工作。

**一句话总结**：Agent 从 $10 起步，每次 LLM 调用扣钱，只有完成专业任务（GDPVal 220 题）并通过 LLM 评审才能挣钱。活不下去就破产。

**排行榜数据**：最强 agent（ATIC + Qwen3.5-Plus）8 小时挣 $19,915，时薪 $2,285，质量合格率 61.6%。

---

## 2. 架构概览

```
ClawWork/
├── livebench/          # 独立仿真模式（Standalone）
│   ├── agent/
│   │   ├── live_agent.py          # 主循环：每日选任务 → decide → execute → submit
│   │   ├── economic_tracker.py    # 余额/成本/收入追踪
│   │   ├── wrapup_workflow.py     # 超时兜底：LangGraph 收集遗留 artifact
│   │   └── message_formatter.py
│   ├── work/
│   │   ├── task_manager.py        # 任务加载/分配（parquet/jsonl/inline）
│   │   └── evaluator.py           # GPT-5.2 评审 + 行业评分标准
│   ├── tools/
│   │   ├── direct_tools.py        # 8 个核心工具（LangChain @tool）
│   │   └── productivity/          # search_web, create_file, execute_code 等
│   ├── prompts/
│   │   └── live_agent_prompt.py   # System prompt 模板
│   ├── api/server.py              # FastAPI + WebSocket
│   └── configs/                   # JSON 配置文件
│
├── clawmode_integration/  # Nanobot/OpenClaw 集成模式
│   ├── agent_loop.py      # 继承 nanobot AgentLoop，注入经济工具
│   ├── tools.py           # 4 核心工具移植为 nanobot Tool ABC
│   ├── artifact_tools.py  # 文件创建/读取工具
│   ├── provider_wrapper.py # TrackedProvider 拦截每次 LLM 调用扣钱
│   ├── task_classifier.py  # 44 职业分类器
│   ├── config.py           # 从 ~/.nanobot/config.json 读配置
│   └── skill/SKILL.md      # Nanobot skill：经济生存协议
│
├── eval/                  # 评估体系
│   └── meta_prompts/      # 44 个职业的评分标准 JSON
│
└── frontend/              # React 仪表盘
```

**两种运行模式**：
1. **Standalone**：LiveAgent 直接用 LangChain + ChatOpenAI 跑仿真循环
2. **ClawMode**：嵌入 Nanobot（OpenClaw 的 agent 框架），通过 ClawWorkAgentLoop 继承 nanobot 的 AgentLoop，给任何 Nanobot 网关加上经济追踪

---

## 3. 8 个 Agent 工具详解

### 3.1 核心工具（4 个）

| 工具 | 实现位置 | 功能 | 关键设计 |
|------|---------|------|---------|
| **decide_activity** | `direct_tools.py` / `tools.py` | 选择 "work" 或 "learn" | reasoning 最少 50 字符，强制 agent 给出理由 |
| **submit_work** | `direct_tools.py` / `tools.py` | 提交工作成果 + 文件 | 支持纯文本/纯文件/混合；调用 evaluator 评分；evaluation_score < 0.6 则 $0 |
| **learn** | `direct_tools.py` / `tools.py` | 持久化知识到 memory | 写入 `memory/memory.jsonl`，knowledge 最少 200 字符 |
| **get_status** | `direct_tools.py` / `tools.py` | 查余额/状态 | 返回 balance, net_worth, daily_cost, survival_status |

### 3.2 生产力工具（4+ 个）

| 工具 | 功能 | 成本追踪 |
|------|------|---------|
| **search_web** | Tavily（$0.0008/次）或 Jina 搜索 | 通过 EconomicTracker.track_flat_api_call |
| **create_file** | 创建 txt/xlsx/docx/pdf 等文件 | 无额外成本 |
| **execute_code_sandbox** | 在 E2B 或 BoxLite 沙箱执行 Python | 通过 ARTIFACT_PATH 标记自动下载文件 |
| **read_file** | 读取各种格式文件（PDF 支持 OCR） | 无额外成本 |
| **create_video** | 从 slides JSON 生成 MP4 | 无额外成本 |
| **read_webpage** | Tavily Extract 提取网页内容 | $0.00016/次 |

### 3.3 ClawMode 额外工具

| 工具 | 功能 |
|------|------|
| **create_artifact** | 在 sandbox 目录创建文件（`artifact_tools.py`） |
| **read_artifact** | 读取 PDF/DOCX/XLSX 等文件内容（`artifact_tools.py`） |

### 3.4 工具实现模式

**Standalone 模式**：用 LangChain `@tool` 装饰器 + `_global_state` 全局字典传递状态。简单但不优雅。

**ClawMode 模式**：用 nanobot `Tool` ABC + `ClawWorkState` dataclass。更干净：
```python
@dataclass
class ClawWorkState:
    economic_tracker: Any
    task_manager: Any
    evaluator: Any
    signature: str = ""
    current_date: str | None = None
    current_task: dict | None = None
    data_path: str = ""
```

每个工具类通过 `__init__(self, state: ClawWorkState)` 注入共享状态。

---

## 4. Memory 机制深度分析

### 4.1 当前实现：JSONL 追加

```python
# learn() 工具核心逻辑
entry = {
    "date": date,
    "timestamp": datetime.now().isoformat(),
    "topic": topic,
    "knowledge": knowledge,  # 至少 200 字符
}
# 追加到 memory/memory.jsonl
```

**存储**：`{data_path}/memory/memory.jsonl`，每条记录一行 JSON。

**读取**：当前代码中没有 retrieval 机制——learn() 只写不读。System prompt 中提到 `get_memory()` 和 `save_to_memory()` 但实际工具列表中没有实现。这是 ClawWork 的一个明显缺口。

### 4.2 设计意图

从 prompt 和 roadmap 可以看出：
- 学习是一种**投资行为**：不产生即时收入，但积累知识帮助未来任务
- Roadmap 中明确列出 "Semantic memory retrieval for smarter learning reuse" 为待办
- 当前的 memory 是**只写**的，agent 无法在后续任务中检索之前学到的知识

### 4.3 评价

**优点**：
- JSONL 格式简洁、可追溯、易调试
- 按日期+topic 组织，有完整时间戳
- 200 字符下限保证了知识质量底线

**缺点**：
- 没有检索机制，memory 无法复用
- 没有去重/合并逻辑
- 没有语义索引，无法按相关性召回
- 不支持跨 session 的知识注入

---

## 5. 任务执行框架分析

### 5.1 每日循环（Daily Loop）

```
1. select_daily_task(date) → 从 GDPVal 220 题中随机/顺序分配
2. 构建 system prompt（含经济状态 + 任务描述 + 工具说明）
3. Agent 调用 decide_activity("work"/"learn")
4. 如果 work:
   a. 最多 15 次迭代（tool calls）
   b. 必须调用 submit_work() 提交
   c. evaluator 用 GPT-5.2 评分
   d. score >= 0.6 → 获得 payment = score × hours × BLS_hourly_wage
5. 如果 learn:
   a. 调用 learn(topic, knowledge) 保存知识
6. 保存每日经济状态
```

### 5.2 经济追踪（EconomicTracker）

- **余额**：`current_balance = initial_balance - total_token_cost + total_work_income`
- **成本追踪**：按 task_id 聚合，分 llm_tokens / search_api / ocr_api / other_api 四个 channel
- **Token 追踪**：支持 OpenRouter 直报成本 + 本地估算两种模式
- **持久化**：`balance.jsonl`（每日状态）+ `token_costs.jsonl`（每任务成本）+ `task_completions.jsonl`（完成记录）
- **生存状态**：bankrupt (<=0) / struggling (<100) / stable (<500) / thriving (>=500)

### 5.3 评估体系

- **评估器**：`WorkEvaluator` → `LLMEvaluator`
- **评分模型**：GPT-5.2（hardcoded）
- **评分标准**：44 个职业各有专属 JSON rubric（`eval/meta_prompts/`）
- **支付公式**：`payment = quality_score × estimated_hours × BLS_hourly_wage`
- **质量门槛**：score < 0.6 → $0 payment（cliff，不是线性衰减）

### 5.4 超时兜底（WrapUp Workflow）

当 agent 达到迭代上限但未提交时，`WrapUpWorkflow`（基于 LangGraph）自动：
1. 列出沙箱中所有文件
2. 用 LLM 选择要提交的 artifact
3. 下载并提交

---

## 6. ClawMode（Nanobot 集成）架构

### 6.1 核心组件

```python
class ClawWorkAgentLoop(AgentLoop):
    # 继承 nanobot AgentLoop
    # 注入 4 核心工具 + 2 artifact 工具
    # 包装 provider 为 TrackedProvider
    # 拦截 /clawwork 命令
```

### 6.2 /clawwork 命令流程

```
用户: /clawwork Write a market analysis for electric vehicles
  ↓
TaskClassifier 分类 → occupation="Financial_Analysts", hours=2.5, wage=$47.5/hr
  ↓
构建 synthetic task → task_value = 2.5 × 47.5 = $118.75
  ↓
注入任务上下文 → 重写消息 → 交给正常 agent loop
  ↓
Agent 用 nanobot 工具（write_file 等）完成工作
  ↓
调用 submit_work() → evaluator 评分 → 按质量付款
  ↓
Response 末尾附带: "Cost: $0.0075 | Balance: $999.99 | Status: thriving"
```

### 6.3 TrackedProvider

```python
class TrackedProvider(LLMProvider):
    # 包装任何 nanobot LLMProvider
    # 每次 LLM 调用后自动：
    #   1. 提取 token usage
    #   2. 调用 economic_tracker.track_tokens()
    #   3. 扣除余额
```

支持 OpenRouter 的 `cost` 字段直报（不依赖本地价格公式）。

---

## 7. 对心情可可的适用性评估

### 7.1 核心差异

| 维度 | ClawWork | 心情可可 |
|------|---------|---------|
| **目标** | 经济生存：挣钱 > 花钱 | 情绪陪伴：看见情绪/原因/模式/方法 |
| **驱动力** | 外部任务分配（GDPVal） | 用户主动倾诉 + 系统主动触发 |
| **评估** | GPT 评分 0-1（质量） | 5 维 9 分标准（情绪/原因/模式/方法/安全） |
| **工具** | 生产力工具（写文件/跑代码） | 陪伴技能（倾听/共情/引导/CBT） |
| **Memory** | JSONL 只写（无检索） | 需要关系智能（跨对话追踪模式） |

### 7.2 可借鉴的设计

**1. 任务执行框架（部分可用）**

ClawWork 的 Daily Loop 模式：
```
select_task → decide_activity → execute → submit → evaluate
```

映射到心情可可的主动触发：
```
触发器检测 → 选择场景（签到/周回顾/事件跟进）→ 执行对话 → 评估效果
```

可借鉴点：
- `decide_activity` 的 reasoning 强制机制 → 可用于 agent 决策是否主动触发的理由记录
- 迭代次数上限 + 超时兜底 → 避免 agent 陷入死循环
- 每次交互的成本追踪 → 控制 token 预算

**2. ClawWorkState 共享状态模式**

```python
@dataclass
class ClawWorkState:
    economic_tracker: Any
    task_manager: Any
    evaluator: Any
    ...
```

这种 dataclass 注入模式比全局字典好，心情可可可以用类似模式管理：
```python
@dataclass
class CocoSessionState:
    user_profile: UserProfile
    emotion_tracker: EmotionTracker
    relationship_memory: RelationshipMemory
    current_session: SessionContext
```

**3. EconomicTracker 的 task-level 聚合**

按 task_id 聚合所有成本的设计很好。心情可可可以按 session_id 聚合，追踪每次对话的 token 成本。

### 7.3 不适用的部分

**1. 经济生存模型**

ClawWork 的核心是经济压力——这对情绪陪伴场景完全不适用。用户不应该感受到任何"成本压力"。可以保留内部成本追踪（用于运营），但不应影响对话质量。

**2. 工作提交/评估流程**

`submit_work → evaluator.evaluate_artifact` 是面向"交付物"的。情绪陪伴没有明确的"交付物"，评估维度完全不同（不是质量 0-1，而是看见情绪/原因/模式/方法各 9 分）。

**3. GDPVal 任务分配**

220 个职业任务的分配逻辑完全不适用。心情可可的"任务"来自：
- 用户主动倾诉（被动触发）
- 每日签到（定时触发）
- 周回顾（定时触发）
- 事件跟进（条件触发：检测到用户之前提到的事件到期）

**4. Memory 只写设计**

ClawWork 的 learn() 只写不读，这对心情可可是致命缺陷。关系智能的核心就是跨对话记忆的检索和模式识别。

### 7.4 主动触发场景的可行方案

ClawWork 的 Daily Loop 模式可以改造为心情可可的主动触发框架：

```
# 每日签到
trigger: cron("0 9 * * *")
flow:
  1. check_user_state()     # 昨天的情绪/未完成事项
  2. decide_approach()       # 选择签到方式（直接问候/回顾昨天/轻松开场）
  3. send_greeting()         # 发送签到消息
  4. wait_response()         # 等待用户回复（或超时放弃）

# 周回顾
trigger: cron("0 20 * 0")   # 每周日晚 8 点
flow:
  1. aggregate_week_data()   # 聚合本周情绪数据
  2. identify_patterns()     # 识别重复模式
  3. compose_review()        # 生成回顾内容
  4. send_review()           # 发送

# 事件跟进
trigger: event_due("user mentioned exam on Friday")
flow:
  1. recall_context()        # 回忆用户之前的描述
  2. compose_followup()      # 生成跟进消息
  3. send_followup()         # 发送
```

但这些都需要 **OpenClaw 的 cron 能力**（定时触发）和 **Memory 的检索能力**，而不是 ClawWork 的经济模型。

---

## 8. 结论

### ClawWork 的价值

- **作为 benchmark 框架**：优秀。用经济压力测试 agent 的工作能力，设计精巧。
- **作为 Nanobot 插件模式**：ClawWorkAgentLoop 继承 + TrackedProvider 包装的架构值得学习。
- **作为工具注册模式**：ClawWorkState dataclass + Tool ABC 是干净的依赖注入。

### 对心情可可的建议

| 可借鉴 | 不可借鉴 |
|--------|---------|
| ClawWorkState 共享状态模式 | 经济生存模型 |
| Task-level 成本聚合追踪 | GDPVal 任务分配 |
| 迭代上限 + 超时兜底 | submit_work + evaluator 流程 |
| TrackedProvider 包装模式 | Memory 只写设计 |
| Tool ABC + dataclass 注入 | 每日二选一（work/learn）决策 |

**最终判断**：ClawWork 的**任务执行框架**（Daily Loop + 工具调用 + 成本追踪）有参考价值，但其核心设计（经济生存）与心情可可的需求（情绪陪伴 + 关系智能）差距太大，不建议直接采用。心情可可的主动触发场景更需要的是 OpenClaw 原生的 **cron 触发** + **Memory 检索** 能力，而不是 ClawWork 的经济模型。

建议后续重点研究 Nanobot 本身的 cron/spawn/memory 能力，而非 ClawWork 的经济层。
