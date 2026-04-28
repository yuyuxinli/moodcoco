"""Unit tests for F6 merged Doubao-lite decision.

All tests mock the Doubao call; no network is used.
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from backend.voice.decisions import merged_decision
from backend.voice.decisions.merged_decision import MergedDecisionResult, SearchDecision
from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx


@pytest.fixture(autouse=True)
def _reset_voice_contextvars():
    session_token = voice_session_ctx.set(None)
    turn_token = voice_turn_ctx.set(None)
    yield
    voice_session_ctx.reset(session_token)
    voice_turn_ctx.reset(turn_token)


@pytest.mark.asyncio
async def test_happy_path(monkeypatch):
    mock_call = AsyncMock(
        return_value='{"search":{"yes":true,"kw":"我妈"},"skill":"listen"}'
    )
    monkeypatch.setattr(merged_decision, "_call_doubao", mock_call)

    result = await merged_decision.decide("我妈又说我了", [{"role": "user"}])

    assert result.search == SearchDecision(yes=True, kw="我妈")
    assert result.skill == "listen"
    assert result.raw_json
    mock_call.assert_awaited_once_with(
        user_msg="我妈又说我了",
        recent_ctx=[{"role": "user"}],
    )


@pytest.mark.asyncio
async def test_json_parse_failure(monkeypatch):
    monkeypatch.setattr(
        merged_decision,
        "_call_doubao",
        AsyncMock(return_value="not json"),
    )

    result = await merged_decision.decide("随便聊聊", [])

    assert result == MergedDecisionResult(raw_json="not json", latency_ms=result.latency_ms)
    assert result.search == SearchDecision()
    assert result.skill is None


@pytest.mark.asyncio
async def test_api_timeout(monkeypatch):
    monkeypatch.setattr(
        merged_decision,
        "_call_doubao",
        AsyncMock(side_effect=asyncio.TimeoutError("too slow")),
    )

    result = await merged_decision.decide("我有点卡住了", [])

    assert result.search == SearchDecision()
    assert result.skill is None
    assert "too slow" in result.raw_json


@pytest.mark.asyncio
async def test_unknown_skill_filtered(monkeypatch):
    monkeypatch.setattr(
        merged_decision,
        "_call_doubao",
        AsyncMock(
            return_value='{"search":{"yes":false,"kw":""},"skill":"unknown-xyz"}'
        ),
    )

    result = await merged_decision.decide("不知道该怎么办", [])

    assert result.search == SearchDecision(yes=False, kw="")
    assert result.skill is None


@pytest.mark.asyncio
async def test_session_id_propagated(monkeypatch, caplog):
    monkeypatch.setattr(
        merged_decision,
        "_call_doubao",
        AsyncMock(return_value='{"search":{"yes":false,"kw":""},"skill":null}'),
    )
    voice_session_ctx.set("room-123")
    voice_turn_ctx.set("turn-abc")

    caplog.set_level(logging.INFO, logger="voice.decisions.merged_decision")
    await merged_decision.decide("我想安静一下", [])

    records = [
        record
        for record in caplog.records
        if record.name == "voice.decisions.merged_decision"
    ]
    assert records
    assert all(record.session_id == "room-123" for record in records)
    assert all(record.turn_id == "turn-abc" for record in records)
