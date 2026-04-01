"""
Journey E2E 测试共享工具：常量、Socket.IO 封装、数据解析。
"""

import asyncio
import json
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import socketio

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"
AI_REPLY_TIMEOUT = 90
STATE_FILE = Path(__file__).parent / ".journey_state.json"

KNOWN_CONTENT_TYPES = {
    "AI_MESSAGE",
    "AI_OPTIONS",
    "AI_MOOD_SELECT",
    "AI_MOOD_RECOVERY",
    "AI_SAFETY_BRAKE",
    "AI_PRAISE_POPUP",
    "AI_EMOTION_RESPONSE",
    "AI_FEELING_EXPLORATION",
    "AI_THOUGHT_FEELING",
    "AI_BODY_SENSATION",
    "AI_RELATIONSHIP",
    "AI_COMPLETE_CONVERSATION",
    "AI_LESSON_CARD",
    "AI_MICRO_LESSON_BATCH",
    "AI_QUIZ_PRACTICE",
    "AI_COURSE_COMPLETE",
    "AI_GROWTH_GREETING",
}


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def try_parse_json(data: Any) -> dict | None:
    if isinstance(data, dict):
        return data
    if not isinstance(data, str):
        return None
    stripped = data.strip()
    if not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    return None


@dataclass
class SioReply:
    """Collected responses from a single AI reply cycle."""

    event_responses: list[dict[str, Any]] = field(default_factory=list)
    structured: list[dict[str, Any]] = field(default_factory=list)
    plain_chunks: list[str] = field(default_factory=list)
    all_events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timed_out: bool = False

    @property
    def full_text(self) -> str:
        parts: list[str] = []
        for resp in self.structured:
            ct = resp.get("content_type", "")
            if ct in ("AI_MESSAGE", "AI_EMOTION_RESPONSE"):
                msgs = resp.get("messages") or []
                content = resp.get("content", {})
                if isinstance(content, dict):
                    msgs = msgs or content.get("messages", [])
                for m in msgs:
                    if isinstance(m, dict):
                        parts.append(m.get("text", ""))
                    elif isinstance(m, str):
                        parts.append(m)
            elif ct == "AI_OPTIONS":
                parts.append(resp.get("text", "") or resp.get("question", ""))
            elif ct == "AI_SAFETY_BRAKE":
                parts.append(resp.get("support_message", ""))
            elif ct == "AI_THOUGHT_FEELING":
                parts.append(resp.get("invitation_text", ""))
        if not parts:
            parts = self.plain_chunks
        return "".join(parts)


class JourneySio:
    """
    Socket.IO session wrapper for journey tests.
    Handles connect/disconnect and message send/collect.
    """

    def __init__(self, token: str, session_type: str = "mood"):
        self.token = token
        self.session_type = session_type
        self.session_id: str | None = None
        self.sio: socketio.AsyncClient | None = None
        self._connected = asyncio.Event()
        self._done = asyncio.Event()
        self._current_reply = SioReply()

    async def connect(self, session_id: str | None = None) -> None:
        if session_id:
            self.session_id = session_id
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{API_BASE}/chat/sessions",
                    json={
                        "user_id": "",
                        "title": "Journey E2E",
                        "session_type": self.session_type.upper(),
                    },
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                if resp.status_code in (200, 201):
                    self.session_id = resp.json().get(
                        "session_id", str(uuid.uuid4())
                    )
                else:
                    self.session_id = str(uuid.uuid4())

        self.sio = socketio.AsyncClient(
            reconnection=False, logger=False, engineio_logger=False
        )
        self._connected.clear()
        self._setup_handlers()

        query_params = {
            "session_id": self.session_id,
            "client_id": str(uuid.uuid4()),
            "character_id": "linyu",
            "timezone_offset": "8",
            "session_type": self.session_type,
            "token": self.token,
        }
        qs = "&".join(
            f"{k}={urllib.parse.quote(str(v))}" for k, v in query_params.items()
        )
        await self.sio.connect(
            f"{BASE_URL}?{qs}",
            socketio_path="/socket.io/",
            transports=["websocket"],
            wait_timeout=20,
        )
        await asyncio.wait_for(self._connected.wait(), timeout=10)
        await asyncio.sleep(2)

    def _setup_handlers(self) -> None:
        sio = self.sio

        @sio.event
        async def connect():
            self._connected.set()

        @sio.on("event_response")
        async def on_event_response(data):
            payload = data if isinstance(data, dict) else {}
            reply = self._current_reply
            reply.event_responses.append(payload)
            reply.all_events.append(
                {"event": "event_response", "data_preview": str(payload)[:200]}
            )

            if "content_type" in payload:
                reply.structured.append(payload)
            else:
                stream_data = payload.get("stream_data", "")
                parsed = try_parse_json(stream_data)
                if parsed and "content_type" in parsed:
                    reply.structured.append(parsed)
                elif isinstance(stream_data, str) and stream_data.strip():
                    reply.plain_chunks.append(stream_data.strip())

        @sio.on("event_processing_end")
        async def on_processing_end(data):
            self._current_reply.all_events.append({"event": "event_processing_end"})
            self._done.set()

        @sio.on("event_processing_start")
        async def on_processing_start(data):
            self._current_reply.all_events.append(
                {"event": "event_processing_start"}
            )

        @sio.on("error")
        async def on_error(data):
            err_str = str(data)
            self._current_reply.errors.append(err_str)
            print(f"  [sio] error: {err_str[:300]}")
            self._done.set()

        @sio.on("session_updated")
        async def on_session_updated(data):
            if isinstance(data, dict) and data.get("new_session_id"):
                self.session_id = data["new_session_id"]

    async def send(
        self, text: str, timeout: float = AI_REPLY_TIMEOUT
    ) -> SioReply:
        """Send a message and collect all responses until event_processing_end."""
        self._done.clear()
        self._current_reply = SioReply()

        msg = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": text},
            },
        }
        print(f"\n  -> 发送: {text}")
        await self.sio.emit("custom_event", msg)

        try:
            await asyncio.wait_for(self._done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._current_reply.timed_out = True
            print(f"  !! 超时 ({timeout}s)")

        reply = self._current_reply
        print(
            f"  <- 收到 {len(reply.event_responses)} 条 event_response, "
            f"{len(reply.structured)} 条结构化"
        )
        if reply.full_text:
            print(f"  <- AI: {reply.full_text[:200]}")
        return reply

    async def send_burst(
        self,
        texts: list[str],
        interval: float = 0.3,
        timeout: float = AI_REPLY_TIMEOUT,
        settle_time: float = 5.0,
    ) -> SioReply:
        """
        Send multiple messages rapidly and collect combined responses.
        Waits for event_processing_end, then an additional settle_time
        to drain any remaining events from queued messages.
        """
        self._done.clear()
        self._current_reply = SioReply()

        for text in texts:
            msg = {
                "event_type": "user_message",
                "payload": {
                    "event_name": "send_message",
                    "action_payload": {"text": text},
                },
            }
            print(f"\n  -> burst: {text}")
            await self.sio.emit("custom_event", msg)
            await asyncio.sleep(interval)

        try:
            await asyncio.wait_for(self._done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._current_reply.timed_out = True

        await asyncio.sleep(settle_time)
        return self._current_reply

    async def disconnect(self) -> None:
        if self.sio and self.sio.connected:
            await self.sio.disconnect()
