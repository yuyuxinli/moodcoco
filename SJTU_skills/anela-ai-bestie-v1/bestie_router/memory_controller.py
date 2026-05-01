"""Memory action policy for route cards.

This module only decides memory intent. It does not read or write a database.
"""

from __future__ import annotations

from .route_builder import unique_items
from .types import (
    ExtractedSignals,
    MemoryAction,
    MemoryTarget,
    RouteCard,
    RouterInput,
    ensure_route_card,
    ensure_router_input,
    ensure_signals,
)


def _lower(input_data: RouterInput) -> str:
    return input_data["userMessage"].lower()


def _target(
    *,
    target_type: str,
    content: str,
    sensitivity: str,
    authorization: bool,
    recall: bool,
    reason: str,
) -> MemoryTarget:
    return MemoryTarget.model_validate(
        {
            "type": target_type,
            "content": content,
            "sensitivity": sensitivity,
            "authorizationRequired": authorization,
            "canProactivelyRecall": recall,
            "reason": reason,
        }
    )


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_recalled_memory_context(input_data: RouterInput) -> bool:
    memory_context = input_data.get("memoryContext")
    if memory_context is None:
        return False
    return bool(memory_context.get("visibleFacts", []))


def _decide_memory(
    input_data: RouterInput, signals: ExtractedSignals, route: RouteCard
) -> tuple[MemoryAction, list[MemoryTarget], list[str], list[str]]:
    text = _lower(input_data)
    content = input_data["userMessage"]

    if route["primarySkill"] == "safety-and-crisis":
        return "none", [], [], ["store_crisis_details_without_explicit_policy"]

    if _has_any(text, ("别记", "忘掉", "删掉", "don't save", "dont save", "forget", "delete")):
        return (
            "delete",
            [
                _target(
                    target_type="sensitive",
                    content=content,
                    sensitivity="high",
                    authorization=True,
                    recall=False,
                    reason="User requested forgetting, deletion, or non-storage.",
                )
            ],
            ["confirm_memory_deletion"],
            ["ask_why_delete_memory"],
        )

    explicit_memory_correction = _has_any(
        text,
        (
            "你记错了",
            "你记错",
            "记错了",
            "you remembered wrong",
            "you got it wrong",
        ),
    )
    contextual_memory_correction = _has_recalled_memory_context(input_data) and _has_any(
        text, ("不是", "不对", "actually", "not ")
    )
    if explicit_memory_correction or contextual_memory_correction:
        return (
            "update",
            [
                _target(
                    target_type="relationship",
                    content=content,
                    sensitivity="medium",
                    authorization=False,
                    recall=True,
                    reason="User corrected a remembered fact.",
                )
            ],
            ["acknowledge_memory_correction", "allow_correction_or_deletion"],
            ["defend_wrong_memory", "claim_uncertain_memory_as_fact"],
        )

    if _has_any(
        text,
        (
            "你还记得吗",
            "你还记得",
            "上次那个",
            "我之前说过",
            "我之前说的",
            "和以前一样",
            "又来了",
            "remember",
            "last time",
            "i told you before",
        ),
    ):
        return "read", [], ["do_not_invent_memory"], ["pretend_memory_exists"]

    sensitive_terms = (
        "创伤",
        "性取向",
        "精神",
        "自伤",
        "不想活",
        "家暴",
        "性侵",
        "trauma",
        "sexuality",
        "self harm",
        "suicide",
        "abuse",
    )
    if _has_any(text, sensitive_terms):
        return (
            "ask-authorization",
            [
                _target(
                    target_type="sensitive",
                    content=content,
                    sensitivity="high",
                    authorization=True,
                    recall=False,
                    reason="High-sensitivity personal content must not be stored by default.",
                )
            ],
            ["ask_memory_authorization_before_write"],
            ["default_store_sensitive_memory"],
        )

    preference_terms = (
        "称呼",
        "语气",
        "我喜欢你",
        "我不喜欢你",
        "以后可以这样",
        "call me",
        "tone",
        "i like it when you",
    )
    if _has_any(text, preference_terms):
        return (
            "write-candidate",
            [
                _target(
                    target_type="preference",
                    content=content,
                    sensitivity="low",
                    authorization=False,
                    recall=True,
                    reason="Low-sensitivity communication preference.",
                )
            ],
            ["allow_correction_or_deletion"],
            ["hide_memory_write"],
        )

    milestone_terms = (
        "offer",
        "我过了",
        "通过了",
        "生日",
        "面试",
        "我做到了",
        "拿到了",
        "got the offer",
        "i passed",
        "i did it",
        "birthday",
    )
    if _has_any(text, milestone_terms):
        return (
            "write-candidate",
            [
                _target(
                    target_type="milestone",
                    content=content,
                    sensitivity="low",
                    authorization=False,
                    recall=True,
                    reason="User shared a positive milestone or small win.",
                )
            ],
            ["allow_correction_or_deletion"],
            ["minimize_success"],
        )

    if "记一下" in text or "remember this" in text:
        relationship_or_goal_terms = (
            "朋友",
            "暧昧",
            "室友",
            "考研",
            "求职",
            "目标",
            "friend",
            "crush",
            "goal",
            "job search",
        )
        if _has_any(text, relationship_or_goal_terms):
            return (
                "ask-authorization",
                [
                    _target(
                        target_type="relationship",
                        content=content,
                        sensitivity="medium",
                        authorization=True,
                        recall=True,
                        reason="Relationship or goal memory should be user-authorized.",
                    )
                ],
                ["ask_memory_authorization_before_write"],
                ["automatic_relationship_memory_write"],
            )
        return (
            "write-candidate",
            [
                _target(
                    target_type="preference",
                    content=content,
                    sensitivity="low",
                    authorization=False,
                    recall=True,
                    reason="User explicitly asked to remember low-sensitivity content.",
                )
            ],
            ["allow_correction_or_deletion"],
            ["hide_memory_write"],
        )

    return "none", [], [], []


def apply_memory_decision(
    route: RouteCard, input_data: RouterInput, signals: ExtractedSignals
) -> RouteCard:
    route = ensure_route_card(route)
    input_data = ensure_router_input(input_data)
    signals = ensure_signals(signals)
    action, targets, must_do, must_not_do = _decide_memory(input_data, signals, route)
    route["memoryAction"] = action
    if targets:
        route["memoryTargets"] = targets
    elif "memoryTargets" in route:
        del route["memoryTargets"]
    route["mustDo"] = unique_items([*route["mustDo"], *must_do])
    route["mustNotDo"] = unique_items([*route["mustNotDo"], *must_not_do])

    if action in ("write-candidate", "ask-authorization", "update", "delete"):
        route["secondarySkills"] = [
            skill
            for skill in [*route["secondarySkills"], "relationship-memory"]
            if skill != route["primarySkill"]
        ][:2]
    return route
