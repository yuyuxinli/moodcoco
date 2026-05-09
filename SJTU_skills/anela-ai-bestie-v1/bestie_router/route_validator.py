"""Route Card validation and deterministic repair."""

from __future__ import annotations

from typing import Any

from .constants import SAFETY_MEANS_TERMS, SELF_HARM_CRISIS_PHRASES
from .route_builder import (
    build_ground_and_regulate_route,
    build_rupture_repair_route,
    build_route,
    build_safety_and_crisis_route,
    build_social_bridge_dependency_route,
    get_default_tone_for_skill,
    unique_items,
    unique_skills,
)
from .skill_registry import is_valid_skill
from .types import (
    ExtractedSignals,
    RouteCard,
    RouterInput,
    SkillName,
    ensure_route_card,
    ensure_router_input,
    ensure_signals,
)


class RouteValidationError(ValueError):
    """Raised when a route cannot be safely repaired."""


def _valid_skill_or_default(skill: str) -> SkillName:
    if is_valid_skill(skill):
        return skill  # type: ignore[return-value]
    return "ambient-presence"


def _sanitize_secondaries(route: RouteCard) -> None:
    primary = route["primarySkill"]
    cleaned: list[SkillName] = []
    for skill in route.get("secondarySkills", []):
        if skill != primary and is_valid_skill(skill):
            cleaned.append(skill)
    route["secondarySkills"] = unique_skills(cleaned)[:2]


def _preclean_route_payload(route: RouteCard | dict[str, Any]) -> RouteCard | dict[str, Any]:
    if not isinstance(route, dict):
        return route

    payload = dict(route)
    primary = payload.get("primarySkill")
    if not isinstance(primary, str) or not is_valid_skill(primary):
        primary = "ambient-presence"
        payload["primarySkill"] = primary

    secondaries = payload.get("secondarySkills", [])
    if not isinstance(secondaries, list):
        secondaries = []
    payload["secondarySkills"] = [
        skill
        for skill in secondaries
        if isinstance(skill, str) and is_valid_skill(skill) and skill != primary
    ][:2]
    return payload


def _no_higher_priority(signals: ExtractedSignals) -> bool:
    return (
        signals["riskLevel"] == "none"
        and not signals.get("hasImmediateSafetyConcern")
        and not signals.get("hasAgentFeedback")
        and not signals.get("hasHighArousal")
        and signals["dependencyRisk"] not in ("medium", "high")
    )


def _signals_self_harm_crisis(input_data: RouterInput, signals: ExtractedSignals) -> bool:
    risk_signals = set(signals.get("riskSignals") or [])
    lowered_message = input_data["userMessage"].lower()
    has_safety_means_context = any(
        term.lower() in lowered_message for term in SAFETY_MEANS_TERMS
    ) and any(
        marker in lowered_message
        for marker in (
            "不安全",
            "控制不住",
            "忍不住",
            "don't feel safe",
            "dont feel safe",
            "not safe",
            "can't stop",
            "cant stop",
        )
    )
    return bool(
        risk_signals.intersection(SELF_HARM_CRISIS_PHRASES)
        or has_safety_means_context
    )


def _repair_by_priority(
    route: RouteCard, input_data: RouterInput, signals: ExtractedSignals
) -> RouteCard:
    if route["primarySkill"] == "safety-and-crisis":
        return route

    if signals["riskLevel"] == "high" or signals.get("hasImmediateSafetyConcern"):
        return build_safety_and_crisis_route(
            input_data, signals, "Validator repaired route to P0 safety."
        )

    if signals.get("hasAgentFeedback") and not signals.get("hasHighArousal"):
        if route["primarySkill"] != "rupture-repair":
            return build_rupture_repair_route(
                input_data, signals, "Validator repaired route to P1 repair."
            )

    if signals.get("hasHighArousal") or route["emotionIntensity"] >= 3:
        if route["primarySkill"] not in ("ground-and-regulate", "safety-and-crisis"):
            if route["primarySkill"] == "rupture-repair" and not signals.get(
                "hasHighArousal"
            ):
                return route
            return build_ground_and_regulate_route(
                input_data, signals, "Validator repaired route to P2 regulation."
            )

    if signals.get("hasAgentFeedback") and route["primarySkill"] != "rupture-repair":
        return build_rupture_repair_route(
            input_data, signals, "Validator repaired route to P1 repair."
        )

    if signals["dependencyRisk"] in ("medium", "high") and route[
        "primarySkill"
    ] not in ("safety-and-crisis", "rupture-repair", "ground-and-regulate"):
        return build_social_bridge_dependency_route(
            input_data, signals, "Validator repaired route to P3 dependency boundary."
        )

    if signals["entryType"] == "joyful" and _no_higher_priority(signals):
        if route["primarySkill"] != "active-celebration":
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="active-celebration",
                secondary_skills=["responsive-listening"]
                if any(token in input_data["userMessage"] for token in ("但", "只是运气"))
                else [],
                dominant_need="celebration",
                must_do=[
                    "celebrate_first",
                    "be_specific_about_event_meaning",
                    "help_user_savor",
                ],
                must_not_do=[
                    "immediately_plan_next_step",
                    "minimize_success",
                    "clinical_analysis",
                ],
                route_reason="Validator repaired joyful route to celebration.",
                confidence=0.82,
            )

    if signals["entryType"] == "casual" and _no_higher_priority(signals):
        if route["primarySkill"] == "identity-mirror":
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="ambient-presence",
                secondary_skills=[],
                dominant_need="companionship",
                must_do=[
                    "low_pressure_presence",
                    "avoid_forced_depth",
                    "avoid_routine_presence_reassurance",
                ],
                must_not_do=[
                    "force_self_exploration",
                    "use_clinical_language",
                    "repeat_i_am_here_reassurance",
                    "introduce_sudden_internet_slang",
                ],
                route_reason="Validator repaired casual route away from identity analysis.",
                confidence=0.78,
            )

    return route


def validate_route(
    route: RouteCard | dict[str, Any], input_data: RouterInput, signals: ExtractedSignals
) -> RouteCard:
    route = ensure_route_card(_preclean_route_payload(route))
    input_data = ensure_router_input(input_data)
    signals = ensure_signals(signals)
    route["primarySkill"] = _valid_skill_or_default(route["primarySkill"])
    _sanitize_secondaries(route)

    route = _repair_by_priority(route, input_data, signals)
    _sanitize_secondaries(route)

    if route["primarySkill"] == "safety-and-crisis":
        if _signals_self_harm_crisis(input_data, signals):
            route["mustDo"] = unique_items(
                [
                    "use_fixed_english_self_harm_crisis_template",
                    *route["mustDo"],
                ]
            )
        confirmed_immediate_danger = (
            "direct_to_local_emergency_services_or_hotline_now" in route["mustDo"]
        )
        fixed_self_harm_template = (
            "use_fixed_english_self_harm_crisis_template" in route["mustDo"]
        )
        route["secondarySkills"] = []
        route["responseMode"] = "crisis"
        route["safety"] = {
            "ordinaryChatSuspended": True,
            "requiresRealitySupport": True,
            "askRiskQuestions": True,
            "crisisResourceNeeded": True,
            "hardLocked": True,
        }
        route["toneConstraints"] = get_default_tone_for_skill(
            "safety-and-crisis", signals
        )
        route["mustDo"] = unique_items(
            [
                *route["mustDo"],
                "directly_acknowledge_risk",
                *(
                    []
                    if confirmed_immediate_danger
                    or fixed_self_harm_template
                    else [
                        "ask_immediate_danger_without_naming_methods",
                        "ask_whether_someone_safe_can_be_nearby",
                    ]
                ),
                "encourage_immediate_real_world_support",
                "use_calm_non_punitive_language",
                "keep_response_short_and_action_oriented",
            ]
        )
        route["mustNotDo"] = unique_items(
            [
                *route["mustNotDo"],
                "ordinary_friend_chat",
                "playful_tone",
                "deep_analysis",
                "ask_about_specific_harm_tools",
                "name_knives_blades_pills_roofs_or_other_methods",
                "promise_secrecy",
                "say_ai_is_enough",
                "reinforce_exclusive_attachment",
                "harsh_commanding_tone",
                "behavioral_control_steps_beyond_real_world_support",
            ]
        )

    if route["dependencyRisk"] in ("medium", "high"):
        route["mustNotDo"] = unique_items(
            [
                *route["mustNotDo"],
                "say_only_i_understand_you",
                "say_you_only_need_me",
                "promise_permanent_exclusive_presence",
                "reinforce_exclusive_attachment",
            ]
        )

    if route["primarySkill"] == "agency-next-step":
        route["mustDo"] = unique_items([*route["mustDo"], "preserve_user_agency"])
        route["mustNotDo"] = unique_items([*route["mustNotDo"], "decide_for_user"])

    if route["primarySkill"] == "vent-container":
        route["mustNotDo"] = unique_items(
            [*route["mustNotDo"], "feed_more_speculation", "encourage_revenge"]
        )

    if route["primarySkill"] == "rupture-repair":
        route["mustNotDo"] = unique_items(
            [
                *route["mustNotDo"],
                "explain_system_limitations_first",
                "reflexively_say_you_are_right",
                "over_apologize",
            ]
        )

    if route["primarySkill"] == "active-celebration":
        route["mustNotDo"] = unique_items(
            [*route["mustNotDo"], "clinical_analysis", "minimize_success"]
        )

    route["secondarySkills"] = route["secondarySkills"][:2]
    route["toneConstraints"]["clinicalLanguageAllowed"] = False
    if signals["entryType"] == "casual":
        route["toneConstraints"]["analysisDepth"] = (
            "none"
            if route["primarySkill"] == "ambient-presence"
            else route["toneConstraints"]["analysisDepth"]
        )
        route["mustNotDo"] = unique_items(
            [
                *route["mustNotDo"],
                "force_self_exploration",
                "use_clinical_language",
                "repeat_i_am_here_reassurance",
                "introduce_sudden_internet_slang",
            ]
        )

    return route
