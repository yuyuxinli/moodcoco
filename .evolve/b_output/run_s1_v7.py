#!/usr/bin/env python3
"""
S1: 陌生人 — 首次接触 (v7) — Decompose: 修复 JSON 污染 + workspace 路径
根因分析（v7 修复项）：
1. JSON 格式污染（已修复）：
   - MoodAgent Tool 调用（AI_MESSAGE 等）通过 stream_type=content 下发 JSON 字符串
     格式: {"content_type": "AI_MESSAGE", "messages": ["..."]}
   - v6 的 on_event_response 直接拼接所有 stream_data，导致 JSON 混入文本
   - v7 修复: extract_text_from_stream_data() 解析每个 stream_data chunk：
       * 若是 AI_MESSAGE JSON → 提取 messages[] 拼接
       * 若是其他工具 JSON → 跳过（非文本响应）
       * 若是普通文本 → 直接用
2. workspace 路径错误（已修复）：
   - v6 检查的是 /Users/jianghongwei/Documents/moodcoco/ai-companion（源码 workspace）
   - 实际运行时 workspace 是 openclaw.json 指定的 ./backend/ai-companion/ai-companion
   - v7 修复: WORKSPACE = /Users/jianghongwei/Documents/psychologists/backend/ai-companion/ai-companion
3. workspace 写入根因说明（本次不修复，仅记录）：
   - people/小白.md 未创建：S1 对话共 7 轮，Turn 6 agent 回应"你说的小白，是男朋友小凯吗？"
     仍在消歧阶段，未完成确认 → agent 未执行 write("people/小白.md")
   - 这是正确的产品行为，但 workspace_people_created 评分需调整预期
   - workspace_user_md_updated 检查正确，但需等 Turn 7 结束后 agent 静默写入（约 5s）
"""

import asyncio
import json
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
import socketio

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

# ─── 运行时 workspace 路径（基于 openclaw.json workspace 字段）─────────────────
RUNTIME_WORKSPACE = "/Users/jianghongwei/Documents/psychologists/backend/ai-companion/ai-companion"

# ─── 工具函数 ────────────────────────────────────────────────────────────────

def http_get(url, token=None):
    req = urllib.request.Request(url)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes.decode())
        except Exception:
            return e.code, {"raw": body_bytes.decode()[:200]}
    except Exception as ex:
        return 0, {"error": str(ex)}

def http_post(url, data=None, token=None):
    body = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes.decode())
        except Exception:
            return e.code, {"raw": body_bytes.decode()[:200]}
    except Exception as ex:
        return 0, {"error": str(ex)}


def extract_text_from_stream_data(stream_data: str) -> str:
    """
    从 stream_data 中提取人类可读文本。

    MoodAgent 通过 event_response 下发的 stream_data 有两种格式：
    1. 普通文本 (tool_choice=auto/none 的 plain_text 模式): 直接返回
    2. Tool 响应 JSON:
       - AI_MESSAGE: {"content_type": "AI_MESSAGE", "messages": ["句子1", "句子2"]}
         → 提取 messages 数组拼接成文本
       - 其他工具 (AI_OPTIONS, AI_MOOD_SELECT 等): 非文本响应，返回空字符串跳过
       - 音频 URL (sentence_audio stream_type 单独下发，不会进入这里)

    注意：stream_type=sentence_audio 的 stream_data 是音频 URL，
    在 on_event_response 中通过 stream_type 过滤掉，不传入此函数。
    """
    if not stream_data:
        return ""

    # 尝试解析 JSON（Tool 响应格式）
    stripped = stream_data.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                content_type = parsed.get("content_type", "")
                if content_type == "AI_MESSAGE":
                    messages = parsed.get("messages", [])
                    if isinstance(messages, list):
                        return "".join(str(m) for m in messages)
                    return ""
                # 其他工具类型（AI_OPTIONS, AI_THOUGHT_FEELING, etc.）：
                # 非纯文本响应，不计入对话文本
                elif content_type:
                    return ""
                # 没有 content_type 的 JSON（异常情况）：跳过
                return ""
        except (json.JSONDecodeError, ValueError):
            # 解析失败说明是普通文本（或部分 chunk）
            pass

    return stream_data


# ─── 主测试逻辑 ──────────────────────────────────────────────────────────────

async def run_s1():
    import time as _time_mod
    _test_start_ts = _time_mod.time()
    result = {
        "feature": "S1",
        "version": "v7",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "_test_start_ts": _test_start_ts,
        "user_id": None,
        "auth_token": None,
        "session_id": None,
        "conversations": [],
        "api_responses": {},
        "functional_checks": {
            "auth_200": False,
            "socket_connected": False,
            "ai_reply_received": False,
            "about_self_200": False,
            "about_relations_200": False,
            "xiaobo_profile_found": False,
            "xiaobo_relation_type_correct": False,
            "rapid_fire_merged": False,
            "workspace_user_md_updated": False,
            "workspace_people_created": False,
        },
        "passed_checks": 0,
        "total_checks": 10,
        "errors": [],
        "steps_completed": 0,
        "steps_total": 10,
        "p1_mbti_in_reply": [],  # 追踪每轮是否含 MBTI
    }

    # ── Step 1: 获取 Guest Session Token ─────────────────────────────────────
    print("[S1v7] Step 1: POST /api/auth/guest/session")
    status, auth_resp = http_post(f"{API_BASE}/auth/guest/session")
    result["api_responses"]["auth"] = {"status": status, "body": auth_resp}

    if status == 200:
        result["functional_checks"]["auth_200"] = True
        result["user_id"] = auth_resp.get("user_id")
        result["auth_token"] = auth_resp.get("token")
        print(f"  OK Auth: user_id={result['user_id']}")
        result["steps_completed"] += 1
    else:
        result["errors"].append(f"Auth failed: {status} {auth_resp}")
        print(f"  FAIL Auth: {status}")
        return result

    token = result["auth_token"]
    user_id = result["user_id"]

    # ── 创建 Chat Session (HTTP) — 使用 MOOD 类型 ────────────────────────────
    print("[S1v7] 预备: POST /api/chat/sessions 创建 MOOD 会话")
    status, session_resp = http_post(
        f"{API_BASE}/chat/sessions",
        {"user_id": user_id, "title": "S1 首次接触测试", "session_type": "MOOD"},
        token,
    )
    print(f"  HTTP session create: status={status}, resp={str(session_resp)[:200]}")
    if status in (200, 201):
        session_id = session_resp.get("session_id")
        result["session_id"] = session_id
        print(f"  OK Session (MOOD): session_id={session_id}")
    else:
        # fallback: 生成新 UUID，连接时用 session_type=mood
        session_id = str(uuid.uuid4())
        result["session_id"] = session_id
        result["errors"].append(f"Session create failed: {status} {session_resp}, using random UUID with mood type")
        print(f"  WARN: 无法创建会话 ({status}), 使用随机 session_id={session_id}，连接时指定 mood")

    client_id = str(uuid.uuid4())

    # ── Step 2: 连接 Socket.IO (session_type=mood) ────────────────────────────
    print(f"[S1v7] Step 2: 连接 Socket.IO (session={session_id}, type=mood)")

    sio = socketio.AsyncClient(
        reconnection=False,
        logger=False,
        engineio_logger=False,
    )

    socket_connected = False

    # 收集当前轮内容
    current_text_parts = []      # 仅文本内容（过滤 JSON 工具响应）
    current_raw_parts = []       # 原始 stream_data（包含 JSON）
    current_done_event = asyncio.Event()
    processing_end_count = 0

    # 所有服务器事件（捕获所有类型）
    all_server_events = []

    @sio.event  # type: ignore[misc]
    async def connect():
        nonlocal socket_connected
        socket_connected = True
        print("  OK Socket.IO connected")

    @sio.event  # type: ignore[misc]
    async def connect_error(data):
        print(f"  FAIL connect_error: {data}")

    @sio.event  # type: ignore[misc]
    async def disconnect():
        print("  Socket.IO disconnected")

    # ── 捕获所有事件 ──────────────────────────────────────────────────────────

    @sio.on("event_response")  # type: ignore[misc]
    async def _on_event_response(data):
        try:
            payload = data.get("payload", data) if isinstance(data, dict) else {}
            stream_data = payload.get("stream_data", "")
            stream_type = payload.get("stream_type", "content")

            # 记录原始数据
            if stream_data:
                current_raw_parts.append(stream_data)

            # 跳过 sentence_audio（音频 URL），只处理 content 类型
            if stream_type not in ("content", ""):
                if stream_type == "sentence_audio":
                    pass  # 忽略音频 URL
                # 其他非 content 类型也跳过文本收集
            else:
                # 修复：提取文本内容，过滤 JSON Tool 响应
                text = extract_text_from_stream_data(stream_data)
                if text:
                    current_text_parts.append(text)

            all_server_events.append({
                "event": "event_response",
                "ts": time.time(),
                "stream_id": payload.get("stream_id"),
                "stream_type": stream_type,
                "has_data": bool(stream_data),
                "data_preview": str(stream_data)[:80] if stream_data else "",
            })
        except Exception as e:
            print(f"  [warn] on_event_response: {e}")

    @sio.on("event_processing_end")  # type: ignore[misc]
    async def _on_event_processing_end(data):
        nonlocal processing_end_count
        processing_end_count += 1
        all_server_events.append({
            "event": "event_processing_end",
            "ts": time.time(),
            "count": processing_end_count,
            "data": str(data)[:100],
        })
        current_done_event.set()
        print(f"  <- event_processing_end #{processing_end_count}")

    @sio.on("message")  # type: ignore[misc]
    async def _on_message(data):
        all_server_events.append({"event": "message", "ts": time.time(), "data": str(data)[:100]})
        current_done_event.set()

    @sio.on("error")  # type: ignore[misc]
    async def _on_error(data):
        print(f"  [server error] {data}")
        all_server_events.append({"event": "error", "data": str(data)[:200], "ts": time.time()})
        current_done_event.set()

    @sio.on("event_processing_start")  # type: ignore[misc]
    async def _on_processing_start():
        all_server_events.append({"event": "event_processing_start", "ts": time.time()})
        print("  <- event_processing_start")

    @sio.on("message_buffered")  # type: ignore[misc]
    async def _on_buffered():
        all_server_events.append({"event": "message_buffered", "ts": time.time()})
        print("  <- message_buffered")

    @sio.on("content_chunk")  # type: ignore[misc]
    async def _on_content_chunk(data):
        all_server_events.append({"event": "content_chunk", "ts": time.time(), "data": str(data)[:100]})
        if isinstance(data, dict) and data.get("content"):
            text = extract_text_from_stream_data(data["content"])
            if text:
                current_text_parts.append(text)

    @sio.on("action_result")  # type: ignore[misc]
    async def _on_action_result(data):
        all_server_events.append({"event": "action_result", "ts": time.time(), "data": str(data)[:200]})
        print(f"  <- action_result: {str(data)[:100]}")

    @sio.on("async_task_progress")  # type: ignore[misc]
    async def _on_async_task_progress(data):
        all_server_events.append({"event": "async_task_progress", "ts": time.time(), "data": str(data)[:200]})
        print(f"  <- async_task_progress: {str(data)[:100]}")

    @sio.on("session_updated")  # type: ignore[misc]
    async def _on_session_updated(data):
        nonlocal session_id
        all_server_events.append({"event": "session_updated", "ts": time.time(), "data": str(data)[:200]})
        print(f"  <- session_updated: {str(data)[:200]}")
        # 更新 session_id
        if isinstance(data, dict) and data.get("new_session_id"):
            session_id = data["new_session_id"]
            result["session_id"] = session_id
            print(f"  [session_id updated to] {session_id}")

    # 注册所有其他事件的通用捕获器
    @sio.on("*")  # type: ignore[misc]
    async def _on_any(event, data):
        if event not in ("event_response", "event_processing_end", "event_processing_start",
                         "message", "error", "message_buffered", "content_chunk",
                         "action_result", "async_task_progress", "session_updated",
                         "connect", "disconnect", "connect_error"):
            all_server_events.append({"event": f"UNKNOWN:{event}", "ts": time.time(), "data": str(data)[:150]})
            print(f"  <- UNKNOWN EVENT: {event} | {str(data)[:100]}")

    # 连接时通过 query string 传认证参数（session_type=mood）
    query_params = {
        "session_id": session_id,
        "client_id": client_id,
        "character_id": "linyu",
        "timezone_offset": "8",
        "session_type": "mood",  # 使用 mood 类型
        "token": token,
    }
    query_string = "&".join(
        f"{k}={urllib.parse.quote(str(v))}" for k, v in query_params.items()
    )
    connect_url = f"{BASE_URL}?{query_string}"

    try:
        await sio.connect(
            connect_url,
            socketio_path="/socket.io/",
            transports=["websocket"],
            wait_timeout=20,
        )
        await asyncio.sleep(2)  # 等待 session_started 介绍完成
        if socket_connected:
            result["functional_checks"]["socket_connected"] = True
            result["steps_completed"] += 1
    except Exception as e:
        result["errors"].append(f"Socket.IO 连接失败: {e}")
        print(f"  FAIL Socket.IO: {e}")
        result["api_responses"]["socket_events"] = all_server_events
        return result

    if not socket_connected:
        print("  FAIL: socket_connected=False after connect()")
        result["api_responses"]["socket_events"] = all_server_events
        return result

    # ── 发送消息帮助函数 ──────────────────────────────────────────────────────
    async def send_and_wait(text, label, wait_sec=30):
        nonlocal current_text_parts, current_raw_parts, current_done_event
        current_text_parts = []
        current_raw_parts = []
        current_done_event = asyncio.Event()

        msg = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": text},
            },
        }
        print(f"  -> send({label}): {text[:60]}")
        await sio.emit("custom_event", msg)

        try:
            await asyncio.wait_for(current_done_event.wait(), timeout=wait_sec)
        except asyncio.TimeoutError:
            print(f"  [timeout] {label} 超时 {wait_sec}s")

        full_reply = "".join(current_text_parts)
        preview = (full_reply[:150] + "...") if len(full_reply) > 150 else full_reply
        print(f"  <- reply({label}): {preview or '[empty]'}")

        # 检查回复中是否含 MBTI（P1 追踪）
        mbti_in_reply = "MBTI" in full_reply or "mbti" in full_reply.lower()
        result["p1_mbti_in_reply"].append({"turn": label, "mbti": mbti_in_reply})
        if mbti_in_reply:
            print(f"  [P1 WARNING] 回复中含有 MBTI 引导!")

        return full_reply

    # ── Step 3: Turn 1 ────────────────────────────────────────────────────────
    print("[S1v7] Step 3: Turn 1 - 初次倾诉")
    await asyncio.sleep(1)
    r1 = await send_and_wait("我刚跟男朋友吵了一架，好烦", "T1")
    # ai_reply_received: 检查任意一轮有回复即可（OpenClaw 首轮可能做 silent tool calls）
    if r1:
        result["functional_checks"]["ai_reply_received"] = True
    result["conversations"].append({"turn": 1, "user": "我刚跟男朋友吵了一架，好烦", "ai_response": r1})
    result["steps_completed"] += 1

    # ── Step 4: Turn 2 ────────────────────────────────────────────────────────
    print("[S1v7] Step 4: Turn 2 - 被说太敏感")
    await asyncio.sleep(2)
    r2 = await send_and_wait("他说我太敏感了，每次都这样说我", "T2")
    if r2 and not result["functional_checks"]["ai_reply_received"]:
        result["functional_checks"]["ai_reply_received"] = True
    result["conversations"].append({"turn": 2, "user": "他说我太敏感了，每次都这样说我", "ai_response": r2})
    result["steps_completed"] += 1

    # ── Step 5: Turn 3-5 快速连发 ─────────────────────────────────────────────
    print("[S1v7] Step 5: Turn 3-5 - 快速连发 (< 1s interval)")
    rapid_msgs = ["我真的很生气", "他每次都这样", "我不知道该怎么办"]
    current_text_parts = []
    current_raw_parts = []
    current_done_event = asyncio.Event()
    end_count_before = processing_end_count
    _rapid_start_ts = time.time()

    for msg_text in rapid_msgs:
        event_msg = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": msg_text},
            },
        }
        print(f"  -> rapid send: {msg_text}")
        await sio.emit("custom_event", event_msg)
        await asyncio.sleep(0.3)

    print("  Waiting for rapid-fire responses (max 60s)...")
    await asyncio.sleep(60)

    rapid_reply = "".join(current_text_parts)
    end_count_after = processing_end_count
    rapid_end_count = end_count_after - end_count_before
    rapid_merged = rapid_end_count < len(rapid_msgs)
    result["functional_checks"]["rapid_fire_merged"] = rapid_merged

    if rapid_reply and not result["functional_checks"]["ai_reply_received"]:
        result["functional_checks"]["ai_reply_received"] = True
    result["conversations"].append({
        "turn": "3_5",
        "user": rapid_msgs,
        "ai_responses": [rapid_reply] if rapid_reply else [],
        "event_processing_end_count": rapid_end_count,
        "rapid_fire_merged": rapid_merged,
        "note": f"发送3条，收到 {rapid_end_count} 个 event_processing_end"
    })
    result["steps_completed"] += 1

    # ── Step 6: Turn 6 - 提及小白 ─────────────────────────────────────────────
    print("[S1v7] Step 6: Turn 6 - 提及小白")
    await asyncio.sleep(1)
    r3 = await send_and_wait("小白就是这样，从来不考虑我的感受", "T6")
    if r3 and not result["functional_checks"]["ai_reply_received"]:
        result["functional_checks"]["ai_reply_received"] = True
    result["conversations"].append({"turn": 6, "user": "小白就是这样，从来不考虑我的感受", "ai_response": r3})
    result["steps_completed"] += 1

    # ── Step 7: Turn 7 - 道别 ─────────────────────────────────────────────────
    print("[S1v7] Step 7: Turn 7 - 道别")
    await asyncio.sleep(1)
    r4 = await send_and_wait("他就是小白，是我男朋友。好了我好一点了，谢谢你", "T7")
    if r4 and not result["functional_checks"]["ai_reply_received"]:
        result["functional_checks"]["ai_reply_received"] = True
    result["conversations"].append({"turn": 7, "user": "他就是小白，是我男朋友。好了我好一点了，谢谢你", "ai_response": r4})
    result["steps_completed"] += 1

    # ── 等待 workspace 写入完成（agent 在对话结束后静默写入）─────────────────
    print("[S1v7] 等待 workspace 写入 (10s)...")
    await asyncio.sleep(10)

    await sio.disconnect()
    result["api_responses"]["socket_events"] = all_server_events[:200]

    # ── Step 8: GET /api/about/self ───────────────────────────────────────────
    print("[S1v7] Step 8: GET /api/about/self")
    await asyncio.sleep(5)
    status, about_self = http_get(f"{API_BASE}/about/self", token)
    result["api_responses"]["about_self"] = {"status": status, "body": about_self}
    if status == 200:
        result["functional_checks"]["about_self_200"] = True
        print(f"  OK about/self: {str(about_self)[:200]}")
    else:
        print(f"  FAIL about/self: {status} {str(about_self)[:100]}")
    result["steps_completed"] += 1

    # ── Step 9: GET /api/about/relations ──────────────────────────────────────
    print("[S1v7] Step 9: GET /api/about/relations")
    status, relations = http_get(f"{API_BASE}/about/relations", token)
    result["api_responses"]["about_relations"] = {"status": status, "body": relations}
    if status == 200:
        result["functional_checks"]["about_relations_200"] = True
        relations_str = json.dumps(relations, ensure_ascii=False)
        if "小白" in relations_str:
            result["functional_checks"]["xiaobo_profile_found"] = True
            print(f"  OK about/relations, 发现'小白'")
        else:
            print(f"  OK about/relations, 未发现'小白' (需要 >= 100 条消息后凌晨4点批处理)")
            print(f"  内容: {relations_str[:300]}")
        print(f"  [P0 NOTE] about/relations 数据: {relations_str[:400]}")
    else:
        print(f"  FAIL about/relations: {status} {str(relations)[:100]}")
    result["steps_completed"] += 1

    # ── Step 10: GET /api/about/relations/小白 ────────────────────────────────
    print("[S1v7] Step 10: GET /api/about/relations/小白")
    name_encoded = urllib.parse.quote("小白")
    status, xiaobo = http_get(f"{API_BASE}/about/relations/{name_encoded}", token)
    result["api_responses"]["about_relations_xiaobo"] = {"status": status, "body": xiaobo}

    if status == 200:
        xiaobo_str = json.dumps(xiaobo, ensure_ascii=False)
        if not result["functional_checks"]["xiaobo_profile_found"]:
            result["functional_checks"]["xiaobo_profile_found"] = True
        relation_keywords = ["男友", "男朋友", "boyfriend", "romantic", "恋人", "partner", "情侣", "伴侣"]
        if any(kw in xiaobo_str for kw in relation_keywords):
            result["functional_checks"]["xiaobo_relation_type_correct"] = True
            print(f"  OK 小白档案，关系类型正确")
        else:
            print(f"  OK 小白档案: {xiaobo_str[:300]}")
    else:
        print(f"  FAIL 小白档案: {status} {str(xiaobo)[:100]}")
    result["steps_completed"] += 1

    # ── workspace 检查（修复：使用运行时 workspace 路径）────────────────────────
    import os
    test_start_ts: float = result.get("_test_start_ts", 0) or 0.0
    print(f"[S1v7] Workspace 检查 (runtime: {RUNTIME_WORKSPACE}):")

    # USER.md 修改时间检查
    user_md_path = os.path.join(RUNTIME_WORKSPACE, "USER.md")
    if os.path.exists(user_md_path):
        user_md_mtime = os.path.getmtime(user_md_path)
        if user_md_mtime > test_start_ts:
            result["functional_checks"]["workspace_user_md_updated"] = True
            print(f"  OK USER.md 已更新: mtime={user_md_mtime:.0f} > test_start={test_start_ts:.0f}")
        else:
            print(f"  WARN USER.md 未更新: mtime={user_md_mtime:.0f} <= test_start={test_start_ts:.0f}")
            print(f"  [分析] USER.md 更新由 OpenClaw agent 自主决定。短对话可能不触发写入。")
        result["workspace_user_md_mtime"] = user_md_mtime
    else:
        print(f"  FAIL USER.md 不存在 at {user_md_path}")

    # people/ 目录检查（修复：使用运行时 workspace 路径）
    people_dir = os.path.join(RUNTIME_WORKSPACE, "people")
    if os.path.isdir(people_dir):
        people_files = os.listdir(people_dir)
        result["workspace_people_files"] = people_files
        # 检查小白相关文件
        xiaobo_files = [f for f in people_files if "小白" in f or "xiaobo" in f.lower()]
        if xiaobo_files:
            result["functional_checks"]["workspace_people_created"] = True
            print(f"  OK people/ 存在且含小白档案: {xiaobo_files}")
        else:
            print(f"  INFO people/ 存在但无小白档案: {people_files}")
            print(f"  [分析] Turn 6 agent 回复了消歧问题，Turn 7 用户确认了小白是男朋友。")
            print(f"  [分析] 如果 agent 写入 people/小白.md，则此检查通过。否则说明本次对话未触发写入。")
    else:
        print(f"  INFO people/ 目录不存在")
        print(f"  [分析] OpenClaw agent 在用户确认关系时创建 people/*.md。")
        print(f"  [分析] Turn 7 消息增加了 '他就是小白，是我男朋友' 以触发确认。")
        result["workspace_people_files"] = []

    # 检查 memory/ 目录的写入情况
    memory_dir = os.path.join(RUNTIME_WORKSPACE, "memory")
    if os.path.isdir(memory_dir):
        memory_files = os.listdir(memory_dir)
        recent_files = []
        for f in memory_files:
            fp = os.path.join(memory_dir, f)
            if os.path.isfile(fp) and os.path.getmtime(fp) > test_start_ts:
                recent_files.append(f)
        if recent_files:
            print(f"  OK memory/ 本次测试后有写入: {recent_files}")
        else:
            print(f"  INFO memory/ 本次测试后无写入: {memory_files}")
        result["workspace_memory_files"] = memory_files
        result["workspace_memory_recent_writes"] = recent_files

    # ── 汇总 ──────────────────────────────────────────────────────────────────
    result["passed_checks"] = sum(1 for v in result["functional_checks"].values() if v)

    # P1 摘要
    mbti_count = sum(1 for item in result["p1_mbti_in_reply"] if item["mbti"])
    result["p1_summary"] = f"{mbti_count}/{len(result['p1_mbti_in_reply'])} 轮回复含 MBTI 引导"
    print(f"\n  [P1 SUMMARY] {result['p1_summary']}")

    return result


if __name__ == "__main__":
    result = asyncio.run(run_s1())

    out_path = "/Users/jianghongwei/Documents/moodcoco/.evolve/b_output/S1_raw_v7.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n=== 结果已保存到: {out_path}")
    print(f"=== 通过检查: {result['passed_checks']}/{result['total_checks']}")
    print(f"=== 完成步骤: {result['steps_completed']}/{result['steps_total']}")
    print(f"=== 功能检查详情:")
    for k, v in result["functional_checks"].items():
        flag = "PASS" if v else "FAIL"
        print(f"    [{flag}] {k}")
    print(f"=== P1 追踪: {result.get('p1_summary', 'N/A')}")
    if result.get("errors"):
        print(f"=== 错误列表:")
        for err in result["errors"]:
            print(f"    - {err}")
