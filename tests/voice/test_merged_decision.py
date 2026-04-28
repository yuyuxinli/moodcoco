"""Unit tests for the F6 merged Doubao decision."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.voice.decisions import merged_decision
from backend.voice.decisions.merged_decision import MergedDecisionResult, decide
from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx


def _mock_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = MagicMock()
    response.choices[0].message.content = content
    return response


def _patch_openai_create(content: str | None = None, exc: Exception | None = None):
    patcher = patch("backend.voice.decisions.merged_decision.AsyncOpenAI")
    mock_client_cls = patcher.start()
    client = mock_client_cls.return_value
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=exc,
        return_value=None if exc else _mock_response(content or ""),
    )
    return patcher, mock_client_cls, client


@pytest.mark.asyncio
async def test_decide_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    patcher, mock_client_cls, client = _patch_openai_create(
        '{"search":{"yes":true,"kw":"我妈"},"skill":"listen"}'
    )

    try:
        result = await decide("我妈又说我了", [{"role": "user", "content": "前情"}])
    finally:
        patcher.stop()

    assert isinstance(result, MergedDecisionResult)
    assert result.search_yes is True
    assert result.search_kw == "我妈"
    assert result.skill == "listen"
    assert result.raw_json == '{"search":{"yes":true,"kw":"我妈"},"skill":"listen"}'
    assert result.latency_ms > 0
    mock_client_cls.assert_called_once_with(
        base_url="https://example.test/v1",
        api_key="test-key",
    )
    client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_decide_json_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    caplog.set_level("WARNING", logger="voice.decisions.merged_decision")
    patcher, _mock_client_cls, _client = _patch_openai_create("not json")

    try:
        result = await decide("乱七八糟", [])
    finally:
        patcher.stop()

    assert result.search_yes is False
    assert result.search_kw == ""
    assert result.skill is None
    assert result.raw_json == "not json"
    assert any(
        record.levelname == "WARNING"
        and record.getMessage() == "merged_decision_json_fallback"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_decide_api_timeout(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    caplog.set_level("ERROR", logger="voice.decisions.merged_decision")
    patcher, _mock_client_cls, _client = _patch_openai_create(
        exc=httpx.TimeoutException("timed out")
    )

    try:
        result = await decide("你快点", [])
    finally:
        patcher.stop()

    assert result.search_yes is False
    assert result.search_kw == ""
    assert result.skill is None
    assert "timed out" in result.raw_json
    assert any(
        record.levelname == "ERROR"
        and record.getMessage() == "merged_decision_timeout"
        and getattr(record, "error_class", None) == "MergedDecisionTimeoutError"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_decide_unknown_skill_filtered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    patcher, _mock_client_cls, _client = _patch_openai_create(
        '{"search":{"yes":false,"kw":""},"skill":"not_a_real_skill"}'
    )

    try:
        result = await decide("我也不知道该怎么办", [])
    finally:
        patcher.stop()

    assert result.search_yes is False
    assert result.search_kw == ""
    assert result.skill is None


@pytest.mark.asyncio
async def test_decide_session_id_propagated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("DOUBAO_API_KEY", "test-key")
    patcher, _mock_client_cls, _client = _patch_openai_create(
        '{"search":{"yes":false,"kw":""},"skill":null}'
    )
    session_token = voice_session_ctx.set("room-abc")
    turn_token = voice_turn_ctx.set("turn-1234")

    try:
        with patch.object(merged_decision.logger, "info") as mock_info:
            result = await decide("就这样吧", [])
    finally:
        voice_turn_ctx.reset(turn_token)
        voice_session_ctx.reset(session_token)
        patcher.stop()

    assert result.skill is None
    assert mock_info.call_count >= 2
    first_extra = mock_info.call_args_list[0].kwargs["extra"]
    assert first_extra["session_id"] == "room-abc"
    assert first_extra["turn_id"] == "turn-1234"
