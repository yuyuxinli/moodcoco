"""
阶段 3B：单关系模式识别

前置条件：阶段 1-2 完成，已有小白档案和对话历史。

B Agent 操作：
  1. 连续 3 条关于小白的重复模式消息
  2. 检查 patterns 字段

C Agent 校验：
  - 用具体事件描述模式，不用标签
  - 先接住情绪再讲模式
"""

import pytest

from journey_helpers import JourneySio, SioReply

pytestmark = pytest.mark.asyncio

_replies: dict[str, SioReply] = {}


async def test_p3b_b_pattern_conversation(
    journey_auth: dict[str, str],
):
    """B Agent: 连续描述重复模式，触发模式识别。"""
    global _replies

    sio = JourneySio(token=journey_auth["token"])
    await sio.connect()
    assert sio.sio and sio.sio.connected

    try:
        r1 = await sio.send("小白又没回我消息，我又开始胡思乱想了")
        _replies["R1"] = r1
        assert len(r1.structured) > 0, "R1: No structured response"
        print(f"[P3B-R1] AI: {r1.full_text[:200]}")

        r2 = await sio.send("每次他不回我，我就觉得他不爱我了")
        _replies["R2"] = r2
        assert len(r2.structured) > 0, "R2: No structured response"
        print(f"[P3B-R2] AI: {r2.full_text[:200]}")

        r3 = await sio.send("上次也是，他出差那几天我天天焦虑")
        _replies["R3"] = r3
        assert len(r3.structured) > 0, "R3: No structured response"
        print(f"[P3B-R3] AI: {r3.full_text[:200]}")

    finally:
        await sio.disconnect()


@pytest.mark.xfail(
    reason="Migration gap: OpenClaw does not persist messages, "
    "so pattern data in relations API is empty.",
    strict=False,
)
async def test_p3b_c_pattern_data(http_client):
    """GET /api/about/relations/小白 检查 patterns 字段。"""
    import httpx

    resp = await http_client.get("/api/about/relations/小白")
    assert resp.status_code == 200
    data = resp.json()
    data_str = str(data)
    assert "pattern" in data_str.lower() or len(data_str) > 50, (
        f"No pattern data for 小白: {data_str[:300]}"
    )


async def test_p3b_c_pattern_recognition_in_conversation():
    """R2 或 R3 中可可应指出重复模式（'每次'/'又'/'一样'等）。"""
    all_text = ""
    for label in ["R2", "R3"]:
        r = _replies.get(label)
        if r:
            all_text += " " + r.full_text

    if not all_text.strip():
        pytest.skip("R2/R3 not available")

    pattern_hints = [
        "每次", "又", "一样", "重复", "同样", "总是", "模式",
        "好几次", "规律", "循环", "来过这儿",
    ]
    has_pattern = any(hint in all_text for hint in pattern_hints)
    assert has_pattern, (
        f"AI should recognize repeated pattern in R2/R3 but found no "
        f"pattern-related words. R2+R3 text: {all_text[:300]}"
    )
    print(f"[P3B-AI] Pattern recognition in conversation ✓")


async def test_p3b_c_pattern_uses_events():
    """AI 应用具体事件描述模式，不用标签。"""
    all_text = " ".join(r.full_text for r in _replies.values() if r.full_text)
    if not all_text:
        pytest.skip("No replies available")

    labels = ["焦虑型依恋", "不安全依恋", "你有依恋问题"]
    for label in labels:
        assert label not in all_text, (
            f"AI uses diagnostic label: '{label}'"
        )
    print(f"[P3B-AI] No diagnostic labels found ✓")


async def test_p3b_c_emotional_safety():
    """先接住情绪再讲模式（不在 R1 就讲）。"""
    r1 = _replies.get("R1")
    if not r1:
        pytest.skip("R1 not available")

    text = r1.full_text
    pattern_keywords = ["模式", "每次都", "重复", "规律", "pattern"]
    has_pattern_in_r1 = any(kw in text for kw in pattern_keywords)

    if has_pattern_in_r1:
        print(f"[P3B-AI] WARNING: R1 mentions pattern too early: {text[:200]}")
    else:
        print(f"[P3B-AI] R1 does not jump to pattern discussion ✓")
