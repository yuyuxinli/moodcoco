from __future__ import annotations

from bestie_router import apply_safety_boundary_gate, extract_signals


def _gate(message: str):
    input_data = {"userMessage": message}
    return apply_safety_boundary_gate(input_data, extract_signals(input_data))


def _gate_with_context(message: str, context: dict):
    input_data = {"userMessage": message, **context}
    return apply_safety_boundary_gate(input_data, extract_signals(input_data))


def test_p0_safety_overrides_all() -> None:
    route = _gate("我拿到 offer 了但我不想活了")
    assert route is not None
    assert route["primarySkill"] == "safety-and-crisis"
    assert route["safety"]["hardLocked"] is True
    assert "use_fixed_english_self_harm_crisis_template" in route["mustDo"]
    assert "ask_immediate_danger_without_naming_methods" not in route["mustDo"]
    assert "ask_plan_means_time_aloneness" not in route["mustDo"]
    assert "name_knives_blades_pills_roofs_or_other_methods" in route["mustNotDo"]


def test_safety_edge_is_high_without_named_method() -> None:
    route = _gate("我觉得没人需要我，我真的撑不下去了")
    assert route is not None
    assert route["primarySkill"] == "safety-and-crisis"
    assert route["riskLevel"] == "high"


def test_confirmed_immediate_danger_directs_to_offline_help() -> None:
    route = _gate_with_context(
        "有，我怕我会控制不住",
        {
            "activeState": "safety-crisis",
            "safetyContext": {"activeSafetyLock": True},
        },
    )
    assert route is not None
    assert route["primarySkill"] == "safety-and-crisis"
    assert "direct_to_local_emergency_services_or_hotline_now" in route["mustDo"]
    assert "ask_user_to_contact_trusted_person_now" in route["mustDo"]
    assert "ask_immediate_danger_without_naming_methods" not in route["mustDo"]
    assert "ask_followup_about_plan_means_time_or_method" in route["mustNotDo"]


def test_safety_context_confirmed_immediate_danger_directs_to_offline_help() -> None:
    route = _gate_with_context(
        "我不知道怎么办",
        {
            "activeState": "safety-crisis",
            "safetyContext": {
                "activeSafetyLock": True,
                "hasConfirmedImmediateDanger": True,
            },
        },
    )
    assert route is not None
    assert "direct_to_local_emergency_services_or_hotline_now" in route["mustDo"]
    assert "continue_risk_interview_after_danger_confirmed" in route["mustNotDo"]


def test_p1_agent_rupture_overrides_ordinary_support() -> None:
    route = _gate("你没懂我")
    assert route is not None
    assert route["primarySkill"] == "rupture-repair"


def test_p2_high_arousal_overrides_cognitive_analysis() -> None:
    route = _gate("他肯定不爱我，我心慌得想吐")
    assert route is not None
    assert route["primarySkill"] == "ground-and-regulate"


def test_body_arousal_does_not_trigger_safety_questions() -> None:
    route = _gate("我哭得停不下来，手一直在抖")
    assert route is not None
    assert route["primarySkill"] == "ground-and-regulate"
    assert route["safety"]["askRiskQuestions"] is False


def test_p3_dependency_overrides_celebration() -> None:
    route = _gate("别人都没用，但我拿到 offer 了")
    assert route is not None
    assert route["primarySkill"] == "social-bridge"
    assert route["dependencyRisk"] == "high"


def test_no_gate_returns_none() -> None:
    assert _gate("好无聊，陪我聊会儿") is None
