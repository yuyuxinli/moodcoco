"""Route card builders shared by gates, policy router, and validator."""

from __future__ import annotations

from .constants import (
    DEFAULT_TONE_BY_SKILL,
    RESPONSE_MODE_BY_SKILL,
    ROUTE_VERSION,
)
from .types import (
    DependencyRisk,
    DominantNeed,
    EmotionIntensity,
    ExtractedSignals,
    ResponseMode,
    RiskLevel,
    RouteCard,
    RouterInput,
    SkillName,
    ToneConstraints,
    ensure_router_input,
    ensure_signals,
)


def unique_items(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def unique_skills(skills: list[SkillName]) -> list[SkillName]:
    return list(dict.fromkeys(skills))


def get_default_tone_for_skill(
    skill: SkillName, signals: ExtractedSignals | None = None
) -> ToneConstraints:
    tone = dict(DEFAULT_TONE_BY_SKILL[skill])
    if skill == "active-celebration" and signals:
        if signals["emotionIntensity"] >= 2 or "好开心" in signals["dominantEmotions"]:
            tone["playfulness"] = "high"
    if skill == "responsive-listening" and signals and signals["emotionIntensity"] >= 2:
        tone["playfulness"] = "none"
    if skill == "rupture-repair" and signals and signals.get("hasAgentFeedback"):
        tone["playfulness"] = "low"
    if skill == "safety-and-crisis":
        tone["playfulness"] = "none"
        tone["analysisDepth"] = "none"
        tone["directiveLevel"] = "high"
    return ToneConstraints.model_validate(tone)


def _default_safety(skill: SkillName, risk_level: RiskLevel) -> dict[str, bool]:
    is_safety = skill == "safety-and-crisis"
    return {
        "ordinaryChatSuspended": is_safety,
        "requiresRealitySupport": is_safety,
        "askRiskQuestions": is_safety,
        "crisisResourceNeeded": is_safety,
        "hardLocked": is_safety,
    }


def build_route(
    *,
    input_data: RouterInput,
    signals: ExtractedSignals,
    primary_skill: SkillName,
    secondary_skills: list[SkillName] | None = None,
    response_mode: ResponseMode | None = None,
    dominant_need: DominantNeed | None = None,
    risk_level: RiskLevel | None = None,
    dependency_risk: DependencyRisk | None = None,
    emotion_intensity: EmotionIntensity | None = None,
    must_do: list[str] | None = None,
    must_not_do: list[str] | None = None,
    route_reason: str,
    confidence: float,
) -> RouteCard:
    input_data = ensure_router_input(input_data)
    signals = ensure_signals(signals)
    secondaries = [
        skill
        for skill in unique_skills(secondary_skills or [])
        if skill != primary_skill
    ][:2]
    resolved_risk = risk_level or signals["riskLevel"]
    return RouteCard(
        routeVersion=ROUTE_VERSION,
        riskLevel=resolved_risk,
        dependencyRisk=dependency_risk or signals["dependencyRisk"],
        emotionIntensity=emotion_intensity or signals["emotionIntensity"],
        dominantUserNeed=dominant_need or signals["dominantNeed"],
        primarySkill=primary_skill,
        secondarySkills=secondaries,
        responseMode=response_mode or RESPONSE_MODE_BY_SKILL[primary_skill],
        toneConstraints=get_default_tone_for_skill(primary_skill, signals),
        mustDo=unique_items(must_do or []),
        mustNotDo=unique_items(must_not_do or []),
        memoryAction="none",
        lifecycle={
            "currentState": input_data.get("activeState", "unknown"),
            "enterReason": "Lifecycle not resolved yet.",
            "exitConditionToCheck": "Resolve lifecycle after route selection.",
        },
        safety=_default_safety(primary_skill, resolved_risk),
        routeReason=route_reason,
        confidence=max(0.0, min(1.0, confidence)),
    )


def build_safety_and_crisis_route(
    input_data: RouterInput, signals: ExtractedSignals, reason: str = "P0 safety gate."
) -> RouteCard:
    risk_level: RiskLevel = (
        "high"
        if signals["riskLevel"] == "high" or signals.get("hasImmediateSafetyConcern")
        else "medium"
    )
    return build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="safety-and-crisis",
        secondary_skills=[],
        response_mode="crisis",
        dominant_need="safety",
        risk_level=risk_level,
        emotion_intensity=4,
        must_do=[
            "directly_acknowledge_risk",
            "ask_immediate_danger_without_naming_methods",
            "ask_whether_someone_safe_can_be_nearby",
            "encourage_immediate_real_world_support",
            "keep_response_short_and_action_oriented",
        ],
        must_not_do=[
            "ordinary_bestie_chat",
            "playful_tone",
            "deep_analysis",
            "ask_about_specific_harm_tools",
            "name_knives_blades_pills_roofs_or_other_methods",
            "promise_secrecy",
            "say_ai_is_enough",
            "reinforce_exclusive_attachment",
        ],
        route_reason=reason,
        confidence=0.99,
    )


def build_rupture_repair_route(
    input_data: RouterInput, signals: ExtractedSignals, reason: str = "P1 repair gate."
) -> RouteCard:
    return build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="rupture-repair",
        secondary_skills=[],
        response_mode="repair",
        dominant_need="validation",
        emotion_intensity=signals["emotionIntensity"],
        must_do=[
            "stop_current_route",
            "acknowledge_mismatch",
            "avoid_defensiveness",
            "restate_user_feedback_briefly",
            "adjust_style_immediately",
        ],
        must_not_do=[
            "explain_system_limitations_first",
            "continue_original_advice",
            "over_apologize",
            "make_user_comfort_ai",
        ],
        route_reason=reason,
        confidence=0.94,
    )


def build_ground_and_regulate_route(
    input_data: RouterInput,
    signals: ExtractedSignals,
    reason: str = "P2 high-arousal gate.",
) -> RouteCard:
    return build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="ground-and-regulate",
        secondary_skills=["responsive-listening", "reality-soft-check"],
        response_mode="bestie-short",
        dominant_need="regulation",
        emotion_intensity=3,
        must_do=[
            "pause_analysis",
            "offer_one_short_body_action",
            "lower_goal_to_not_escalate",
            "prevent_impulsive_send_or_action",
        ],
        must_not_do=[
            "long_analysis",
            "tell_user_to_calm_down",
            "force_breathing_exercise",
            "over_questioning",
        ],
        route_reason=reason,
        confidence=0.93,
    )


def build_social_bridge_dependency_route(
    input_data: RouterInput,
    signals: ExtractedSignals,
    reason: str = "P3 dependency-boundary gate.",
) -> RouteCard:
    return build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="social-bridge",
        secondary_skills=["responsive-listening", "agency-next-step"],
        response_mode="structured",
        dominant_need=(
            "autonomy"
            if signals.get("asksForDecisionDelegation")
            else "social-connection"
        ),
        dependency_risk=(
            signals["dependencyRisk"]
            if signals["dependencyRisk"] in ("medium", "high")
            else "medium"
        ),
        must_do=[
            "validate_need_for_stable_support",
            "avoid_rejecting_user_coldly",
            "gently_de_exclusivize_ai",
            "encourage_one_small_real_world_support_or_self_action",
            "preserve_user_choice",
        ],
        must_not_do=[
            "say_only_i_understand_you",
            "say_you_only_need_me",
            "promise_permanent_exclusive_presence",
            "push_user_away_coldly",
            "decide_for_user",
            "reinforce_exclusive_attachment",
        ],
        route_reason=reason,
        confidence=0.92,
    )
