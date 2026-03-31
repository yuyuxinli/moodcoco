#!/usr/bin/env python3
"""循环叹息引导 —— 单 WebSocket 连接版，消除 CLI 启动开销。

用法: breathe-fast.py <channel> [cycles]
示例: breathe-fast.py feishu 3
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import websocket
except ImportError:
    print(
        "错误：缺少 websocket-client 库，请运行 pip3 install websocket-client",
        file=sys.stderr,
    )
    sys.exit(1)

# --- 参数 ---
if len(sys.argv) < 2:
    print("用法: breathe-fast.py <channel> [cycles]")
    sys.exit(1)

CHANNEL = sys.argv[1]
CYCLES = int(sys.argv[2]) if len(sys.argv) > 2 else 3
DRY_RUN = bool(os.environ.get("DRY_RUN"))

# --- 从 sessions.json 找 target ---
sessions_path = Path.home() / ".openclaw/agents/coco/sessions/sessions.json"
target: str | None = None
account: str | None = None
if not DRY_RUN:
    with sessions_path.open() as f:
        sessions = json.load(f)
    best: dict[str, Any] | None = None
    best_ts: int = 0
    for val in sessions.values():
        if isinstance(val, dict) and val.get("lastChannel") == CHANNEL:
            ts = int(val.get("updatedAt", 0))
            if ts > best_ts:
                best, best_ts = val, ts
    if not best or not best.get("lastTo"):
        print(f"错误：找不到 channel={CHANNEL} 的 target", file=sys.stderr)
        sys.exit(1)
    target = best["lastTo"]
    account = best.get("lastAccountId", "")

# --- 连接 gateway WebSocket ---
ws: websocket.WebSocket | None = None
if not DRY_RUN:
    config_path = Path.home() / ".openclaw/openclaw.json"
    with config_path.open() as f:
        config = json.load(f)
    port = config["gateway"]["port"]
    token = config["gateway"]["auth"]["token"]

    ws = websocket.create_connection(
        f"ws://127.0.0.1:{port}",
        timeout=10,
    )

    # 收 challenge
    _challenge = json.loads(ws.recv())

    # 发 connect + auth
    connect_id = str(uuid.uuid4())
    ws.send(
        json.dumps(
            {
                "type": "req",
                "id": connect_id,
                "method": "connect",
                "params": {
                    "minProtocol": 3,
                    "maxProtocol": 3,
                    "client": {
                        "id": "gateway-client",
                        "version": "1.0.0",
                        "platform": "node",
                        "mode": "backend",
                    },
                    "role": "operator",
                    "scopes": [
                        "operator.admin",
                        "operator.read",
                        "operator.write",
                        "operator.approvals",
                        "operator.pairing",
                    ],
                    "auth": {"token": token},
                },
            }
        )
    )
    # 等待 connect 响应，跳过事件消息
    resp: dict[str, Any] = {}
    while True:
        resp = json.loads(ws.recv())
        if resp.get("type") == "res" and resp.get("id") == connect_id:
            break
    if not resp.get("ok", False):
        print(f"认证失败: {resp}", file=sys.stderr)
        sys.exit(1)


def recv_response(req_id: str) -> dict[str, Any]:
    """接收响应，跳过 gateway 推送的事件消息（如 health）。"""
    assert ws is not None, "WebSocket 未连接"
    while True:
        msg: dict[str, Any] = json.loads(ws.recv())
        if msg.get("type") == "res" and msg.get("id") == req_id:
            return msg
        # 跳过事件和其他非响应消息


def send(text: str) -> None:
    if DRY_RUN:
        print(f"[{time.strftime('%H:%M:%S')}] {text}")
        return
    assert ws is not None, "WebSocket 未连接"
    req_id = str(uuid.uuid4())
    frame: dict[str, Any] = {
        "type": "req",
        "id": req_id,
        "method": "send",
        "params": {
            "to": target,
            "message": text,
            "channel": CHANNEL,
            "idempotencyKey": str(uuid.uuid4()),
        },
    }
    if account:
        frame["params"]["accountId"] = account
    ws.send(json.dumps(frame))
    resp = recv_response(req_id)
    if not resp.get("ok", False):
        err = resp.get("error", {}).get("message", str(resp))
        print(f"发送失败: {err}", file=sys.stderr)
        sys.exit(1)


def send_and_pause(pause_sec: float, text: str) -> None:
    t0 = time.monotonic()
    send(text)
    elapsed = time.monotonic() - t0
    remaining = pause_sec - elapsed
    if remaining > 0.05:
        time.sleep(remaining)


# --- 呼吸引导 ---
send_and_pause(2, "跟我一起，就一个动作。跟着数就行。")

for i in range(1, CYCLES + 1):
    send_and_pause(4, "鼻子吸气，数 4 秒 —— 1、2、3、4")
    send_and_pause(2, "再追一小口，撑满 —— 1、2")
    send_and_pause(8, "嘴巴慢慢吐 …… 8 秒，不急 —— 1、2、3、4、5、6、7、8")
    if i < CYCLES:
        send("再来。")

send_and_pause(1, "好了。")

if ws:
    ws.close()
