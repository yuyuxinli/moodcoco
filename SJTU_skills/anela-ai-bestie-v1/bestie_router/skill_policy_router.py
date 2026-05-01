"""Deterministic skill policy router for non-hard-gated turns."""

from __future__ import annotations

from .constants import JOY_SELF_DOUBT_PHRASES
from .route_builder import build_route
from .types import (
    ExtractedSignals,
    RouteCard,
    RouterInput,
    SoftRouteSuggestion,
    SkillName,
    ensure_router_input,
    ensure_signals,
    ensure_soft_suggestion,
)

SOFT_PRIMARY_BLOCKLIST: set[SkillName] = {
    "safety-and-crisis",
    "rupture-repair",
    "ground-and-regulate",
}


def _lower(input_data: RouterInput) -> str:
    return input_data["userMessage"].lower()


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase.lower() in text for phrase in phrases)


def _is_pure_memory_request(signals: ExtractedSignals, text: str) -> bool:
    if not signals["memorySignals"]:
        return False
    governance = any(
        phrase in text
        for phrase in (
            "记一下",
            "别记",
            "忘掉",
            "删掉",
            "你还记得",
            "上次那个",
            "之前说过",
            "remember",
            "forget",
            "delete",
            "don't save",
            "dont save",
        )
    )
    return governance and signals["entryType"] not in (
        "crisis",
        "agent-rupture",
        "dependency",
        "pattern",
    )


class SkillPolicyRouter:
    """Rule-first policy router. LLM suggestions are intentionally non-authoritative."""

    def route(
        self,
        input_data: RouterInput,
        signals: ExtractedSignals,
        soft_suggestion: SoftRouteSuggestion | dict[str, object] | None = None,
    ) -> RouteCard:
        input_data = ensure_router_input(input_data)
        signals = ensure_signals(signals)
        route = self._route_by_rules(input_data, signals)
        return self._merge_soft_suggestion(
            route, input_data, signals, ensure_soft_suggestion(soft_suggestion)
        )

    def _route_by_rules(
        self, input_data: RouterInput, signals: ExtractedSignals
    ) -> RouteCard:
        text = _lower(input_data)

        if _is_pure_memory_request(signals, text):
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="relationship-memory",
                secondary_skills=[],
                dominant_need="companionship",
                must_do=[
                    "respect_memory_governance",
                    "do_not_invent_memory",
                    "make_memory_scope_visible",
                ],
                must_not_do=[
                    "automatic_sensitive_persistence",
                    "claim_memory_without_retrieval",
                ],
                route_reason="Explicit memory governance or recall request.",
                confidence=0.88,
            )

        repetition_count = signals.get("repetitionCount", 1)
        if repetition_count >= 4:
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="reality-soft-check",
                secondary_skills=["vent-container", "ground-and-regulate"],
                dominant_need="clarity",
                must_do=[
                    "gently_name_loop",
                    "protect_user_from_more_speculation",
                    "offer_body_reset_or_one_action_or_rest",
                    "validate_before_checking_reality",
                    "separate_fact_feeling_guess",
                    "avoid_mind_reading",
                ],
                must_not_do=[
                    "generate_more_mind_reading",
                    "shame_user_for_ruminating",
                    "feed_more_speculation",
                ],
                route_reason="Repeated same-event rumination detected across turns.",
                confidence=0.9,
            )

        if signals["entryType"] == "joyful":
            secondaries = []
            if any(
                phrase.lower() in text for phrase in JOY_SELF_DOUBT_PHRASES
            ) or any(token in text for token in ("不敢开心", "只是运气", "但我又")):
                secondaries.append("responsive-listening")
            if any(token in text for token in ("offer", "过了", "生日", "面试", "拿到")):
                secondaries.append("relationship-memory")
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="active-celebration",
                secondary_skills=secondaries,
                dominant_need="celebration",
                must_do=[
                    "celebrate_first",
                    "be_specific_about_event_meaning",
                    "help_user_savor",
                    "connect_to_effort_without_overanalysis",
                ],
                must_not_do=[
                    "immediately_plan_next_step",
                    "minimize_success",
                    "clinical_analysis",
                ],
                route_reason="Joyful or milestone share should be celebrated first.",
                confidence=0.89,
            )

        if signals["entryType"] == "playful":
            secondaries = []
            if any(token in text for token in ("骂", "吐槽", "rant", "roast", "室友")):
                secondaries.append("vent-container")
            if any(token in text for token in ("委屈", "难受", "hurt", "upset")):
                secondaries.append("responsive-listening")
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="playful-attunement",
                secondary_skills=secondaries,
                dominant_need="companionship",
                must_do=[
                    "mirror_style_lightly",
                    "keep_boundary_on_attack",
                    "co_create_expression_if_asked",
                ],
                must_not_do=[
                    "use_jokes_in_crisis",
                    "escalate_insults",
                    "output_threats_or_manipulation",
                ],
                route_reason="Playful language or co-creation request without higher risk.",
                confidence=0.86,
            )

        if signals["cognitiveDistortionSignals"]:
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="reality-soft-check",
                secondary_skills=["responsive-listening", "agency-next-step"],
                dominant_need="clarity",
                must_do=[
                    "validate_before_checking_reality",
                    "separate_fact_feeling_guess",
                    "avoid_mind_reading",
                    "offer_small_confirmable_next_step",
                    "validate_first",
                    "separate_known_unknown_guess",
                    "offer_confirmable_next_step",
                ],
                must_not_do=[
                    "say_you_are_overthinking",
                    "confirm_other_person_bad_intent",
                    "feed_more_speculation",
                    "encourage_revenge",
                    "confirm_other_person_motive",
                    "argue",
                    "confirm_external_motive",
                ],
                route_reason="Mind-reading or catastrophizing needs gentle reality checking.",
                confidence=0.87,
            )

        if signals.get("asksForNoAdvice") or signals["entryType"] == "negative-emotion":
            shame_or_mixed = any(
                token in text
                for token in (
                    "说不上来",
                    "乱",
                    "是不是很坏",
                    "是不是太敏感",
                    "嫉妒",
                    "羞耻",
                    "overreacting",
                    "jealous",
                    "ashamed",
                )
            )
            primary = "emotion-labeling" if shame_or_mixed else "responsive-listening"
            secondary = ["responsive-listening"] if primary == "emotion-labeling" else [
                "emotion-labeling"
            ]
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill=primary,
                secondary_skills=secondary,
                dominant_need="validation",
                must_do=[
                    "validate_specific_experience",
                    "use_user_language",
                    "reduce_shame",
                    "leave_space_to_continue",
                    "not_confirm_external_motive",
                ],
                must_not_do=[
                    "generic_empathy",
                    "premature_advice",
                    "confirm_external_motive",
                    "diagnose_user",
                    "generic_comfort",
                    "premature_solution",
                    "diagnose",
                ],
                route_reason=(
                    "Mixed or shame-heavy emotion needs labeling."
                    if shame_or_mixed
                    else "User needs validation before any solution."
                ),
                confidence=0.85,
            )

        if signals["entryType"] == "action-request":
            relationship_expression = signals.get("asksForMessageDraft") or any(
                token in text
                for token in (
                    "拒绝",
                    "开口",
                    "发消息",
                    "怎么回",
                    "沟通",
                    "message",
                    "reply",
                    "say no",
                )
            )
            primary = "social-bridge" if relationship_expression else "agency-next-step"
            secondary = []
            if signals["cognitiveDistortionSignals"]:
                secondary.append("reality-soft-check")
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill=primary,
                secondary_skills=secondary,
                dominant_need="action",
                must_do=[
                    "preserve_user_agency",
                    "show_options_and_tradeoffs",
                    "create_small_next_step",
                    "include_low_risk_draft_if_needed",
                    "preserve_choice",
                    "options_and_tradeoffs",
                    "smallest_next_step",
                ],
                must_not_do=[
                    "decide_for_user",
                    "command_user",
                    "guarantee_outcome",
                    "encourage_manipulation",
                    "guarantee_result",
                    "manipulate_others",
                ],
                route_reason="User asks for action support while still keeping agency.",
                confidence=0.84,
            )

        if signals["entryType"] in ("self-exploration", "pattern"):
            wants_change = any(token in text for token in ("改变", "怎么办", "change"))
            primary = (
                "pattern-witness"
                if signals["entryType"] == "pattern"
                or any(token in text for token in ("总是", "每次", "又来了", "again"))
                else "identity-mirror"
            )
            secondaries = ["responsive-listening"]
            if wants_change:
                secondaries.append("agency-next-step")
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill=primary,
                secondary_skills=secondaries,
                dominant_need="identity",
                must_do=[
                    "use_light_hypotheses",
                    "avoid_labels",
                    "connect_to_values",
                ],
                must_not_do=[
                    "diagnose_personality",
                    "overgeneralize_from_single_event",
                ],
                route_reason="Self-exploration or repeated pattern needs reflective support.",
                confidence=0.82,
            )

        if "乱" in text or "messy" in text or "confused" in text:
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="collaborative-untangling",
                secondary_skills=["responsive-listening"],
                dominant_need="clarity",
                must_do=[
                    "validate_before_structuring",
                    "separate_event_feeling_need_next_step",
                    "keep_hypotheses_light",
                ],
                must_not_do=[
                    "over_structure_too_early",
                    "diagnose_user",
                    "turn_into_interrogation",
                ],
                route_reason="User is willing to organize a messy issue.",
                confidence=0.78,
            )

        if signals["entryType"] == "casual" or signals["entryType"] == "unknown":
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill="ambient-presence",
                secondary_skills=[],
                dominant_need="companionship",
                must_do=[
                    "low_pressure_presence",
                    "offer_light_options",
                    "avoid_forced_depth",
                    "avoid_over_psychologizing",
                    "match_light_tone",
                    "keep_low_pressure",
                ],
                must_not_do=[
                    "pathologize_boredom",
                    "interrogate_user",
                    "force_self_exploration",
                    "turn_everything_into_therapy",
                    "use_clinical_language",
                ],
                route_reason="Casual low-pressure entry with no stronger signal.",
                confidence=0.8,
            )

        return build_route(
            input_data=input_data,
            signals=signals,
            primary_skill="responsive-listening",
            secondary_skills=[],
            dominant_need="validation",
            must_do=["validate_specific_experience", "leave_space_to_continue"],
            must_not_do=["premature_advice", "diagnose_user"],
            route_reason="Fallback to responsive listening when signals are ambiguous.",
            confidence=0.62,
        )

    def _merge_soft_suggestion(
        self,
        route: RouteCard,
        input_data: RouterInput,
        signals: ExtractedSignals,
        suggestion: SoftRouteSuggestion | None,
    ) -> RouteCard:
        """Deterministically merge non-authoritative soft hints.

        Soft suggestions only influence low-confidence ambiguous routing or add
        harmless secondary hints. They never set P0-P2 hard primary skills, never
        bypass dependency policy, and never execute memory actions.
        """

        if suggestion is None or suggestion.confidence < 0.55:
            return route

        if suggestion.suggestedMemoryAction is not None:
            route["routeReason"] = (
                f"{route['routeReason']} Soft memory intent was observed but "
                "deferred to deterministic MemoryController."
            )

        suggested_primary = suggestion.primarySkill
        if suggested_primary in SOFT_PRIMARY_BLOCKLIST:
            route["routeReason"] = (
                f"{route['routeReason']} Soft primary suggestion "
                f"{suggested_primary} ignored because hard-gated skills are "
                "deterministic only."
            )
            return route

        if (
            suggested_primary == "social-bridge"
            and signals["dependencyRisk"] in ("medium", "high")
        ):
            route["routeReason"] = (
                f"{route['routeReason']} Soft social-bridge dependency suggestion "
                "ignored because dependency boundaries are deterministic."
            )
            return route

        ambiguous = signals["entryType"] == "unknown" or route["confidence"] <= 0.64
        if suggested_primary is not None and ambiguous:
            return build_route(
                input_data=input_data,
                signals=signals,
                primary_skill=suggested_primary,
                secondary_skills=suggestion.secondarySkills,
                dominant_need=suggestion.dominantUserNeed
                or route["dominantUserNeed"],
                must_do=[*route["mustDo"], "soft_suggestion_merged"],
                must_not_do=route["mustNotDo"],
                route_reason=(
                    f"{route['routeReason']} Soft suggestion merged after "
                    f"deterministic low-confidence route: {suggestion.routeReason or 'no reason'}."
                ),
                confidence=min(0.74, max(route["confidence"], suggestion.confidence * 0.8)),
            )

        merged_secondaries = [*route["secondarySkills"]]
        for skill in suggestion.secondarySkills:
            if skill != route["primarySkill"] and skill not in SOFT_PRIMARY_BLOCKLIST:
                merged_secondaries.append(skill)
        route["secondarySkills"] = list(dict.fromkeys(merged_secondaries))[:2]
        return route
