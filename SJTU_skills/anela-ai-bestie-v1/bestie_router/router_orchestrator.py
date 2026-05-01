"""Top-level orchestration for the Bestie Agent Policy Layer."""

from __future__ import annotations

import inspect

from .lifecycle_manager import apply_lifecycle
from .memory_controller import apply_memory_decision
from .route_validator import validate_route
from .safety_boundary_gate import apply_safety_boundary_gate
from .signal_extractor import extract_signals
from .skill_policy_router import SkillPolicyRouter
from .types import (
    ExtractedSignals,
    LlmRouteClassifier,
    RouteCard,
    RouterInput,
    SoftRouteSuggestion,
    ensure_router_input,
    ensure_soft_suggestion,
)


class RouterOrchestrator:
    """Stateful-input, deterministic-output router orchestrator.

    The orchestrator is stateless itself. All state required for the decision is
    passed in via RouterInput so the route remains auditable and replayable.
    """

    def __init__(self, llm_classifier: LlmRouteClassifier | None = None) -> None:
        self._soft_provider = llm_classifier
        self._policy_router = SkillPolicyRouter()

    def _soft_suggest(
        self, input_data: RouterInput, signals: ExtractedSignals
    ) -> SoftRouteSuggestion | None:
        if self._soft_provider is None:
            return None
        try:
            suggestion = self._soft_provider.classify(input_data, signals)
            return ensure_soft_suggestion(suggestion)
        except Exception:
            # Soft providers are advisory only. Invalid Pydantic AI output,
            # provider exceptions, or accidental RouteCard-shaped returns must
            # not break the deterministic policy pipeline.
            return None

    async def _soft_suggest_async(
        self, input_data: RouterInput, signals: ExtractedSignals
    ) -> SoftRouteSuggestion | None:
        if self._soft_provider is None:
            return None
        try:
            suggestion = self._soft_provider.classify(input_data, signals)
            if inspect.isawaitable(suggestion):
                suggestion = await suggestion
            return ensure_soft_suggestion(suggestion)
        except Exception:
            return None

    def route_model(self, input_data: RouterInput, *, debug: bool = False) -> RouteCard:
        input_data = ensure_router_input(input_data)
        signals = extract_signals(input_data)

        route = apply_safety_boundary_gate(input_data, signals)
        if route is None:
            soft_suggestion = self._soft_suggest(input_data, signals)
            route = self._policy_router.route(input_data, signals, soft_suggestion)

        route = validate_route(route, input_data, signals)
        route = apply_memory_decision(route, input_data, signals)
        route = validate_route(route, input_data, signals)
        route = apply_lifecycle(route, input_data, signals)

        if debug:
            route["debugSignals"] = signals
        elif "debugSignals" in route:
            del route["debugSignals"]
        return route

    async def route_model_async(
        self, input_data: RouterInput, *, debug: bool = False
    ) -> RouteCard:
        input_data = ensure_router_input(input_data)
        signals = extract_signals(input_data)

        route = apply_safety_boundary_gate(input_data, signals)
        if route is None:
            soft_suggestion = await self._soft_suggest_async(input_data, signals)
            route = self._policy_router.route(input_data, signals, soft_suggestion)

        route = validate_route(route, input_data, signals)
        route = apply_memory_decision(route, input_data, signals)
        route = validate_route(route, input_data, signals)
        route = apply_lifecycle(route, input_data, signals)

        if debug:
            route["debugSignals"] = signals
        elif "debugSignals" in route:
            del route["debugSignals"]
        return route

    def route(self, input_data: RouterInput, *, debug: bool = False) -> dict[str, object]:
        """Return a plain JSON-serializable Route Card dict."""

        return self.route_model(input_data, debug=debug).model_dump(exclude_none=True)

    async def route_async(
        self, input_data: RouterInput, *, debug: bool = False
    ) -> dict[str, object]:
        """Async route helper that can await async Pydantic AI-style providers."""

        route = await self.route_model_async(input_data, debug=debug)
        return route.model_dump(exclude_none=True)


def route_bestie_turn(input_data: RouterInput, *, debug: bool = False) -> dict[str, object]:
    """Route one user turn and return a serializable Route Card."""

    return RouterOrchestrator().route(input_data, debug=debug)


async def route_bestie_turn_async(
    input_data: RouterInput, *, debug: bool = False
) -> dict[str, object]:
    """Async convenience wrapper for API layers that already use await."""

    return await RouterOrchestrator().route_async(input_data, debug=debug)
