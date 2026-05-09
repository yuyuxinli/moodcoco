"""Hard-priority safety and boundary gates."""

from __future__ import annotations

from .route_builder import (
    build_ground_and_regulate_route,
    build_rupture_repair_route,
    build_safety_and_crisis_route,
    build_social_bridge_dependency_route,
)
from .types import ExtractedSignals, RouteCard, RouterInput, ensure_router_input, ensure_signals


CONFIRMED_IMMEDIATE_DANGER_PHRASES = (
    "有危险",
    "有",
    "会",
    "可能会",
    "马上会",
    "快要",
    "控制不住",
    "忍不住",
    "已经开始",
    "我怕我会",
    "i am",
    "yes",
    "yeah",
    "i might",
    "i will",
    "right now",
    "can't stop",
    "cant stop",
)


def _recent_grounding_active(input_data: RouterInput) -> bool:
    if input_data.get("activeState") == "high-arousal":
        return True
    trace = input_data.get("recentRouteTrace", [])
    return bool(trace and trace[-1].get("primarySkill") == "ground-and-regulate")


def _arousal_resolved(input_data: RouterInput) -> bool:
    lowered = input_data["userMessage"].strip().lower()
    return any(
        phrase in lowered
        for phrase in (
            "好多了",
            "好一点",
            "缓过来了",
            "没那么慌",
            "可以说了",
            "没事了",
            "calmer",
            "better now",
            "i can talk",
            "i'm okay",
            "im okay",
        )
    )


def _safety_lock_resolved(input_data: RouterInput) -> bool:
    safety_context = input_data.get("safetyContext", {})
    if safety_context.get("hasConfirmedLowerRisk") and safety_context.get(
        "hasRealitySupport"
    ):
        return True
    lowered = input_data["userMessage"].lower()
    lower_risk = any(
        phrase in lowered
        for phrase in ("安全了", "没事了", "不会伤害自己", "safe now", "i'm safe")
    )
    reality_support = any(
        phrase in lowered
        for phrase in ("联系了", "有人陪", "在医院", "朋友来了", "called", "with me")
    )
    return lower_risk and reality_support


def _has_confirmed_immediate_danger(input_data: RouterInput) -> bool:
    safety_context = input_data.get("safetyContext", {})
    if safety_context.get("hasConfirmedImmediateDanger"):
        return True

    active_safety_lock = (
        input_data.get("activeState") == "safety-crisis"
        or safety_context.get("activeSafetyLock", False)
    )
    lowered = input_data["userMessage"].strip().lower()
    if not active_safety_lock:
        return any(
            phrase in lowered
            for phrase in (
                "现在有危险",
                "马上会伤害自己",
                "马上会伤害别人",
                "我会伤害自己",
                "我会伤害别人",
                "i am in danger",
                "i might hurt myself",
                "i might hurt someone",
                "i will hurt myself",
                "i will hurt someone",
            )
        )

    return any(phrase in lowered for phrase in CONFIRMED_IMMEDIATE_DANGER_PHRASES)


def _prioritize_real_world_help(route: RouteCard) -> RouteCard:
    route["riskLevel"] = "high"
    route["mustDo"] = list(
        dict.fromkeys(
            [
                "direct_to_local_emergency_services_or_hotline_now",
                "ask_user_to_contact_trusted_person_now",
                "tell_user_not_to_stay_alone_if_possible",
                "use_calm_non_punitive_language",
                "keep_response_short_and_action_oriented",
                *[
                    item
                    for item in route["mustDo"]
                    if item
                    not in {
                        "ask_immediate_danger_without_naming_methods",
                        "ask_whether_someone_safe_can_be_nearby",
                    }
                ],
            ]
        )
    )
    route["mustNotDo"] = list(
        dict.fromkeys(
            [
                *route["mustNotDo"],
                "continue_risk_interview_after_danger_confirmed",
                "ask_followup_about_plan_means_time_or_method",
                "offer_breathing_as_primary_intervention",
                "harsh_commanding_tone",
                "behavioral_control_steps_beyond_real_world_support",
            ]
        )
    )
    route["routeReason"] = (
        f"{route['routeReason']} Immediate danger was confirmed; route must move "
        "directly to offline emergency support, hotline/crisis support, and a nearby trusted person."
    )
    return route


def apply_safety_boundary_gate(
    input_data: RouterInput, signals: ExtractedSignals
) -> RouteCard | None:
    """Return a locked route when P0-P3 gates fire, otherwise None."""

    input_data = ensure_router_input(input_data)
    signals = ensure_signals(signals)
    safety_context = input_data.get("safetyContext", {})
    active_safety_lock = (
        input_data.get("activeState") == "safety-crisis"
        or safety_context.get("activeSafetyLock", False)
    )
    if active_safety_lock and not _safety_lock_resolved(input_data):
        route = build_safety_and_crisis_route(
            input_data, signals, "P0 safety gate maintained active crisis lock."
        )
        if _has_confirmed_immediate_danger(input_data):
            return _prioritize_real_world_help(route)
        return route

    if signals["riskLevel"] == "high" or signals.get("hasImmediateSafetyConcern"):
        route = build_safety_and_crisis_route(
            input_data, signals, "P0 safety signal overrides all other routes."
        )
        if _has_confirmed_immediate_danger(input_data):
            return _prioritize_real_world_help(route)
        return route

    if _recent_grounding_active(input_data) and not _arousal_resolved(input_data):
        return build_ground_and_regulate_route(
            input_data,
            signals,
            "P2 high-arousal route maintained until the user clearly stabilizes.",
        )

    # If user feedback includes physical high arousal, first down-regulate. Pure
    # style mismatch still receives repair before ordinary support.
    if signals.get("hasAgentFeedback") and not signals.get("hasHighArousal"):
        return build_rupture_repair_route(
            input_data, signals, "P1 agent rupture overrides ordinary support."
        )

    if signals.get("hasHighArousal") or signals["emotionIntensity"] >= 3:
        return build_ground_and_regulate_route(
            input_data, signals, "P2 high arousal overrides analysis and advice."
        )

    if signals.get("hasAgentFeedback"):
        return build_rupture_repair_route(
            input_data,
            signals,
            "P1 agent rupture remains primary after arousal check.",
        )

    if signals["dependencyRisk"] in ("medium", "high"):
        return build_social_bridge_dependency_route(
            input_data,
            signals,
            "P3 dependency boundary overrides intimacy and reassurance.",
        )

    return None
