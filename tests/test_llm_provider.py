from __future__ import annotations

import sys
from types import SimpleNamespace


class _FakeOpenAIChatModel:
    def __init__(self, *, model_name: str, provider: object, settings: object | None = None) -> None:
        self.model_name = model_name
        self.provider = provider
        self.settings = settings


def test_fast_and_slow_agent_models_are_split(monkeypatch):
    import backend.llm_provider as llm_provider

    provider = object()
    monkeypatch.setattr(llm_provider, "get_openai_provider", lambda: provider)
    monkeypatch.setitem(
        sys.modules,
        "pydantic_ai.models.openai",
        SimpleNamespace(OpenAIChatModel=_FakeOpenAIChatModel),
    )
    monkeypatch.setenv("DOUBAO_MODEL", "doubao-fast")
    monkeypatch.setenv("OPENAI_MODEL", "minimax-slow")
    monkeypatch.delenv("OPENAI_FAST_MODEL", raising=False)

    fast_model = llm_provider.create_fast_model()
    slow_model = llm_provider.create_slow_model()
    default_model = llm_provider.create_agent_model()

    assert fast_model.model_name == "doubao-fast"
    assert slow_model.model_name == "minimax-slow"
    assert default_model.model_name == "minimax-slow"


def test_fast_model_allows_explicit_override(monkeypatch):
    import backend.llm_provider as llm_provider

    provider = object()
    monkeypatch.setattr(llm_provider, "get_openai_provider", lambda: provider)
    monkeypatch.setitem(
        sys.modules,
        "pydantic_ai.models.openai",
        SimpleNamespace(OpenAIChatModel=_FakeOpenAIChatModel),
    )
    monkeypatch.setenv("OPENAI_FAST_MODEL", "openrouter-fast-no-thinking")
    monkeypatch.setenv("DOUBAO_MODEL", "doubao-fast")
    monkeypatch.setenv("OPENAI_MODEL", "minimax-slow")

    fast_model = llm_provider.create_fast_model()

    assert fast_model.model_name == "openrouter-fast-no-thinking"


def test_voice_streaming_model_prefers_explicit_fast_override(monkeypatch):
    import backend.llm_provider as llm_provider

    monkeypatch.delenv("DOUBAO_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_FAST_MODEL", "voice-fast-model")
    monkeypatch.setenv("DOUBAO_API_KEY", "doubao-key")
    monkeypatch.setenv("OPENAI_MODEL", "slow-model")

    assert llm_provider.get_voice_streaming_model_name() == "voice-fast-model"


def test_voice_streaming_model_keeps_openai_fallback_without_doubao(monkeypatch):
    import backend.llm_provider as llm_provider

    monkeypatch.delenv("DOUBAO_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_FAST_MODEL", raising=False)
    monkeypatch.delenv("DOUBAO_API_KEY", raising=False)
    monkeypatch.delenv("DOUBAO_BASE_URL", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("OPENAI_MODEL", "openrouter-slow")

    assert llm_provider.get_voice_streaming_model_name() == "openrouter-slow"
