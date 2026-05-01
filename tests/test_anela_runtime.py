from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from backend import anela_runtime


def _route_card() -> dict:
    return {
        "routeVersion": "1.0",
        "riskLevel": "none",
        "dependencyRisk": "none",
        "emotionIntensity": 2,
        "dominantUserNeed": "validation",
        "primarySkill": "responsive-listening",
        "secondarySkills": ["active-celebration"],
        "responseMode": "bestie-medium",
        "mustDo": ["reflect the emotional center"],
        "mustNotDo": ["do not expose route JSON"],
        "memoryAction": "none",
        "routeReason": "user needs to be heard",
        "confidence": 0.91,
    }


class FakeAgent:
    instances: list[FakeAgent] = []

    def __init__(self, model, *, system_prompt: str, retries: int = 0):
        self.model = model
        self.system_prompt = system_prompt
        self.retries = retries
        self.run_prompts: list[str] = []
        FakeAgent.instances.append(self)

    async def run(self, user_prompt: str):
        self.run_prompts.append(user_prompt)
        return SimpleNamespace(output="我先陪你把这口气放下来。")


class ThinkingAgent(FakeAgent):
    async def run(self, user_prompt: str):
        self.run_prompts.append(user_prompt)
        return SimpleNamespace(
            output=(
                "Assistant: 思考中...\n"
                "<think>这里是内部分析，不该显示。</think>\n"
                "我在。我们先不用急着解释这件事。"
            )
        )


def test_run_anela_turn_routes_loads_prompts_and_uses_agent(monkeypatch):
    called: dict = {}

    def fake_route_bestie_turn(input_data, *, debug=False):
        called["input_data"] = input_data
        called["debug"] = debug
        return _route_card()

    import bestie_router

    monkeypatch.setattr(bestie_router, "route_bestie_turn", fake_route_bestie_turn)
    monkeypatch.setattr(anela_runtime, "Agent", FakeAgent)
    monkeypatch.setattr(anela_runtime, "create_agent_model", lambda: "fake-model")
    FakeAgent.instances.clear()

    result = asyncio.run(
        anela_runtime.run_anela_turn(
            "今天真的很委屈",
            history=[
                {"role": "user", "content": "我被朋友鸽了"},
                {"role": "assistant", "content": "听起来有点失落。"},
            ],
            context={"conversation_summary": "用户正在讲朋友失约。"},
            locale="zh-CN",
        )
    )

    assert called["debug"] is False
    assert called["input_data"]["userMessage"] == "今天真的很委屈"
    assert called["input_data"]["conversationHistory"][0]["content"] == "我被朋友鸽了"
    assert called["input_data"]["locale"] == "zh-CN"

    assert result.assistant_response == "我先陪你把这口气放下来。"
    assert result.route.primary_skill == "responsive-listening"
    assert result.route.secondary_skills == ["active-celebration"]
    assert result.route.route_reason == "user needs to be heard"
    assert result.tool_calls == []

    assert len(FakeAgent.instances) == 1
    prompt = FakeAgent.instances[0].system_prompt
    assert "AGENTS Template for Anela AI Bestie v1" in prompt
    assert "Anela AI Bestie v1 Routing Spec" in prompt
    assert "# Responsive Listening" in prompt
    assert "# Active Celebration" in prompt
    assert "CURRENT ROUTE GUIDANCE" in prompt
    assert "Do not expose route JSON" in prompt

    assert "AGENTS Template" not in result.assistant_response
    assert "CURRENT ROUTE GUIDANCE" not in result.assistant_response


def test_runtime_accepts_backend_history_aliases(monkeypatch):
    called: dict = {}

    def fake_route_bestie_turn(input_data, *, debug=False):
        called["input_data"] = input_data
        return _route_card()

    import bestie_router

    monkeypatch.setattr(bestie_router, "route_bestie_turn", fake_route_bestie_turn)
    monkeypatch.setattr(anela_runtime, "Agent", FakeAgent)
    monkeypatch.setattr(anela_runtime, "create_agent_model", lambda: "fake-model")
    FakeAgent.instances.clear()

    result = asyncio.run(
        anela_runtime.run_anela_turn(
            "继续说",
            history=[
                {"role": "persona", "text": "我被朋友鸽了"},
                {"role": "coco", "text": "听起来有点失落。"},
            ],
        )
    )

    assert result.assistant_response == "我先陪你把这口气放下来。"
    assert called["input_data"]["conversationHistory"] == [
        {"role": "user", "content": "我被朋友鸽了"},
        {"role": "assistant", "content": "听起来有点失落。"},
    ]
    user_prompt = FakeAgent.instances[0].run_prompts[0]
    assert "user: 我被朋友鸽了" in user_prompt
    assert "assistant: 听起来有点失落。" in user_prompt


def test_runtime_removes_thinking_markers_from_assistant_output(monkeypatch):
    def fake_route_bestie_turn(input_data, *, debug=False):
        return _route_card()

    import bestie_router

    monkeypatch.setattr(bestie_router, "route_bestie_turn", fake_route_bestie_turn)
    monkeypatch.setattr(anela_runtime, "Agent", ThinkingAgent)
    monkeypatch.setattr(anela_runtime, "create_agent_model", lambda: "fake-model")
    ThinkingAgent.instances.clear()

    result = asyncio.run(anela_runtime.run_anela_turn("我不知道怎么办"))

    assert result.assistant_response == "我在。我们先不用急着解释这件事。"
    assert "思考中" not in result.assistant_response
    assert "<think>" not in result.assistant_response


def test_runtime_sanitizes_generation_errors(monkeypatch):
    def fake_route_bestie_turn(input_data, *, debug=False):
        return _route_card()

    class FailingAgent(FakeAgent):
        async def run(self, user_prompt: str):
            raise RuntimeError(
                "MINIMAX_API_KEY=minimax-secret-123 Authorization: Bearer abcdefghijkl"
            )

    import bestie_router

    monkeypatch.setattr(bestie_router, "route_bestie_turn", fake_route_bestie_turn)
    monkeypatch.setattr(anela_runtime, "Agent", FailingAgent)
    monkeypatch.setattr(anela_runtime, "create_agent_model", lambda: "fake-model")

    with pytest.raises(anela_runtime.AnelaRuntimeError) as exc_info:
        asyncio.run(anela_runtime.run_anela_turn("hello"))

    message = str(exc_info.value)
    assert "minimax-secret-123" not in message
    assert "abcdefghijkl" not in message
    assert "MINIMAX_API_KEY=[REDACTED]" in message
    assert "Authorization: Bearer [REDACTED]" in message


def test_missing_anela_bundle_returns_clear_error(tmp_path):
    service = anela_runtime.AnelaRuntimeService(bundle_path=tmp_path / "missing-anela")

    with pytest.raises(anela_runtime.AnelaRuntimeError) as exc_info:
        asyncio.run(service.run_turn("hello"))

    message = str(exc_info.value)
    assert "Anela bundle not found" in message
    assert "SJTU_skills/anela-ai-bestie-v1" in message
