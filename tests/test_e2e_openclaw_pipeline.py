"""
E2E 测试：OpenClaw 新链路端到端验证

链路：
  测试脚本 → Socket.IO (localhost:8000) → ws_socketio.py → ChatProxy
  → OpenClaw Gateway (localhost:18789) → Agent Runtime → Tool Bridge
  → event_response → 测试脚本收到

前置条件：
  - 后端 FastAPI 已在 localhost:8000 运行
  - OpenClaw Gateway 已在 localhost:18789 运行
"""

import asyncio
import json
import uuid
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio
import socketio

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"
OPENCLAW_GATEWAY_URL = "http://localhost:18789"

AI_REPLY_TIMEOUT = 90

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

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

_cached_auth: Optional[Dict[str, str]] = None
_cached_session: Optional[Dict[str, str]] = None


async def _get_guest_auth() -> Dict[str, str]:
    global _cached_auth
    if _cached_auth is not None:
        return _cached_auth
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{API_BASE}/auth/guest/session")
        assert resp.status_code == 200, f"Guest auth failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "token" in data, f"Auth response missing 'token': {data}"
        assert "user_id" in data, f"Auth response missing 'user_id': {data}"
        print(f"\n[fixture] Guest auth OK: user_id={data['user_id']}")
        _cached_auth = {"token": data["token"], "user_id": data["user_id"]}
        return _cached_auth


async def _get_chat_session() -> Dict[str, str]:
    global _cached_session
    if _cached_session is not None:
        return _cached_session
    auth = await _get_guest_auth()
    token = auth["token"]
    user_id = auth["user_id"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{API_BASE}/chat/sessions",
            json={"user_id": user_id, "title": "E2E OpenClaw Test", "session_type": "MOOD"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code in (200, 201):
            session_id = resp.json().get("session_id")
            print(f"[fixture] Session created: {session_id}")
        else:
            session_id = str(uuid.uuid4())
            print(f"[fixture] Session create failed ({resp.status_code}), using random: {session_id}")
        _cached_session = {**auth, "session_id": session_id}
        return _cached_session


@pytest_asyncio.fixture
async def guest_auth() -> Dict[str, str]:
    return await _get_guest_auth()


@pytest_asyncio.fixture
async def chat_session() -> Dict[str, str]:
    return await _get_chat_session()


# ─────────────────────────────────────────────────────────────────────
# Test 1: 健康检查
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_backend_health():
    """后端 /api/health 返回 200 且 status=ok"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{API_BASE}/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "ok", f"Unexpected health response: {body}"
        print(f"[Test1] Backend health OK: {body}")


@pytest.mark.asyncio
async def test_openclaw_gateway_reachable():
    """OpenClaw Gateway 可达（尝试 health 端点或根路径）"""
    async with httpx.AsyncClient(timeout=10) as client:
        for path in ["/__openclaw__/health", "/health", "/v1/models", "/"]:
            try:
                resp = await client.get(f"{OPENCLAW_GATEWAY_URL}{path}")
                if resp.status_code < 500:
                    print(f"[Test1] OpenClaw Gateway reachable at {path}: {resp.status_code}")
                    return
            except httpx.ConnectError:
                pass
        pytest.fail(
            f"OpenClaw Gateway at {OPENCLAW_GATEWAY_URL} is not reachable on any known path"
        )


# ─────────────────────────────────────────────────────────────────────
# Test 2: Guest Auth
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_guest_auth(guest_auth: Dict[str, str]):
    """POST /api/auth/guest/session 返回 200 且含 token、user_id"""
    assert guest_auth["token"], "token is empty"
    assert guest_auth["user_id"], "user_id is empty"
    print(f"[Test2] Guest auth verified: user_id={guest_auth['user_id']}")


# ─────────────────────────────────────────────────────────────────────
# Test 3: Socket.IO 连接
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_socketio_connect(chat_session: Dict[str, str]):
    """通过 Socket.IO 连接后端，验证 connect 成功。"""
    token = chat_session["token"]
    session_id = chat_session["session_id"]
    client_id = str(uuid.uuid4())

    sio: Any = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)
    connected = asyncio.Event()

    @sio.event
    async def connect():
        connected.set()

    query_params = {
        "session_id": session_id,
        "client_id": client_id,
        "character_id": "linyu",
        "timezone_offset": "8",
        "session_type": "mood",
        "token": token,
    }
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query_params.items())
    connect_url = f"{BASE_URL}?{qs}"

    try:
        await sio.connect(connect_url, socketio_path="/socket.io/", transports=["websocket"], wait_timeout=20)
        await asyncio.wait_for(connected.wait(), timeout=10)
        assert connected.is_set(), "Socket.IO connection was not established"
        print(f"[Test3] Socket.IO connected successfully (session={session_id})")
    finally:
        if sio.connected:
            await sio.disconnect()


# ─────────────────────────────────────────────────────────────────────
# Test 4: AI 回复必须是结构化 JSON（通过 Tool Bridge）
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_reply_must_be_structured_json(chat_session: Dict[str, str]):
    """
    发送 '你好' 并严格验证：
      1. 至少收到一个 event_response 且 stream_data 是 JSON
      2. JSON 中包含 content_type 字段
      3. content_type 值在已知枚举中
      4. 如果是 AI_MESSAGE，messages 数组存在且非空
      5. 如果是 AI_OPTIONS，options 数组存在
      6. 纯文本回复 → FAIL
    """
    token = chat_session["token"]
    session_id = chat_session["session_id"]
    client_id = str(uuid.uuid4())

    sio: Any = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)

    connected = asyncio.Event()
    done = asyncio.Event()

    event_responses: List[Dict[str, Any]] = []
    structured_responses: List[Dict[str, Any]] = []
    plain_text_chunks: List[str] = []
    all_events: List[Dict[str, Any]] = []
    errors: List[str] = []

    @sio.event
    async def connect():
        connected.set()
        print("  [sio] connected")

    @sio.event
    async def connect_error(data):
        errors.append(f"connect_error: {data}")
        print(f"  [sio] connect_error: {data}")

    @sio.on("event_response")
    async def on_event_response(data):
        payload = data if isinstance(data, dict) else {}
        stream_data = payload.get("stream_data", "")
        stream_type = payload.get("stream_type", "")
        event_responses.append(payload)
        all_events.append({
            "event": "event_response",
            "stream_type": stream_type,
            "data_preview": str(stream_data)[:120],
            "has_content_type": "content_type" in payload if isinstance(payload, dict) else False,
        })

        if "content_type" in payload:
            structured_responses.append(payload)
        elif stream_data:
            parsed_json = _try_parse_json(stream_data)
            if parsed_json and "content_type" in parsed_json:
                structured_responses.append(parsed_json)
            elif isinstance(stream_data, str) and stream_data.strip():
                plain_text_chunks.append(stream_data.strip())

        print(f"  [sio] event_response: type={stream_type} ct={payload.get('content_type', '')} data={str(stream_data)[:80]}")

    @sio.on("event_processing_end")
    async def on_processing_end(data):
        all_events.append({"event": "event_processing_end", "data": str(data)[:200]})
        done.set()
        print(f"  [sio] event_processing_end")

    @sio.on("event_processing_start")
    async def on_processing_start(data):
        all_events.append({"event": "event_processing_start"})
        print("  [sio] event_processing_start")

    @sio.on("error")
    async def on_error(data):
        errors.append(str(data))
        all_events.append({"event": "error", "data": str(data)[:200]})
        print(f"  [sio] error: {data}")
        done.set()

    @sio.on("session_updated")
    async def on_session_updated(data):
        nonlocal session_id
        all_events.append({"event": "session_updated", "data": str(data)[:200]})
        if isinstance(data, dict) and data.get("new_session_id"):
            session_id = data["new_session_id"]
            print(f"  [sio] session_updated → {session_id}")

    query_params = {
        "session_id": session_id,
        "client_id": client_id,
        "character_id": "linyu",
        "timezone_offset": "8",
        "session_type": "mood",
        "token": token,
    }
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query_params.items())
    connect_url = f"{BASE_URL}?{qs}"

    try:
        await sio.connect(connect_url, socketio_path="/socket.io/", transports=["websocket"], wait_timeout=20)
        await asyncio.wait_for(connected.wait(), timeout=10)
        assert connected.is_set(), "Socket.IO connection failed"
        print(f"[Test4] Connected, session_id={session_id}")

        await asyncio.sleep(3)

        msg = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": "你好"},
            },
        }
        print(f"[Test4] Sending message: 你好")
        await sio.emit("custom_event", msg)

        try:
            await asyncio.wait_for(done.wait(), timeout=AI_REPLY_TIMEOUT)
        except asyncio.TimeoutError:
            pass

        # ─── Results Summary ───
        print(f"\n[Test4] Results:")
        print(f"  event_responses: {len(event_responses)}")
        print(f"  structured_responses (with content_type): {len(structured_responses)}")
        print(f"  plain_text_chunks: {len(plain_text_chunks)}")
        for i, resp in enumerate(event_responses):
            sd = resp.get("stream_data", "")
            st = resp.get("stream_type", "")
            print(f"  event_response[{i}]: stream_type={st} stream_data={str(sd)[:200]}")
        if plain_text_chunks:
            combined_plain = "".join(plain_text_chunks)
            print(f"  plain_text_content: {combined_plain[:200]}")
        if errors:
            print(f"  errors: {errors}")

        # ─── Assertion 1: 收到至少一个 event_response ───
        assert len(event_responses) > 0, (
            f"No event_response received. All events: {all_events}"
        )

        # ─── Assertion 2: 至少一个结构化响应包含 content_type ───
        assert len(structured_responses) > 0, (
            f"No structured JSON response with content_type received. "
            f"Got {len(plain_text_chunks)} plain text chunks instead: "
            f"{plain_text_chunks[:3]}. "
            f"Agent is outputting plain text — it must use Tool calls "
            f"(ai_message, ai_options, etc.) for all output."
        )

        # ─── Assertion 3: content_type 值在已知枚举中 ───
        for i, resp in enumerate(structured_responses):
            ct = resp.get("content_type")
            assert ct in KNOWN_CONTENT_TYPES, (
                f"structured_response[{i}] has unknown content_type '{ct}'. "
                f"Known types: {KNOWN_CONTENT_TYPES}"
            )
            print(f"  [Assertion3] content_type={ct} ✓")

        # ─── Assertion 4: AI_MESSAGE → messages 非空 ───
        for i, resp in enumerate(structured_responses):
            ct = resp.get("content_type")
            if ct == "AI_MESSAGE":
                messages = resp.get("messages") or []
                content = resp.get("content", {})
                if isinstance(content, dict):
                    messages = messages or content.get("messages", [])
                assert isinstance(messages, list) and len(messages) > 0, (
                    f"AI_MESSAGE[{i}] has empty or invalid messages: {resp}"
                )
                print(f"  [Assertion4] AI_MESSAGE messages={messages} ✓")

            # ─── Assertion 5: AI_OPTIONS → options 非空 ───
            if ct == "AI_OPTIONS":
                options = resp.get("options") or []
                content = resp.get("content", {})
                if isinstance(content, dict):
                    options = options or content.get("options", [])
                assert isinstance(options, list) and len(options) > 0, (
                    f"AI_OPTIONS[{i}] has empty or invalid options: {resp}"
                )
                print(f"  [Assertion5] AI_OPTIONS options count={len(options)} ✓")

        # ─── Assertion 6: 不接受纯文本回复 ───
        if plain_text_chunks and not structured_responses:
            pytest.fail(
                f"Agent output was pure plain text (no Tool calls). "
                f"Plain text: {''.join(plain_text_chunks)[:300]}. "
                f"Agent MUST use ai_message() Tool for all text output."
            )

        print(f"[Test4] PASS: All {len(structured_responses)} responses are structured JSON with valid content_type")

    finally:
        if sio.connected:
            await sio.disconnect()


# ─────────────────────────────────────────────────────────────────────
# Test 5: Tool Bridge 推送路径验证
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_bridge_push_path(chat_session: Dict[str, str]):
    """
    验证 event_response 是通过 Tool Bridge 推送的。

    Tool Bridge 推送的 event_response 的 stream_data 是完整的 JSON 对象
    （包含 content_type），而非 ChatProxy 的纯文本流。
    """
    token = chat_session["token"]
    session_id = chat_session["session_id"]
    client_id = str(uuid.uuid4())

    sio: Any = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)

    connected = asyncio.Event()
    done = asyncio.Event()

    event_responses: List[Dict[str, Any]] = []
    tool_bridge_responses: List[Dict[str, Any]] = []

    @sio.event
    async def connect():
        connected.set()

    @sio.on("event_response")
    async def on_event_response(data):
        payload = data if isinstance(data, dict) else {}
        event_responses.append(payload)

        if "content_type" in payload:
            tool_bridge_responses.append(payload)
        else:
            stream_data = payload.get("stream_data", "")
            parsed = _try_parse_json(stream_data)
            if parsed and "content_type" in parsed:
                tool_bridge_responses.append(parsed)

    @sio.on("event_processing_end")
    async def on_processing_end(data):
        done.set()

    @sio.on("error")
    async def on_error(data):
        done.set()

    @sio.on("session_updated")
    async def on_session_updated(data):
        nonlocal session_id
        if isinstance(data, dict) and data.get("new_session_id"):
            session_id = data["new_session_id"]

    query_params = {
        "session_id": session_id,
        "client_id": client_id,
        "character_id": "linyu",
        "timezone_offset": "8",
        "session_type": "mood",
        "token": token,
    }
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query_params.items())
    connect_url = f"{BASE_URL}?{qs}"

    try:
        await sio.connect(connect_url, socketio_path="/socket.io/", transports=["websocket"], wait_timeout=20)
        await asyncio.wait_for(connected.wait(), timeout=10)

        await asyncio.sleep(3)

        msg = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": "你好"},
            },
        }
        await sio.emit("custom_event", msg)

        try:
            await asyncio.wait_for(done.wait(), timeout=AI_REPLY_TIMEOUT)
        except asyncio.TimeoutError:
            pass

        print(f"\n[Test5] Tool Bridge push path results:")
        print(f"  total event_responses: {len(event_responses)}")
        print(f"  tool_bridge_responses (with content_type): {len(tool_bridge_responses)}")

        assert len(tool_bridge_responses) > 0, (
            f"No Tool Bridge responses detected. "
            f"All {len(event_responses)} event_responses were plain text stream "
            f"(no content_type in stream_data). "
            f"This means the Agent is NOT using Tool calls."
        )

        for i, resp in enumerate(tool_bridge_responses):
            ct = resp.get("content_type")
            assert ct in KNOWN_CONTENT_TYPES, (
                f"Tool Bridge response[{i}] has unknown content_type: {ct}"
            )

        print(f"[Test5] PASS: {len(tool_bridge_responses)} responses came through Tool Bridge")

    finally:
        if sio.connected:
            await sio.disconnect()


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _try_parse_json(data) -> Optional[Dict[str, Any]]:
    """Attempt to parse stream_data as JSON. Returns dict or None."""
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
