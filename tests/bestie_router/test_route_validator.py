from __future__ import annotations

from bestie_router import extract_signals, validate_route
from bestie_router.route_builder import build_route


def _signals(message: str):
    return extract_signals({"userMessage": message})


def test_fixes_too_many_secondary_skills() -> None:
    input_data = {"userMessage": "好无聊"}
    signals = _signals("好无聊")
    route = build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="ambient-presence",
        secondary_skills=[
            "responsive-listening",
            "emotion-labeling",
            "agency-next-step",
        ],
        route_reason="test",
        confidence=0.5,
    )
    fixed = validate_route(route, input_data, signals)
    assert len(fixed["secondarySkills"]) == 2


def test_repairs_raw_invalid_route_before_pydantic_validation() -> None:
    input_data = {"userMessage": "好无聊"}
    signals = _signals("好无聊")
    raw_route = {
        "routeVersion": "test",
        "riskLevel": "none",
        "dependencyRisk": "none",
        "emotionIntensity": 0,
        "dominantUserNeed": "companionship",
        "primarySkill": "not-a-real-skill",
        "secondarySkills": [
            "responsive-listening",
            "emotion-labeling",
            "agency-next-step",
            "not-a-real-skill",
        ],
        "responseMode": "bestie-short",
        "toneConstraints": {
            "warmth": "high",
            "playfulness": "medium",
            "analysisDepth": "none",
            "directiveLevel": "low",
            "clinicalLanguageAllowed": False,
            "bestieToneRequired": False,
        },
        "mustDo": [],
        "mustNotDo": [],
        "memoryAction": "none",
        "lifecycle": {
            "currentState": "unknown",
            "enterReason": "test",
            "exitConditionToCheck": "test",
        },
        "safety": {
            "ordinaryChatSuspended": False,
            "requiresRealitySupport": False,
            "askRiskQuestions": False,
            "crisisResourceNeeded": False,
            "hardLocked": False,
        },
        "routeReason": "raw invalid route",
        "confidence": 0.4,
    }
    fixed = validate_route(raw_route, input_data, signals)
    assert fixed["primarySkill"] == "ambient-presence"
    assert fixed["secondarySkills"] == ["responsive-listening", "emotion-labeling"]


def test_safety_primary_has_no_secondary_and_crisis_tone() -> None:
    input_data = {"userMessage": "我不想活了"}
    signals = _signals("我不想活了")
    route = build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="safety-and-crisis",
        secondary_skills=["responsive-listening"],
        route_reason="test",
        confidence=0.5,
    )
    fixed = validate_route(route, input_data, signals)
    assert fixed["secondarySkills"] == []
    assert fixed["responseMode"] == "crisis"
    assert fixed["toneConstraints"]["playfulness"] == "none"
    assert "use_fixed_english_self_harm_crisis_template" in fixed["mustDo"]
    assert "ask_immediate_danger_without_naming_methods" not in fixed["mustDo"]


def test_high_arousal_cannot_route_to_identity_mirror() -> None:
    input_data = {"userMessage": "我心慌得想吐，我是谁都不知道了"}
    signals = _signals(input_data["userMessage"])
    route = build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="identity-mirror",
        route_reason="test",
        confidence=0.5,
    )
    fixed = validate_route(route, input_data, signals)
    assert fixed["primarySkill"] == "ground-and-regulate"
    assert "screen_acute_body_danger_before_grounding" in fixed["mustDo"]


def test_dependency_cannot_produce_exclusive_language() -> None:
    input_data = {"userMessage": "只有你最懂我，我以后只跟你说"}
    signals = _signals(input_data["userMessage"])
    route = build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="responsive-listening",
        route_reason="test",
        confidence=0.5,
    )
    fixed = validate_route(route, input_data, signals)
    assert fixed["primarySkill"] == "social-bridge"
    assert "reinforce_exclusive_attachment" in fixed["mustNotDo"]


def test_joyful_cannot_be_taskified() -> None:
    input_data = {"userMessage": "我拿到 offer 了！！！"}
    signals = _signals(input_data["userMessage"])
    route = build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="agency-next-step",
        route_reason="test",
        confidence=0.5,
    )
    fixed = validate_route(route, input_data, signals)
    assert fixed["primarySkill"] == "active-celebration"


def test_forbidden_safety_transition_is_represented_after_validation() -> None:
    input_data = {"userMessage": "我已经想好怎么做了"}
    signals = _signals(input_data["userMessage"])
    route = build_route(
        input_data=input_data,
        signals=signals,
        primary_skill="playful-attunement",
        route_reason="test",
        confidence=0.5,
    )
    fixed = validate_route(route, input_data, signals)
    assert fixed["primarySkill"] == "safety-and-crisis"
    assert "playful_tone" in fixed["mustNotDo"]
    assert "harsh_commanding_tone" in fixed["mustNotDo"]
