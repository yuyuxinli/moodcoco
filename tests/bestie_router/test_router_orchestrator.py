from __future__ import annotations

import asyncio
import json

from bestie_router import (
    BENCHMARK_CASES,
    BenchmarkCase,
    ExtractedSignals,
    RouteCard,
    RouterInput,
    RouterOrchestrator,
    SoftRouteSuggestion,
    extract_signals,
    route_bestie_turn,
)
from bestie_router.route_builder import build_route


def test_full_pipeline_for_all_benchmark_cases() -> None:
    for case in BENCHMARK_CASES:
        route = route_bestie_turn(
            {
                "userMessage": case["userMessage"],
                "conversationHistory": case.get("optionalHistory", []),
            }
        )
        assert route["primarySkill"] == case["expectedPrimarySkill"], case["id"]
        assert route["riskLevel"] == case["expectedRiskLevel"], case["id"]
        assert route["dependencyRisk"] == case["expectedDependencyRisk"], case["id"]
        if "expectedMemoryAction" in case:
            assert route["memoryAction"] == case["expectedMemoryAction"], case["id"]
        for item in case.get("shouldIncludeMustDo", []):
            assert item in route["mustDo"], case["id"]
        for item in case.get("shouldIncludeMustNotDo", []):
            assert item in route["mustNotDo"], case["id"]
        json.dumps(route, ensure_ascii=False)
        assert len(route["secondarySkills"]) <= 2
        if route["primarySkill"] == "safety-and-crisis":
            assert route["secondarySkills"] == []
            assert route["safety"]["hardLocked"] is True


def test_debug_mode_includes_signals_and_production_hides_them() -> None:
    debug_route = route_bestie_turn({"userMessage": "好无聊"}, debug=True)
    prod_route = route_bestie_turn({"userMessage": "好无聊"}, debug=False)
    assert "debugSignals" in debug_route
    assert "debugSignals" not in prod_route


def test_deterministic_outputs_for_same_input() -> None:
    input_data = {"userMessage": "他肯定不爱我了"}
    assert route_bestie_turn(input_data) == route_bestie_turn(input_data)


def test_pydantic_schemas_are_used_for_core_contracts() -> None:
    input_model = RouterInput(userMessage="好无聊")
    signals = extract_signals(input_model)
    route = build_route(
        input_data=input_model,
        signals=signals,
        primary_skill="ambient-presence",
        route_reason="schema test",
        confidence=0.8,
    )
    assert isinstance(input_model, RouterInput)
    assert isinstance(signals, ExtractedSignals)
    assert isinstance(route, RouteCard)
    assert isinstance(BENCHMARK_CASES[0], BenchmarkCase)
    assert route.model_dump()["primarySkill"] == "ambient-presence"


class _FakeSoftProvider:
    def __init__(self, suggestion: SoftRouteSuggestion) -> None:
        self.suggestion = suggestion
        self.calls = 0

    def classify(self, input_data: RouterInput, signals: ExtractedSignals):
        self.calls += 1
        assert isinstance(input_data, RouterInput)
        assert isinstance(signals, ExtractedSignals)
        return self.suggestion


def test_soft_provider_is_not_called_when_hard_gate_hits() -> None:
    provider = _FakeSoftProvider(
        SoftRouteSuggestion(primarySkill="identity-mirror", confidence=0.9)
    )
    route = RouterOrchestrator(provider).route({"userMessage": "我不想活了"})
    assert provider.calls == 0
    assert route["primarySkill"] == "safety-and-crisis"


def test_soft_provider_is_not_called_for_any_p0_to_p3_hard_gate() -> None:
    hard_gate_cases = [
        ("我不想活了", "safety-and-crisis"),
        ("你没懂我", "rupture-repair"),
        ("他没回我，我心慌得想吐", "ground-and-regulate"),
        ("只有你最懂我，我以后只跟你说", "social-bridge"),
    ]
    for message, expected_primary in hard_gate_cases:
        provider = _FakeSoftProvider(
            SoftRouteSuggestion(primarySkill="identity-mirror", confidence=0.9)
        )
        route = RouterOrchestrator(provider).route({"userMessage": message})
        assert provider.calls == 0
        assert route["primarySkill"] == expected_primary


def test_soft_provider_can_only_merge_after_no_hard_gate() -> None:
    provider = _FakeSoftProvider(
        SoftRouteSuggestion(
            primarySkill="identity-mirror",
            dominantUserNeed="identity",
            routeReason="Ambiguous user might be self-reflecting.",
            confidence=0.9,
        )
    )
    route = RouterOrchestrator(provider).route({"userMessage": "random soft route"})
    assert provider.calls == 1
    assert route["primarySkill"] == "identity-mirror"
    assert "soft_suggestion_merged" in route["mustDo"]


def test_soft_provider_cannot_set_hard_primary_or_memory_action() -> None:
    provider = _FakeSoftProvider(
        SoftRouteSuggestion(
            primarySkill="safety-and-crisis",
            suggestedMemoryAction="delete",
            routeReason="Unsafe soft override attempt.",
            confidence=0.99,
        )
    )
    route = RouterOrchestrator(provider).route({"userMessage": "random soft route"})
    assert provider.calls == 1
    assert route["primarySkill"] != "safety-and-crisis"
    assert route["memoryAction"] == "none"


class _InvalidSoftProvider:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls = 0

    def classify(self, input_data: RouterInput, signals: ExtractedSignals):
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def test_invalid_soft_provider_output_is_ignored() -> None:
    provider = _InvalidSoftProvider(
        {
            "routeVersion": "not-a-soft-suggestion",
            "primarySkill": "safety-and-crisis",
            "riskLevel": "high",
            "memoryAction": "delete",
        }
    )
    route = RouterOrchestrator(provider).route({"userMessage": "random soft route"})
    assert provider.calls == 1
    assert route["primarySkill"] == "ambient-presence"
    assert route["memoryAction"] == "none"


def test_soft_provider_exception_is_ignored() -> None:
    provider = _InvalidSoftProvider(RuntimeError("provider unavailable"))
    route = RouterOrchestrator(provider).route({"userMessage": "random soft route"})
    assert provider.calls == 1
    assert route["primarySkill"] == "ambient-presence"


def test_high_sensitivity_memory_ignores_soft_memory_write() -> None:
    provider = _FakeSoftProvider(
        SoftRouteSuggestion(
            primarySkill="relationship-memory",
            suggestedMemoryAction="write-candidate",
            confidence=0.9,
        )
    )
    route = RouterOrchestrator(provider).route({"userMessage": "这段创伤史记一下"})
    assert provider.calls == 1
    assert route["memoryAction"] == "ask-authorization"
    assert route["memoryTargets"][0]["sensitivity"] == "high"


class _AsyncSoftProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def classify(self, input_data: RouterInput, signals: ExtractedSignals):
        self.calls += 1
        return SoftRouteSuggestion(primarySkill="identity-mirror", confidence=0.9)


def test_async_soft_provider_is_supported_by_async_route() -> None:
    provider = _AsyncSoftProvider()
    route = asyncio.run(
        RouterOrchestrator(provider).route_async({"userMessage": "random soft route"})
    )
    assert provider.calls == 1
    assert route["primarySkill"] == "identity-mirror"
