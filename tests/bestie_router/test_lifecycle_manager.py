from __future__ import annotations

from bestie_router import route_bestie_turn


def test_light_connection_transition() -> None:
    route = route_bestie_turn({"userMessage": "好无聊，陪我聊会儿"})
    assert route["lifecycle"]["currentState"] == "light-connection"


def test_emotional_opening_transition() -> None:
    route = route_bestie_turn({"userMessage": "她们没叫我，我好委屈"})
    assert route["lifecycle"]["currentState"] == "emotional-opening"


def test_high_arousal_transition() -> None:
    route = route_bestie_turn({"userMessage": "我心慌得想吐"})
    assert route["lifecycle"]["currentState"] == "high-arousal"


def test_safety_crisis_lock() -> None:
    route = route_bestie_turn(
        {"userMessage": "我今天吃饭了", "activeState": "safety-crisis"}
    )
    assert route["primarySkill"] == "safety-and-crisis"
    assert route["lifecycle"]["currentState"] == "safety-crisis"


def test_repair_state_stable_next_skill() -> None:
    route = route_bestie_turn({"userMessage": "你没懂我"})
    assert route["lifecycle"]["currentState"] == "relationship-repair"
    assert route["lifecycle"]["nextSkillIfStable"] == "responsive-listening"


def test_repeated_rumination_moves_to_meaning_making() -> None:
    route = route_bestie_turn(
        {
            "userMessage": "所以他到底什么意思？",
            "conversationHistory": [
                {"role": "user", "content": "他到底什么意思？"},
                {"role": "user", "content": "可是他到底什么意思？"},
                {"role": "user", "content": "你说他到底什么意思？"},
            ],
        }
    )
    assert route["lifecycle"]["currentState"] == "meaning-making"
    assert "gently_name_loop" in route["mustDo"]
