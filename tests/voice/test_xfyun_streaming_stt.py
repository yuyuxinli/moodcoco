from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from livekit import rtc
from livekit.agents.stt import SpeechEventType

from backend.voice.plugins.xfyun_streaming_stt import (
    TranscriptAggregator,
    XfyunStreamingSTTPlugin,
    XfyunTranscriptEvent,
    build_xfyun_iat_url,
    parse_xfyun_iat_message,
)


def test_parse_xfyun_iat_partial_message() -> None:
    message = {
        "code": 0,
        "data": {
            "status": 1,
            "result": {
                "ws": [
                    {"cw": [{"w": "我"}]},
                    {"cw": [{"w": "今天"}]},
                ]
            },
        },
    }

    event = parse_xfyun_iat_message(message)

    assert event.text == "我今天"
    assert event.is_final is False


def test_parse_xfyun_iat_final_message() -> None:
    message = {
        "code": 0,
        "data": {
            "status": 2,
            "result": {
                "ws": [
                    {"cw": [{"w": "很"}]},
                    {"cw": [{"w": "难过"}]},
                ]
            },
        },
    }

    event = parse_xfyun_iat_message(message)

    assert event.text == "很难过"
    assert event.is_final is True


def test_parse_xfyun_iat_header_payload_final_message() -> None:
    text_payload = {
        "pgs": "apd",
        "ws": [
            {"cw": [{"w": "我"}]},
            {"cw": [{"w": "说完了"}]},
        ],
    }
    message = {
        "header": {"code": 0, "status": 2},
        "payload": {
            "result": {
                "text": base64.b64encode(
                    json.dumps(text_payload, ensure_ascii=False).encode("utf-8")
                ).decode("utf-8")
            }
        },
    }

    event = parse_xfyun_iat_message(message)

    assert event.text == "我说完了"
    assert event.segments == ["我", "说完了"]
    assert event.pgs == "apd"
    assert event.is_final is True


def test_parse_xfyun_iat_dynamic_replacement_metadata() -> None:
    message = {
        "code": 0,
        "data": {
            "status": 1,
            "result": {
                "pgs": "rpl",
                "rg": [2, 4],
                "ws": [{"cw": [{"w": "现在"}]}, {"cw": [{"w": "很难过"}]}],
            },
        },
    }

    event = parse_xfyun_iat_message(message)

    assert event.text == "现在很难过"
    assert event.segments == ["现在", "很难过"]
    assert event.pgs == "rpl"
    assert event.rg == [2, 4]


def test_transcript_aggregator_appends_partials() -> None:
    agg = TranscriptAggregator()

    assert agg.update(["我", "今天"], is_final=False) == "我今天"
    assert agg.update(["很", "难过"], is_final=True) == "我今天很难过"
    assert agg.final_text == "我今天很难过"


def test_transcript_aggregator_replaces_dynamic_correction_multi_slot_range() -> None:
    agg = TranscriptAggregator()

    assert agg.update(["我", "今天", "很", "烦"], is_final=False) == "我今天很烦"
    assert (
        agg.update(["现在", "很难过"], is_final=True, pgs="rpl", rg=[2, 4])
        == "我现在很难过"
    )
    assert agg.final_text == "我现在很难过"


def test_build_xfyun_iat_url_uses_hmac_authorization() -> None:
    url = build_xfyun_iat_url(
        base_url="wss://ws-api.xfyun.cn/v2/iat",
        api_key="test-key",
        api_secret="test-secret",
        now=datetime(2026, 5, 8, 0, 0, tzinfo=UTC),
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    decoded_auth = base64.b64decode(query["authorization"][0]).decode("utf-8")

    assert query["host"] == ["ws-api.xfyun.cn"]
    assert query["date"] == ["Fri, 08 May 2026 00:00:00 GMT"]
    assert 'api_key="test-key"' in decoded_auth
    assert 'headers="host date request-line"' in decoded_auth
    assert 'algorithm="hmac-sha256"' in decoded_auth


class _FakeStreamingClient:
    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self.sent_statuses: list[int] = []
        self.events_queue: asyncio.Queue[XfyunTranscriptEvent | None] = asyncio.Queue()

    async def start(self) -> None:
        self.started = True

    async def send_pcm(self, pcm: bytes, *, status: int) -> None:
        self.sent_statuses.append(status)

    async def events(self):
        while True:
            item = await self.events_queue.get()
            if item is None:
                return
            yield item
            if item.is_final:
                return

    async def close(self) -> None:
        self.closed = True


def _frame() -> rtc.AudioFrame:
    return rtc.AudioFrame(
        data=bytes(1600),
        sample_rate=16000,
        num_channels=1,
        samples_per_channel=800,
    )


def _voice_frame() -> rtc.AudioFrame:
    return rtc.AudioFrame(
        data=(b"\xff\x7f" * 800),
        sample_rate=16000,
        num_channels=1,
        samples_per_channel=800,
    )


async def _wait_until(predicate, *, timeout_s: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


def test_streaming_stt_capabilities() -> None:
    plugin = XfyunStreamingSTTPlugin(client_factory=_FakeStreamingClient)

    assert plugin.capabilities.streaming is True
    assert plugin.capabilities.interim_results is True


@pytest.mark.asyncio
async def test_streaming_stt_sends_first_frame_and_flush_status() -> None:
    client = _FakeStreamingClient()
    plugin = XfyunStreamingSTTPlugin(client_factory=lambda: client)
    stream = plugin.stream()

    stream.push_frame(_voice_frame())
    stream.flush()
    await _wait_until(lambda: len(client.sent_statuses) >= 2)
    client.events_queue.put_nowait(None)
    await stream.aclose()

    assert client.started is True
    assert client.sent_statuses[:2] == [0, 2]
    assert client.closed is True


@pytest.mark.asyncio
async def test_streaming_stt_logs_first_speech_frame(caplog: pytest.LogCaptureFixture) -> None:
    client = _FakeStreamingClient()
    plugin = XfyunStreamingSTTPlugin(client_factory=lambda: client)
    stream = plugin.stream()
    caplog.set_level(logging.INFO, logger="voice.plugins.xfyun_streaming_stt")

    stream.push_frame(_frame())
    stream.push_frame(_voice_frame())
    stream.flush()
    await _wait_until(lambda: client.started)
    client.events_queue.put_nowait(None)
    await stream.aclose()

    assert any(
        record.message == "voice_streaming_stt_speech_started"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_streaming_stt_auto_flushes_after_trailing_silence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _FakeStreamingClient()
    plugin = XfyunStreamingSTTPlugin(client_factory=lambda: client)
    stream = plugin.stream()
    caplog.set_level(logging.INFO, logger="voice.plugins.xfyun_streaming_stt")

    stream.push_frame(_voice_frame())
    for _ in range(20):
        stream.push_frame(_frame())

    await _wait_until(lambda: 2 in client.sent_statuses)
    client.events_queue.put_nowait(
        XfyunTranscriptEvent(text="说完了", segments=["说完了"], is_final=True)
    )
    client.events_queue.put_nowait(None)
    final = await stream.__anext__()
    await stream.aclose()

    assert client.sent_statuses[-1] == 2
    assert final.type == SpeechEventType.FINAL_TRANSCRIPT
    assert final.alternatives[0].text == "说完了"
    assert any(
        record.message == "voice_streaming_stt_endpointed"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_streaming_stt_keeps_stream_open_for_multiple_utterances() -> None:
    client = _FakeStreamingClient()
    plugin = XfyunStreamingSTTPlugin(client_factory=lambda: client)
    stream = plugin.stream()

    stream.push_frame(_voice_frame())
    for _ in range(20):
        stream.push_frame(_frame())
    await _wait_until(lambda: 2 in client.sent_statuses)
    client.events_queue.put_nowait(
        XfyunTranscriptEvent(text="第一句", segments=["第一句"], is_final=True)
    )
    first = await stream.__anext__()

    stream.push_frame(_voice_frame())
    for _ in range(20):
        stream.push_frame(_frame())
    await _wait_until(lambda: client.sent_statuses.count(2) >= 2)
    client.events_queue.put_nowait(
        XfyunTranscriptEvent(text="第二句", segments=["第二句"], is_final=True)
    )
    second = await stream.__anext__()
    await stream.aclose()

    assert first.type == SpeechEventType.FINAL_TRANSCRIPT
    assert first.alternatives[0].text == "第一句"
    assert second.type == SpeechEventType.FINAL_TRANSCRIPT
    assert second.alternatives[0].text == "第二句"


@pytest.mark.asyncio
async def test_streaming_stt_emits_interim_and_final_events() -> None:
    client = _FakeStreamingClient()
    plugin = XfyunStreamingSTTPlugin(client_factory=lambda: client)
    stream = plugin.stream()

    stream.push_frame(_voice_frame())
    client.events_queue.put_nowait(
        XfyunTranscriptEvent(text="我今天", segments=["我", "今天"], is_final=False)
    )
    client.events_queue.put_nowait(
        XfyunTranscriptEvent(text="我今天很难过", segments=["很", "难过"], is_final=True)
    )
    client.events_queue.put_nowait(None)

    first = await stream.__anext__()
    second = await stream.__anext__()
    await stream.aclose()

    assert first.type == SpeechEventType.INTERIM_TRANSCRIPT
    assert first.alternatives[0].text == "我今天"
    assert second.type == SpeechEventType.FINAL_TRANSCRIPT
    assert second.alternatives[0].text == "我今天很难过"
