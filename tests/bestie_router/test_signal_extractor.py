from __future__ import annotations

from bestie_router import extract_signals


def test_extracts_risk_keywords() -> None:
    signals = extract_signals({"userMessage": "我不想活了"})
    assert signals["entryType"] == "crisis"
    assert signals["riskLevel"] in ("medium", "high")
    assert signals["hasImmediateSafetyConcern"] is True
    assert signals["emotionIntensity"] == 4


def test_extracts_high_arousal() -> None:
    signals = extract_signals({"userMessage": "他没回我，我心慌得想吐"})
    assert signals["hasHighArousal"] is True
    assert signals["emotionIntensity"] == 3
    assert "心慌" in signals["arousalSignals"]


def test_extracts_agent_rupture() -> None:
    signals = extract_signals({"userMessage": "你没懂我"})
    assert signals["hasAgentFeedback"] is True
    assert signals["entryType"] == "agent-rupture"


def test_extracts_dependency() -> None:
    signals = extract_signals({"userMessage": "只有你最懂我，我以后只跟你说"})
    assert signals["dependencyRisk"] == "high"
    assert signals["asksForOnlyAiSupport"] is True
    assert signals["entryType"] == "dependency"


def test_extracts_joyful_playful_action_cognitive_memory() -> None:
    joyful = extract_signals({"userMessage": "我拿到 offer 了！！！"})
    assert joyful["entryType"] == "joyful"

    playful = extract_signals({"userMessage": "我真的会谢，帮我写朋友圈文案"})
    assert playful["entryType"] == "playful"
    assert playful["asksForMessageDraft"] is True

    action = extract_signals({"userMessage": "我该怎么回他？"})
    assert action["entryType"] == "action-request"
    assert action["asksForAdvice"] is True

    cognitive = extract_signals({"userMessage": "他肯定不爱我了"})
    assert "他肯定" in cognitive["cognitiveDistortionSignals"]

    memory = extract_signals({"userMessage": "你还记得我之前说过的朋友吗"})
    assert memory["memorySignals"]


def test_latest_no_advice_or_advice_wins() -> None:
    no_advice = extract_signals({"userMessage": "怎么办？算了别给建议，我只是想说说"})
    assert no_advice["asksForNoAdvice"] is True
    assert no_advice["asksForAdvice"] is False

    advice = extract_signals({"userMessage": "不想听建议，但你说我该怎么办？"})
    assert advice["asksForAdvice"] is True
    assert advice["asksForNoAdvice"] is False


def test_repetition_count_uses_history() -> None:
    signals = extract_signals(
        {
            "userMessage": "所以他到底什么意思？",
            "conversationHistory": [
                {"role": "user", "content": "他到底什么意思？"},
                {"role": "assistant", "content": "先分事实和猜测。"},
                {"role": "user", "content": "可是他到底什么意思？"},
                {"role": "user", "content": "你说他到底什么意思？"},
            ],
        }
    )
    assert signals["repetitionCount"] == 4
    assert signals["entryType"] == "pattern"
