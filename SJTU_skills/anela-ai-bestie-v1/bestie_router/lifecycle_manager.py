"""Conversation lifecycle state machine for route cards."""

from __future__ import annotations

from .types import (
    ConversationState,
    ExtractedSignals,
    RouteCard,
    RouterInput,
    SkillName,
    ensure_route_card,
    ensure_router_input,
    ensure_signals,
)


def _forbidden_for(skill: SkillName) -> list[SkillName]:
    if skill == "safety-and-crisis":
        return ["playful-attunement", "active-celebration", "ambient-presence"]
    if skill == "ground-and-regulate":
        return ["identity-mirror", "collaborative-untangling"]
    if skill == "active-celebration":
        return ["reality-soft-check"]
    if skill == "vent-container":
        return ["reality-soft-check"]
    if skill == "rupture-repair":
        return ["agency-next-step"]
    if skill == "agency-next-step":
        return ["social-bridge"]
    if skill == "social-bridge":
        return ["active-celebration"]
    return []


def _state_for_route(route: RouteCard, signals: ExtractedSignals) -> ConversationState:
    skill = route["primarySkill"]
    if skill == "safety-and-crisis":
        return "safety-crisis"
    if skill == "rupture-repair":
        return "relationship-repair"
    if skill == "ground-and-regulate":
        return "high-arousal"
    if route["dependencyRisk"] in ("medium", "high"):
        return "dependency-boundary"
    if skill in ("agency-next-step", "social-bridge"):
        return "action-planning"
    if skill in (
        "reality-soft-check",
        "collaborative-untangling",
        "identity-mirror",
        "pattern-witness",
    ):
        return "meaning-making"
    if skill in ("responsive-listening", "emotion-labeling", "vent-container"):
        return "emotional-opening"
    if signals["entryType"] == "negative-emotion":
        return "emotional-opening"
    return "light-connection"


def _enter_reason(
    state: ConversationState, route: RouteCard, signals: ExtractedSignals
) -> str:
    if state == "safety-crisis":
        return "Safety risk or active safety lock requires crisis protocol."
    if state == "relationship-repair":
        return "User gave feedback that the AI missed, forgot, or mismatched style."
    if state == "high-arousal":
        return "High arousal or impulse signals require body-safety screening and short regulation first."
    if state == "dependency-boundary":
        return "AI exclusivity or dependency signal requires de-exclusivizing support."
    if state == "action-planning":
        return "User is preparing a message, decision, or concrete next step."
    if state == "meaning-making":
        if signals.get("repetitionCount", 1) >= 4:
            return "Repeated same-event rumination needs loop protection."
        return "User is seeking clarity, identity reflection, or pattern meaning."
    if state == "emotional-opening":
        return "User is sharing emotion and needs validation before advice."
    return f"Low-pressure connection routed to {route['primarySkill']}."


def _exit_condition(state: ConversationState) -> str:
    return {
        "light-connection": "Check for explicit event, emotion, task request, or risk word.",
        "emotional-opening": "Check whether emotion rises, user asks for advice, or loop repeats.",
        "high-arousal": "Check whether acute body danger appears, safety risk appears, or intensity drops to 0-2.",
        "meaning-making": "Check whether user wants action, arousal rises, or analysis is rejected.",
        "action-planning": "Check for pre-action panic, relationship expression need, or decision delegation.",
        "relationship-repair": "Check whether user confirms adjusted style or stays dissatisfied.",
        "dependency-boundary": "Check whether user accepts AI as one support among others or crisis appears.",
        "safety-crisis": "Do not exit until immediate risk is lower and real-world support/action is in place.",
        "unknown": "Check next user turn for clearer route signals.",
    }[state]


def _stable_skill(state: ConversationState, route: RouteCard) -> SkillName:
    return {
        "light-connection": route["primarySkill"],
        "emotional-opening": "collaborative-untangling",
        "high-arousal": "responsive-listening",
        "meaning-making": "agency-next-step",
        "action-planning": route["primarySkill"],
        "relationship-repair": "responsive-listening",
        "dependency-boundary": "social-bridge",
        "safety-crisis": "ground-and-regulate",
        "unknown": route["primarySkill"],
    }[state]


def _worse_skill(state: ConversationState) -> SkillName:
    return {
        "light-connection": "responsive-listening",
        "emotional-opening": "ground-and-regulate",
        "high-arousal": "safety-and-crisis",
        "meaning-making": "ground-and-regulate",
        "action-planning": "ground-and-regulate",
        "relationship-repair": "safety-and-crisis",
        "dependency-boundary": "safety-and-crisis",
        "safety-crisis": "safety-and-crisis",
        "unknown": "responsive-listening",
    }[state]


def apply_lifecycle(
    route: RouteCard, input_data: RouterInput, signals: ExtractedSignals
) -> RouteCard:
    route = ensure_route_card(route)
    input_data = ensure_router_input(input_data)
    signals = ensure_signals(signals)
    state = _state_for_route(route, signals)
    if input_data.get("activeState") == "safety-crisis" and route[
        "primarySkill"
    ] == "safety-and-crisis":
        state = "safety-crisis"

    route["lifecycle"] = {
        "currentState": state,
        "enterReason": _enter_reason(state, route, signals),
        "exitConditionToCheck": _exit_condition(state),
        "nextSkillIfStable": _stable_skill(state, route),
        "nextSkillIfWorse": _worse_skill(state),
        "forbiddenTransitions": _forbidden_for(route["primarySkill"]),
    }
    return route
