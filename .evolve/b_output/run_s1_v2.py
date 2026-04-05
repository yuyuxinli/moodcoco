#!/usr/bin/env python3
"""
S1: 陌生人 — 首次接触 (v2)
修正后的 Socket.IO 事件监听逻辑
服务器事件名: event_response / event_processing_end
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
        print(f"  OK Auth: user_id={result['user_id']}")
        result["steps_completed"] += 1
    else:
        result["errors"].append(f"Auth failed: {status} {auth_resp}")
        print(f"  FAIL Auth: {status}")
        return result

    token = result["auth_token"]
    user_id = result["user_id"]
    session_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())

    # ── Step 2: 连接 Socket.IO ────────────────────────────────────────────────
    print("[S1] Step 2: 连接 Socket.IO")

    sio = socketio.AsyncClient(
        reconnection=False,
        logger=False,
        engineio_logger=False,
    )

    socket_connected = False
    connection_error = None

    # 用于收集当前轮回复
    current_content_parts = []
    current_done_event = asyncio.Event()
    processing_end_count = 0  # 统计 event_processing_end 次数（用于快速连发检测）

    # 存储所有收到的服务器事件
    all_server_events = []

    @sio.event
    async def connect():
        nonlocal socket_connected
        socket_connected = True
        print("  OK Socket.IO connected")

    @sio.event
    async def connect_error(data):
        nonlocal connection_error
        connection_error = str(data)
        print(f"  FAIL connect_error: {data}")

    @sio.event
    async def disconnect():
        print("  Socket.IO disconnected")

    @sio.on("event_response")
    async def on_event_response(data):
        """服务器流式内容块"""
        try:
            payload = data.get("payload", data) if isinstance(data, dict) else {}
            stream_data = payload.get("stream_data", "")
            if stream_data:
                current_content_parts.append(stream_data)
            # 记录事件
            all_server_events.append({
                "event": "event_response",
                "ts": time.time(),
                "stream_id": payload.get("stream_id"),
                "data_len": len(stream_data) if stream_data else 0,
            })
        except Exception as e:
            print(f"  [warn] on_event_response error: {e}")

    @sio.on("event_processing_end")
    async def on_event_processing_end(data):
        """流式输出结束"""
        nonlocal processing_end_count
        processing_end_count += 1
        all_server_events.append({
            "event": "event_processing_end",
            "ts": time.time(),
            "count": processing_end_count,
        })
        current_done_event.set()
        print(f"  <- event_processing_end #{processing_end_count}")

    @sio.on("message")
    async def on_message(data):
        """非流式消息"""
        try:
            if isinstance(data, str):
                data = json.loads(data)
            content = data.get("content", "") or data.get("text", "") or str(data)
            if content and content not in ["null", "{}"]:
                current_content_parts.append(content)
        except Exception:
            pass
        current_done_event.set()

    @sio.on("error")
    async def on_error(data):
        print(f"  [server error] {data}")
        all_server_events.append({"event": "error", "data": str(data), "ts": time.time()})
        current_done_event.set()  # unblock waiter on error

    # 捕获所有未知事件（调试用）
    @sio.on("*")
    async def on_any(event, data):
        if event not in ("event_response", "event_processing_end", "message", "error",
                         "connect", "disconnect", "connect_error"):
            all_server_events.append({"event": event, "ts": time.time()})

    # 连接 Socket.IO（token 作为 query 参数传递，与前端代码保持一致）
    query_params = {
        "session_id": session_id,
        "client_id": client_id,
        "character_id": "linyu",
        "timezone_offset": "8",
        "session_type": "chat",
        "token": token,
    }
    query_string = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in query_params.items())

    try:
        await sio.connect(
            BASE_URL,
            socketio_path="/socket.io/",
            transports=["websocket"],
            wait_timeout=15,
            headers={"Authorization": f"Bearer {token}"},
        )
        if socket_connected:
            result["functional_checks"]["socket_connected"] = True
            result["steps_completed"] += 1
    except Exception as e:
        result["errors"].append(f"Socket.IO 连接失败 (headers auth): {e}")
        print(f"  [retry] 尝试 query params 认证")
        try:
            await sio.connect(
                f"{BASE_URL}?{query_string}",
                socketio_path="/socket.io/",
                transports=["websocket"],
                wait_timeout=15,
            )
            if socket_connected:
                result["functional_checks"]["socket_connected"] = True
                result["steps_completed"] += 1
        except Exception as e2:
            result["errors"].append(f"Socket.IO 连接失败 (query auth): {e2}")
            print(f"  FAIL Socket.IO: {e2}")

    if not socket_connected:
        print("  [fallback] Socket.IO 不可用，记录失败状态")
        result["api_responses"]["socket_events"] = all_server_events
        return result

    # ── 发送消息帮助函数 ──────────────────────────────────────────────────────
    async def send_and_wait(text, label, wait_sec=45):
        """发送一条消息并等待 AI 回复完成"""
        nonlocal current_content_parts, current_done_event
        current_content_parts = []
        current_done_event = asyncio.Event()

        msg = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": text},
            },
        }
        print(f"  -> send({label}): {text[:50]}")
        await sio.emit("custom_event", msg)

        try:
            await asyncio.wait_for(current_done_event.wait(), timeout=wait_sec)
        except asyncio.TimeoutError:
            print(f"  [timeout] {label} 等待超时 {wait_sec}s")

        full_reply = "".join(current_content_parts)
        preview = (full_reply[:100] + "...") if len(full_reply) > 100 else full_reply
        print(f"  <- reply({label}): {preview or '[empty]'}")
        return full_reply

    # ── Step 3: Turn 1 ────────────────────────────────────────────────────────
    print("[S1] Step 3: Turn 1 - 初次倾诉")
    await asyncio.sleep(1)
    r1 = await send_and_wait("我刚跟男朋友吵了一架，好烦", "T1")
    if r1:
        result["functional_checks"]["ai_reply_received"] = True
    result["conversations"].append({
        "turn": 1,
        "user": "我刚跟男朋友吵了一架，好烦",
        "ai_response": r1,
    })
    result["steps_completed"] += 1

    # ── Step 4: Turn 2 ────────────────────────────────────────────────────────
    print("[S1] Step 4: Turn 2 - 被说太敏感")
    await asyncio.sleep(1)
    r2 = await send_and_wait("他说我太敏感了，每次都这样说我", "T2")
    result["conversations"].append({
        "turn": 2,
        "user": "他说我太敏感了，每次都这样说我",
        "ai_response": r2,
    })
    result["steps_completed"] += 1

    # ── Step 5: Turn 3-5 快速连发 ─────────────────────────────────────────────
    print("[S1] Step 5: Turn 3-5 - 快速连发 (< 1s interval)")
    rapid_msgs = ["我真的很生气", "他每次都这样", "我不知道该怎么办"]
    current_content_parts = []
    current_done_event = asyncio.Event()
    end_count_before = processing_end_count

    for msg in rapid_msgs:
        event_msg = {
            "event_type": "user_message",
            "payload": {
                "event_name": "send_message",
                "action_payload": {"text": msg},
            },
        }
        print(f"  -> rapid send: {msg}")
        await sio.emit("custom_event", event_msg)
        await asyncio.sleep(0.3)

    # 等待所有回复（最多 60 秒）
    print("  Waiting for rapid-fire responses (max 60s)...")
    await asyncio.sleep(60)

    rapid_reply = "".join(current_content_parts)
    end_count_after = processing_end_count
    rapid_end_count = end_count_after - end_count_before
    # 合并判断：如果 event_processing_end 次数 < 发送数量 = 合并了
    rapid_merged = rapid_end_count < len(rapid_msgs)
    result["functional_checks"]["rapid_fire_merged"] = rapid_merged

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
    print("[S1] Step 6: Turn 6 - 提及小白")
    await asyncio.sleep(1)
    r3 = await send_and_wait("小白就是这样，从来不考虑我的感受", "T6")
    result["conversations"].append({
        "turn": 6,
        "user": "小白就是这样，从来不考虑我的感受",
        "ai_response": r3,
    })
    result["steps_completed"] += 1

    # ── Step 7: Turn 7 - 道别 ─────────────────────────────────────────────────
    print("[S1] Step 7: Turn 7 - 道别")
    await asyncio.sleep(1)
    r4 = await send_and_wait("好了我好一点了，谢谢你", "T7")
    result["conversations"].append({
        "turn": 7,
        "user": "好了我好一点了，谢谢你",
        "ai_response": r4,
    })
    result["steps_completed"] += 1

    await sio.disconnect()

    # 保存 Socket 事件记录
    result["api_responses"]["socket_events"] = all_server_events[:100]

    # ── Step 8: GET /api/about/self ───────────────────────────────────────────
    print("[S1] Step 8: GET /api/about/self")
    await asyncio.sleep(3)
    status, about_self = http_get(f"{API_BASE}/about/self", token)
    result["api_responses"]["about_self"] = {"status": status, "body": about_self}
    if status == 200:
        result["functional_checks"]["about_self_200"] = True
        print(f"  OK about/self")
    else:
        print(f"  FAIL about/self: {status} {str(about_self)[:100]}")
    result["steps_completed"] += 1

    # ── Step 9: GET /api/about/relations ──────────────────────────────────────
    print("[S1] Step 9: GET /api/about/relations")
    status, relations = http_get(f"{API_BASE}/about/relations", token)
    result["api_responses"]["about_relations"] = {"status": status, "body": relations}
    if status == 200:
        result["functional_checks"]["about_relations_200"] = True
        relations_str = json.dumps(relations, ensure_ascii=False)
        if "小白" in relations_str:
            result["functional_checks"]["xiaobo_profile_found"] = True
            print(f"  OK about/relations, 发现'小白'")
        else:
            print(f"  OK about/relations, 未发现'小白' (内容: {relations_str[:200]})")
    else:
        print(f"  FAIL about/relations: {status} {str(relations)[:100]}")
    result["steps_completed"] += 1

    # ── Step 10: GET /api/about/relations/小白 ────────────────────────────────
    print("[S1] Step 10: GET /api/about/relations/小白")
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
            print(f"  OK 小白档案，但未识别关系类型: {xiaobo_str[:200]}")
    else:
        print(f"  FAIL 小白档案: {status} {str(xiaobo)[:100]}")
    result["steps_completed"] += 1

    # ── 汇总 ──────────────────────────────────────────────────────────────────
    result["passed_checks"] = sum(1 for v in result["functional_checks"].values() if v)
    return result


if __name__ == "__main__":
    result = asyncio.run(run_s1())
    out_path = "/Users/jianghongwei/Documents/moodcoco/.evolve/b_output/S1_raw.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n=== 结果已保存到: {out_path}")
    print(f"=== 通过检查: {result['passed_checks']}/{result['total_checks']}")
    print(f"=== 完成步骤: {result['steps_completed']}/{result['steps_total']}")
    print(f"=== 功能检查详情:")
    for k, v in result["functional_checks"].items():
        status = "PASS" if v else "FAIL"
        print(f"      [{status}] {k}")
