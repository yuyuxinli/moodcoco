from __future__ import annotations

from bestie_router import SkillPolicyRouter, apply_memory_decision, extract_signals


def _route_with_memory(message: str):
    input_data = {"userMessage": message}
    signals = extract_signals(input_data)
    route = SkillPolicyRouter().route(input_data, signals)
    return apply_memory_decision(route, input_data, signals)


def test_memory_read() -> None:
    route = _route_with_memory("你还记得我之前说的那个朋友吗？")
    assert route["memoryAction"] == "read"


def test_memory_write_candidate_low_sensitivity() -> None:
    route = _route_with_memory("这个称呼我喜欢，你以后可以这样叫我。")
    assert route["memoryAction"] == "write-candidate"
    assert route["memoryTargets"][0]["type"] == "preference"
    assert route["memoryTargets"][0]["authorizationRequired"] is False


def test_memory_ask_authorization_high_sensitivity() -> None:
    route = _route_with_memory("这段创伤史记一下，但别随便提。")
    assert route["memoryAction"] == "ask-authorization"
    assert route["memoryTargets"][0]["sensitivity"] == "high"


def test_memory_update() -> None:
    route = _route_with_memory("你记错了，不是小林，是小陈。")
    assert route["memoryAction"] == "update"


def test_memory_not_every_not_statement_becomes_update() -> None:
    route = _route_with_memory("记一下，我不是本地人。")
    assert route["memoryAction"] == "write-candidate"


def test_memory_context_allows_contextual_update() -> None:
    input_data = {
        "userMessage": "不是小林，是小陈。",
        "memoryContext": {"visibleFacts": ["暧昧对象叫小林"]},
    }
    signals = extract_signals(input_data)
    route = SkillPolicyRouter().route(input_data, signals)
    route = apply_memory_decision(route, input_data, signals)
    assert route["memoryAction"] == "update"


def test_memory_delete() -> None:
    route = _route_with_memory("忘掉我刚才说的。")
    assert route["memoryAction"] == "delete"
    assert "ask_why_delete_memory" in route["mustNotDo"]


def test_memory_none() -> None:
    route = _route_with_memory("好无聊，陪我聊会儿。")
    assert route["memoryAction"] == "none"
