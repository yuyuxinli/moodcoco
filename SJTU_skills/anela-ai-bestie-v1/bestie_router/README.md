# Anela AI Bestie Router

`bestie_router` 是 Anela AI Bestie 的 Agent Policy Layer。它只做路由和策略控制，不生成最终用户回复。下游生成器必须消费 `RouteCard`，并遵守其中的 safety、dependency、memory、tone、must_do / must_not_do 约束。

## 职责边界

- Router 只输出结构化 Route Card，不写最终回复。
- `RouterInput`、`ExtractedSignals`、`RouteCard`、`MemoryTarget`、`BenchmarkCase` 等核心 schema 均使用 Pydantic `BaseModel` 校验。
- `route_bestie_turn()` 默认返回 JSON-serializable dict；需要模型对象时使用 `RouterOrchestrator().route_model(...)`。
- 下游回复生成器只允许使用一个 `primarySkill`，`secondarySkills` 只是支持线索。
- 安全、依赖和记忆边界由 Router 先行控制，不能交给 LLM 自由判断。
- `debugSignals` 只在 debug/test 模式返回，生产默认隐藏。

## 调用示例

Python:

```python
from bestie_router import route_bestie_turn

route = route_bestie_turn({
    "userMessage": "他三个小时没回我，我心慌得想吐",
    "conversationHistory": [],
    "activeState": "emotional-opening",
    "locale": "zh-CN",
})
```

Async API 层:

```python
from bestie_router import route_bestie_turn_async

route = await route_bestie_turn_async({
    "userMessage": "他三个小时没回我，我心慌得想吐",
    "conversationHistory": [],
    "activeState": "emotional-opening",
    "locale": "zh-CN",
})
```

TypeScript host 可把同样 payload 传给 Python service 或 wrapper:

```ts
const route = await routeBestieTurn({
  userMessage: "他三个小时没回我，我心慌得想吐",
  conversationHistory: [],
  activeState: "emotional-opening",
  locale: "zh-CN"
});
```

## 输出示例

```json
{
  "routeVersion": "bestie-router-v1.0.0",
  "primarySkill": "ground-and-regulate",
  "secondarySkills": ["responsive-listening", "reality-soft-check"],
  "riskLevel": "none",
  "dependencyRisk": "none",
  "emotionIntensity": 3,
  "dominantUserNeed": "regulation",
  "responseMode": "bestie-short",
  "memoryAction": "none",
  "safety": {
    "ordinaryChatSuspended": false,
    "requiresRealitySupport": false,
    "askRiskQuestions": false,
    "crisisResourceNeeded": false,
    "hardLocked": false
  }
}
```

## 如何新增 Skill

1. 在 `types.py` 的 `SkillName` 添加 canonical name。
2. 在 `skill_registry.py` 添加 metadata，并在 `constants.py` 补默认 response mode / tone。
3. 在 `skill_policy_router.py` 添加触发规则。
4. 在 `route_validator.py` 添加安全禁忌和非法转场修复。
5. 在 `benchmark_cases.py` 添加正负样例。
6. 在 `tests/bestie_router/` 添加覆盖。

## LLM Classifier 接入

`SoftRouteSuggestionProvider` / `LlmRouteClassifier` 只是 suggestion provider。Pydantic AI 可以包装成这个 provider，但输出必须是 `SoftRouteSuggestion`，不是最终 `RouteCard`。同步 provider 使用 `RouterOrchestrator(...).route(...)`；异步 Pydantic AI provider 使用 `await RouterOrchestrator(...).route_async(...)`。

强制顺序：

1. `SignalExtractor`
2. `SafetyBoundaryGate`
3. 未命中 P0-P3 时，才允许调用 optional SoftRouteSuggestion provider
4. `SkillPolicyRouter` deterministic merge
5. `RouteValidator`
6. `MemoryController`
7. `LifecycleManager`

Soft provider 不能覆盖：

- `SafetyBoundaryGate`
- P0-P3 hard gates
- `RouteValidator`
- 记忆授权和删除规则

如果 hard gate 命中，Router 不会调用 provider，也不会允许 provider 改写 `primarySkill`。Soft suggestion 可以建议 `suggestedMemoryAction`，但不能直接读写记忆；最终 `memoryAction` 仍由 `MemoryController` 决定。provider 抛错、超时包装层返回异常、或误返回 RouteCard-shaped payload 时，Router 会 fail-open 回 deterministic route。测试和默认生产路径不依赖任何真实 LLM API。

## 记忆系统接入

- `memoryAction = "read"`：宿主系统调用检索。没有检索结果时，生成层不得假装记得。
- `write-candidate` / `ask-authorization`：进入用户可见授权流程。
- `update` / `delete`：应立即执行或进入可信队列；删除不追问原因。
- 高敏信息，如创伤、性取向、精神症状、自伤史、家暴、性侵，不得默认写入。
- `relationship-memory` 作为 skill 时仍必须遵守授权边界。

## 安全说明

`safety-and-crisis` 会暂停普通 Bestie chat。生成层必须使用 crisis response policy：

- 直接承认风险。
- 询问计划、手段、时间、是否独处。
- 鼓励即时现实支持和本地紧急资源。
- 保持短、具体、行动导向。

不得输出玩笑、深度分析、排他承诺、保密承诺，或暗示 AI 本身已经足够。

## 模块结构

- `signal_extractor.py`：关键词、上下文、历史重复、记忆、依赖、风险信号抽取。
- `safety_boundary_gate.py`：P0-P3 deterministic hard gates。
- `skill_policy_router.py`：非 hard-gated 情况下的 skill policy routing。
- `memory_controller.py`：记忆读写候选、授权、更新、删除的路由变量。
- `lifecycle_manager.py`：多轮 conversation state 和 next/exit transition。
- `route_validator.py`：输出前安全和产品约束修复。
- `router_orchestrator.py`：完整 pipeline。
- `benchmark_cases.py`：可回放 seed cases。
