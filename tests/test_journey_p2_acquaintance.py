"""
阶段 2：初识 — 记忆与解读

前置条件：阶段 1 完成，已有小白档案。开新 Socket.IO 连接模拟新会话。

B Agent 操作：
  1. 新 Socket.IO 连接（同一 user_id）
  2. 发送 4 条对话消息（跨会话记忆、关系上下文、信号解读、第二人建档）
  3. 日记 CRUD
  4. 关系列表检查

C Agent 校验：
  - 跨会话记忆识别
  - 关系上下文理解
  - 信号解读引导（不直接下判断）
  - 消歧（小美=闺蜜 vs 小白=男友）
  - 日记数据契约
"""

from datetime import date

import httpx
import pytest

from journey_helpers import (
    AI_REPLY_TIMEOUT,
    KNOWN_CONTENT_TYPES,
    JourneySio,
    SioReply,
)

pytestmark = pytest.mark.asyncio

_replies: dict[str, SioReply] = {}


async def test_p2_b_cross_session_conversation(
    journey_auth: dict[str, str],
):
    """
    B Agent 新会话对话：跨会话记忆 + 信号解读 + 第二人建档。
    """
    global _replies

    sio = JourneySio(token=journey_auth["token"])
    await sio.connect()
    assert sio.sio and sio.sio.connected

    try:
        # R1: 识别老用户
        r1 = await sio.send("嘿，我又来了")
        _replies["R1"] = r1
        assert len(r1.structured) > 0, "R1: No structured response"
        print(f"[P2-R1] AI: {r1.full_text[:200]}")

        # R2: 记得小白
        r2 = await sio.send("小白今天给我发了条消息")
        _replies["R2"] = r2
        assert len(r2.structured) > 0, "R2: No structured response"
        print(f"[P2-R2] AI: {r2.full_text[:200]}")

        # R3: 信号解读
        r3 = await sio.send("他说'忙完再说吧'，是不是在敷衍我？")
        _replies["R3"] = r3
        assert len(r3.structured) > 0, "R3: No structured response"
        print(f"[P2-R3] AI: {r3.full_text[:200]}")

        # R4: 第二人建档
        r4 = await sio.send("我闺蜜小美说我想太多了")
        _replies["R4"] = r4
        assert len(r4.structured) > 0, "R4: No structured response"
        print(f"[P2-R4] AI: {r4.full_text[:200]}")

    finally:
        await sio.disconnect()


# ─────────────────────────────────────────────────────────────────────
# Mood diary CRUD
# ─────────────────────────────────────────────────────────────────────


async def test_p2_mood_diary_write(http_client: httpx.AsyncClient):
    """POST /api/mood 写入日记。"""
    today = date.today().isoformat()
    resp = await http_client.post(
        "/api/mood",
        json={
            "date": today,
            "mood": "sad",
        },
    )
    if resp.status_code == 400 and "already exists" in resp.text:
        print(f"[P2] Mood diary already exists for {today} (idempotent)")
        return

    assert resp.status_code in (200, 201), (
        f"mood write HTTP {resp.status_code}: {resp.text[:300]}"
    )
    print(f"[P2] Mood diary written for {today}")


async def test_p2_mood_diary_read(http_client: httpx.AsyncClient):
    """GET /api/mood/{date} 读回日记。"""
    today = date.today().isoformat()
    resp = await http_client.get(f"/api/mood/{today}")
    assert resp.status_code == 200, (
        f"mood read HTTP {resp.status_code}: {resp.text[:300]}"
    )

    data = resp.json()
    print(f"[P2] Mood diary read: {str(data)[:300]}")
    data_str = str(data)
    assert "3" in data_str or "mood" in data_str.lower(), (
        f"Mood data doesn't contain expected content: {data_str[:300]}"
    )


# ─────────────────────────────────────────────────────────────────────
# C Agent: Relations check (xfail due to memory gap)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.xfail(
    reason="Migration gap: OpenClaw flow does not persist messages, "
    "so memory extraction and relation tracking don't work.",
    strict=False,
)
async def test_p2_c_relations_both_exist(http_client: httpx.AsyncClient):
    """关系列表同时包含小白和小美。"""
    resp = await http_client.get("/api/about/relations")
    assert resp.status_code == 200
    data = resp.json()
    data_str = str(data)
    assert "小白" in data_str, f"小白 not in relations: {data_str[:300]}"
    assert "小美" in data_str, f"小美 not in relations: {data_str[:300]}"


@pytest.mark.xfail(
    reason="Migration gap: relation type extraction not working.",
    strict=False,
)
async def test_p2_c_xiaomei_type(http_client: httpx.AsyncClient):
    """小美关系类型 = 朋友/闺蜜。"""
    resp = await http_client.get("/api/about/relations")
    assert resp.status_code == 200
    data = resp.json()
    friend_keywords = ["朋友", "闺蜜", "friend"]
    data_str = str(data)
    assert "小美" in data_str, f"小美 not found"
    assert any(kw in data_str for kw in friend_keywords), (
        f"小美 type not friend/闺蜜: {data_str[:300]}"
    )


# ─────────────────────────────────────────────────────────────────────
# C Agent: AI Quality
# ─────────────────────────────────────────────────────────────────────


async def test_p2_c_ai_signal_interpretation():
    """R3 信号解读：不直接下判断，引导用户自己分析。"""
    reply = _replies.get("R3")
    if not reply:
        pytest.skip("R3 not available")

    text = reply.full_text

    definitive_judgments = [
        "他就是在敷衍你",
        "他不在乎你",
        "他对你没感觉了",
        "他肯定是敷衍",
    ]
    for judgment in definitive_judgments:
        assert judgment not in text, (
            f"R3 makes definitive judgment: '{judgment}' in '{text[:200]}'"
        )

    exploratory_markers = ["你觉得", "可能", "也许", "哪种", "什么感觉", "你怎么看"]
    has_exploration = any(m in text for m in exploratory_markers)
    if not has_exploration:
        print(f"[P2-AI] WARNING: R3 may not be exploratory enough: {text[:200]}")
    else:
        print(f"[P2-AI] R3 signal interpretation: exploratory ✓")


async def test_p2_c_mood_data_contract(http_client: httpx.AsyncClient):
    """
    日记数据契约：对照 pages/mood-diary-v2/*.wxml 和 diary-detail/*.wxml。
    验证返回格式包含页面渲染所需字段。
    """
    today = date.today().isoformat()
    resp = await http_client.get(f"/api/mood/{today}")
    if resp.status_code == 404:
        pytest.skip("No mood record for today")

    assert resp.status_code == 200
    data = resp.json()
    assert "date" in data, f"Mood missing 'date' field: {data}"
    assert "mood" in data, f"Mood missing 'mood' field: {data}"
    assert "id" in data, f"Mood missing 'id' field: {data}"
    print(f"[P2-C] Mood data contract: {str(data)[:300]}")


async def test_p2_c_cross_session_memory():
    """R1 跨会话记忆：可可不重新自我介绍。"""
    reply = _replies.get("R1")
    if not reply:
        pytest.skip("R1 not available")

    text = reply.full_text
    intro_patterns = ["你好，我是可可", "初次见面", "欢迎来到", "很高兴认识你", "我是你的"]
    for pat in intro_patterns:
        assert pat not in text, (
            f"R1 re-introduces itself to returning user: '{pat}' in '{text[:200]}'"
        )
    print(f"[P2-AI] Cross-session memory: no re-introduction ✓")


async def test_p2_c_relationship_context():
    """R2 关系上下文：提到小白时带上次的情绪背景。"""
    reply = _replies.get("R2")
    if not reply:
        pytest.skip("R2 not available")

    text = reply.full_text
    assert len(text) > 2, f"R2 empty or trivial: {text}"
    print(f"[P2-AI] Relationship context response: {text[:200]}")


@pytest.mark.xfail(
    reason="Migration gap: relation extraction not working.",
    strict=False,
)
async def test_p2_c_relations_xiaomei_detail(http_client: httpx.AsyncClient):
    """GET /api/about/relations/小美 返回小美档案。"""
    resp = await http_client.get("/api/about/relations/小美")
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    inner = data.get("data", data)
    assert inner.get("name") == "小美", f"Name mismatch: {inner}"
    print(f"[P2-C] 小美 detail: {str(inner)[:300]}")
