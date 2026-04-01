#!/usr/bin/env python3
"""
S1: 陌生人 — 首次接触
B Agent 执行脚本，通过 Socket.IO 模拟真实用户对话，收集原始 API 响应
"""

import asyncio
import json
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timezone
import socketio

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

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
        return e.code, json.loads(e.read().decode()) if e.read else {}
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
        return e.code, json.loads(body_bytes.decode()) if body_bytes else {}
    except Exception as ex:
        return 0, {"error": str(ex)}

# ─── 主测试逻辑 ──────────────────────────────────────────────────────────────

async def run_s1():
    result = {
        "feature": "S1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": None,
        "auth_token": None,
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
        },
        "passed_checks": 0,
        "total_checks": 8,
        "errors": [],
        "steps_completed": 0,
        "steps_total": 10,
    }

    # ── Step 1: 获取 Guest Session Token ─────────────────────────────────────
    print("[S1] Step 1: POST /api/auth/guest/session")
    status, auth_resp = http_post(f"{API_BASE}/auth/guest/session")
    result["api_responses"]["auth"] = {"status": status, "body": auth_resp}

    if status == 200:
        result["functional_checks"]["auth_200"] = True
        result["user_id"] = auth_resp.get("user_id")
        result["auth_token"] = auth_resp.get("token")
        print(f"  ✓ Auth OK: user_id={result['user_id']}")
        result["steps_completed"] += 1
    else:
        result["errors"].append(f"Auth failed: {status} {auth_resp}")
        print(f"  ✗ Auth failed: {status}")
        # 保存部分结果并退出
        _save_and_exit(result)
        return result

    token = result["auth_token"]
    user_id = result["user_id"]
    session_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())

    # ── Step 2-7: Socket.IO 对话 ──────────────────────────────────────────────
    print("[S1] Step 2: 连接 Socket.IO")

    sio = socketio.AsyncClient(
        reconnection=False,
        logger=False,
        engineio_logger=False,
    )

    conversations = []
    socket_connected = False
    connection_error = None

    # 存放每轮对话收集到的流内容
    current_turn_content = []
    current_turn_event = asyncio.Event()
    stream_done = asyncio.Event()

    @sio.event
    async def connect():
        nonlocal socket_connected
        socket_connected = True
        print("  ✓ Socket.IO 连接成功")

    @sio.event
    async def connect_error(data):
        nonlocal connection_error
        connection_error = str(data)
        print(f"  ✗ 连接失败: {data}")

    @sio.event
    async def disconnect():
        print("  Socket.IO 断开连接")

    # 监听服务器的 stream_response 事件（流式内容块）
    @sio.on("stream_response")
    async def on_stream_response(data):
        try:
            if isinstance(data, str):
                data = json.loads(data)
            content = data.get("content", "") or data.get("delta", "") or ""
            if content:
                current_turn_content.append(content)
        except Exception as e:
            pass

    # 监听 stream_complete 事件
    @sio.on("stream_complete")
    async def on_stream_complete(data):
        stream_done.set()
        current_turn_event.set()

    # 监听 message 事件（非流式回复）
    @sio.on("message")
    async def on_message(data):
        try:
            if isinstance(data, str):
                data = json.loads(data)
            content = data.get("content", "") or data.get("text", "") or str(data)
            current_turn_content.append(content)
        except Exception:
            pass
        current_turn_event.set()

    # 监听所有事件（调试用）
    received_events = []

    @sio.on("*")
    async def on_any_event(event, data):
        received_events.append({"event": event, "data": data, "ts": time.time()})

    # 连接 Socket.IO
    query_params = {
        "session_id": session_id,
        "client_id": client_id,
        "character_id": "linyu",
        "timezone_offset": "8",
        "session_type": "chat",
        "token": token,
    }
    query_string = "&".join(f"{k}={v}" for k, v in query_params.items())

    try:
        await sio.connect(
            BASE_URL,
            socketio_path="/socket.io/",
            transports=["websocket"],
            wait_timeout=15,
            auth={"token": token},
        )
        result["functional_checks"]["socket_connected"] = True
        result["steps_completed"] += 1
    except Exception as e:
        # 尝试带 query params 的方式
        try:
            await sio.connect(
                f"{BASE_URL}?{query_string}",
                socketio_path="/socket.io/",
                transports=["websocket"],
                wait_timeout=15,
            )
            result["functional_checks"]["socket_connected"] = True
            result["steps_completed"] += 1
        except Exception as e2:
            result["errors"].append(f"Socket.IO 连接失败: {e2}")
            print(f"  ✗ Socket.IO 连接失败: {e2}")
            socket_connected = False

    if not socket_connected:
        # 回退：尝试通过 HTTP REST API 发送消息
        print("  [fallback] 尝试通过 HTTP /api/events-socketio/message 发送消息")
        await _run_http_fallback(result, token, session_id)
        _save_result(result)
        return result

    async def send_message_and_wait(text, turn_label, wait_timeout=45):
        """发送消息并等待完整 AI 回复"""
        nonlocal current_turn_content, current_turn_event, stream_done
        current_turn_content = []
        current_turn_event = asyncio.Event()
        stream_done = asyncio.Event()

        event_message = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": text},
            },
        }

        print(f"  → 发送({turn_label}): {text[:40]}")
        await sio.emit("custom_event", event_message)

        # 等待回复（最多 wait_timeout 秒）
        try:
            await asyncio.wait_for(current_turn_event.wait(), timeout=wait_timeout)
        except asyncio.TimeoutError:
            pass

        # 额外等待流完成
        if current_turn_content and not stream_done.is_set():
            try:
                await asyncio.wait_for(stream_done.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass

        full_reply = "".join(current_turn_content)
        print(f"  ← 回复({turn_label}): {full_reply[:80]}..." if len(full_reply) > 80 else f"  ← 回复({turn_label}): {full_reply}")
        return full_reply

    if socket_connected:
        # ── Step 3: Turn 1 ──────────────────────────────────────────────────
        print("[S1] Step 3: Turn 1 - 初次倾诉")
        await asyncio.sleep(1)
        r1 = await send_message_and_wait("我刚跟男朋友吵了一架，好烦", "T1")
        if r1:
            result["functional_checks"]["ai_reply_received"] = True
        conversations.append({
            "turn": 1,
            "user": "我刚跟男朋友吵了一架，好烦",
            "ai_response": r1,
        })
        result["steps_completed"] += 1

        # ── Step 4: Turn 2 ──────────────────────────────────────────────────
        print("[S1] Step 4: Turn 2 - 被说太敏感")
        await asyncio.sleep(1)
        r2 = await send_message_and_wait("他说我太敏感了，每次都这样说我", "T2")
        conversations.append({
            "turn": 2,
            "user": "他说我太敏感了，每次都这样说我",
            "ai_response": r2,
        })
        result["steps_completed"] += 1

        # ── Step 5: Turn 3-5 快速连发 ────────────────────────────────────────
        print("[S1] Step 5: Turn 3-5 - 快速连发（间隔 < 1秒）")
        rapid_messages = ["我真的很生气", "他每次都这样", "我不知道该怎么办"]
        rapid_responses = []

        # 快速连发（不等每条回复）
        for msg in rapid_messages:
            event_message = {
                "event_type": "user_message",
                "payload": {
                    "event_name": "send_message",
                    "action_payload": {"text": msg},
                },
            }
            await sio.emit("custom_event", event_message)
            await asyncio.sleep(0.3)  # < 1秒间隔

        # 等待所有回复（最多 60 秒）
        print("  等待快速连发的回复...")
        await asyncio.sleep(60)  # 等待足够时间收集所有回复

        # 收集到目前为止的所有内容
        rapid_collected = "".join(current_turn_content)
        rapid_responses = [rapid_collected] if rapid_collected else []

        # 检查是否合并回复（回复数量 < 发送数量 = 合并）
        # 通过检查收到的 stream_complete 事件数量
        stream_complete_count = sum(
            1 for e in received_events if e.get("event") == "stream_complete"
        )
        result["functional_checks"]["rapid_fire_merged"] = (
            stream_complete_count < len(rapid_messages)
        )

        conversations.append({
            "turn": "3_5",
            "user": rapid_messages,
            "ai_responses": rapid_responses,
            "stream_complete_events": stream_complete_count,
            "rapid_fire_merged": result["functional_checks"]["rapid_fire_merged"],
        })
        result["steps_completed"] += 1

        # ── Step 6: Turn 6 - 提及小白 ────────────────────────────────────────
        print("[S1] Step 6: Turn 6 - 提及小白")
        current_turn_content = []
        current_turn_event = asyncio.Event()
        stream_done = asyncio.Event()
        await asyncio.sleep(1)
        r3 = await send_message_and_wait("小白就是这样，从来不考虑我的感受", "T6")
        conversations.append({
            "turn": 6,
            "user": "小白就是这样，从来不考虑我的感受",
            "ai_response": r3,
        })
        result["steps_completed"] += 1

        # ── Step 7: Turn 7 - 道别 ────────────────────────────────────────────
        print("[S1] Step 7: Turn 7 - 道别")
        current_turn_content = []
        current_turn_event = asyncio.Event()
        stream_done = asyncio.Event()
        await asyncio.sleep(1)
        r4 = await send_message_and_wait("好了我好一点了，谢谢你", "T7")
        conversations.append({
            "turn": 7,
            "user": "好了我好一点了，谢谢你",
            "ai_response": r4,
        })
        result["steps_completed"] += 1

        await sio.disconnect()

    result["conversations"] = conversations

    # 保存所有 received_events 摘要
    result["socket_events_summary"] = [
        {"event": e["event"], "ts": e["ts"]}
        for e in received_events[:50]  # 最多 50 条
    ]

    # ── Step 8: GET /api/about/self ───────────────────────────────────────────
    print("[S1] Step 8: GET /api/about/self")
    await asyncio.sleep(2)  # 等待后端处理完毕
    status, about_self = http_get(f"{API_BASE}/about/self", token)
    result["api_responses"]["about_self"] = {"status": status, "body": about_self}
    if status == 200:
        result["functional_checks"]["about_self_200"] = True
        print(f"  ✓ about/self OK")
    else:
        print(f"  ✗ about/self: {status} {about_self}")
    result["steps_completed"] += 1

    # ── Step 9: GET /api/about/relations ─────────────────────────────────────
    print("[S1] Step 9: GET /api/about/relations")
    status, relations = http_get(f"{API_BASE}/about/relations", token)
    result["api_responses"]["about_relations"] = {"status": status, "body": relations}
    if status == 200:
        result["functional_checks"]["about_relations_200"] = True
        print(f"  ✓ about/relations OK")
        # 检查是否含有"小白"
        relations_str = json.dumps(relations, ensure_ascii=False)
        if "小白" in relations_str:
            result["functional_checks"]["xiaobo_profile_found"] = True
            print("  ✓ 发现'小白'档案")
    else:
        print(f"  ✗ about/relations: {status} {relations}")
    result["steps_completed"] += 1

    # ── Step 10: GET /api/about/relations/小白 ────────────────────────────────
    print("[S1] Step 10: GET /api/about/relations/{小白}")
    import urllib.parse
    name_encoded = urllib.parse.quote("小白")
    status, xiaobo = http_get(f"{API_BASE}/about/relations/{name_encoded}", token)
    result["api_responses"]["about_relations_xiaobo"] = {"status": status, "body": xiaobo}

    if status == 200:
        xiaobo_str = json.dumps(xiaobo, ensure_ascii=False)
        if not result["functional_checks"]["xiaobo_profile_found"]:
            result["functional_checks"]["xiaobo_profile_found"] = True
        # 检查关系类型是否正确（男友/恋人等）
        relation_keywords = ["男友", "男朋友", "boyfriend", "romantic", "恋人", "partner", "情侣"]
        if any(kw in xiaobo_str for kw in relation_keywords):
            result["functional_checks"]["xiaobo_relation_type_correct"] = True
        print(f"  ✓ 小白档案: {xiaobo_str[:200]}")
    else:
        print(f"  ✗ 小白档案: {status} {xiaobo}")
    result["steps_completed"] += 1

    # ── 汇总检查结果 ──────────────────────────────────────────────────────────
    result["passed_checks"] = sum(1 for v in result["functional_checks"].values() if v)

    return result


async def _run_http_fallback(result, token, session_id):
    """通过 HTTP REST API 发送消息的降级方案"""
    print("[fallback] 使用 HTTP /api/events-socketio/message 发送消息")

    conversations = []
    messages = [
        "我刚跟男朋友吵了一架，好烦",
        "他说我太敏感了，每次都这样说我",
        "我真的很生气",
        "他每次都这样",
        "我不知道该怎么办",
        "小白就是这样，从来不考虑我的感受",
        "好了我好一点了，谢谢你",
    ]

    for i, msg in enumerate(messages):
        status, resp = http_post(
            f"http://localhost:8000/api/events-socketio/message",
            {"session_id": session_id, "content": msg, "message": msg},
            token,
        )
        print(f"  [HTTP] Turn {i+1}: status={status}, reply={str(resp)[:80]}")
        conversations.append({
            "turn": i + 1,
            "user": msg,
            "ai_response": resp.get("content", resp.get("reply", str(resp))),
            "http_status": status,
        })
        if i == 0 and status == 200:
            result["functional_checks"]["ai_reply_received"] = True
        await asyncio.sleep(2)

    result["conversations"] = conversations


def _save_result(result):
    out_path = "/Users/jianghongwei/Documents/moodcoco/.evolve/b_output/S1_raw.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[S1] 结果已保存到: {out_path}")
    print(f"[S1] 通过检查: {result['passed_checks']}/{result['total_checks']}")
    print(f"[S1] 完成步骤: {result['steps_completed']}/{result['steps_total']}")


def _save_and_exit(result):
    _save_result(result)


if __name__ == "__main__":
    result = asyncio.run(run_s1())
    _save_result(result)
