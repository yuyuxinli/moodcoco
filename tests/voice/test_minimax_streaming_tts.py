from __future__ import annotations

import json
from asyncio import Queue

import pytest

from backend.voice.plugins.minimax_streaming_tts import (
    MiniMaxStreamingTTSClient,
    MiniMaxStreamingTTSConfig,
)


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.recv_queue: Queue[dict] = Queue()
        self.closed = False

    def push(self, message: dict) -> None:
        self.recv_queue.put_nowait(message)

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def recv(self) -> str:
        return json.dumps(await self.recv_queue.get())

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_minimax_streaming_client_sends_text_and_yields_audio() -> None:
    ws = _FakeWebSocket()
    ws.push({"event": "connected_success", "base_resp": {"status_code": 0}})
    ws.push({"event": "task_started", "base_resp": {"status_code": 0}})
    ws.push(
        {
            "data": {"audio": b"audio-1".hex()},
            "is_final": False,
            "base_resp": {"status_code": 0},
        }
    )
    ws.push(
        {
            "data": {"audio": b"audio-2".hex()},
            "is_final": True,
            "base_resp": {"status_code": 0},
        }
    )
    seen: dict[str, object] = {}
    client = MiniMaxStreamingTTSClient(
        config=MiniMaxStreamingTTSConfig(api_key="key", group_id="group"),
        websocket_factory=lambda url, headers: (seen.update(url=url, headers=headers) or ws),
    )

    await client.start()
    chunks = [chunk async for chunk in client.synthesize_sentence("你好。")]
    await client.finish()

    assert chunks == [b"audio-1", b"audio-2"]
    assert ws.sent[0]["event"] == "task_start"
    assert ws.sent[0]["audio_setting"]["format"] == "pcm"
    assert ws.sent[1] == {"event": "task_continue", "text": "你好。"}
    assert ws.sent[-1] == {"event": "task_finish"}
    assert seen["url"] == "wss://api.minimax.io/ws/v1/t2a_v2?GroupId=group"
    assert seen["headers"] == {"Authorization": "Bearer key"}
    assert ws.closed is True
