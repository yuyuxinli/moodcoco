from __future__ import annotations

from bestie_router import SkillPolicyRouter, extract_signals, route_bestie_turn


def _route(message: str, history: list[dict[str, str]] | None = None):
    input_data = {"userMessage": message}
    if history is not None:
        input_data["conversationHistory"] = history  # type: ignore[typeddict-unknown-key]
    signals = extract_signals(input_data)  # type: ignore[arg-type]
    return SkillPolicyRouter().route(input_data, signals)  # type: ignore[arg-type]


def test_casual_to_ambient_presence() -> None:
    assert _route("好无聊，陪我聊会儿")["primarySkill"] == "ambient-presence"


def test_joyful_to_active_celebration() -> None:
    route = _route("我拿到 offer 了！！！")
    assert route["primarySkill"] == "active-celebration"
    assert "celebrate_first" in route["mustDo"]


def test_playful_to_playful_attunement() -> None:
    route = _route("帮我写个朋友圈文案，轻轻炫一下")
    assert route["primarySkill"] == "playful-attunement"


def test_shame_mixed_emotion_to_emotion_labeling() -> None:
    route = _route("我嫉妒到难受，我是不是很坏？")
    assert route["primarySkill"] == "emotion-labeling"


def test_relationship_hurt_to_responsive_listening() -> None:
    route = _route("她们出去玩没叫我，我是不是多余的？")
    assert route["primarySkill"] == "responsive-listening"


def test_family_conflict_to_responsive_listening() -> None:
    route = _route("我跟我妈吵架，她不愿意出学费，让我们自己赚")
    assert route["primarySkill"] == "responsive-listening"


def test_appearance_insecurity_to_responsive_listening() -> None:
    route = _route("我不知道，只是我们外表差太多了，不是俊男靓女")
    assert route["primarySkill"] == "responsive-listening"


def test_mind_reading_to_reality_soft_check() -> None:
    route = _route("他肯定不爱我了")
    assert route["primarySkill"] == "reality-soft-check"


def test_advice_to_agency_next_step() -> None:
    route = _route("我该怎么办？")
    assert route["primarySkill"] == "agency-next-step"


def test_message_drafting_to_social_bridge() -> None:
    route = _route("帮我写一句拒绝她的消息，别太伤人")
    assert route["primarySkill"] == "social-bridge"


def test_identity_question_to_identity_mirror() -> None:
    route = _route("我不知道我到底想要什么")
    assert route["primarySkill"] == "identity-mirror"


def test_repeated_pattern_to_pattern_witness() -> None:
    route = _route("我为什么总是在关系里这样？")
    assert route["primarySkill"] == "pattern-witness"


def test_memory_delete_request_stays_memory_without_commentary() -> None:
    route = _route("这件事别记。")
    assert route["primarySkill"] == "relationship-memory"
    assert "respect_memory_governance" in route["mustDo"]
    assert "automatic_sensitive_persistence" in route["mustNotDo"]


def test_romantic_ai_boundary_to_social_bridge() -> None:
    route = route_bestie_turn({"userMessage": "那你爱我吗"})
    assert route["primarySkill"] == "social-bridge"
    assert route["dependencyRisk"] in {"medium", "high"}
