"""
阶段 4C：告别仪式（可选）

B Agent 操作：
  1. 发送"我想放下小白了"
  2. 检查封存状态

C Agent 校验：
  - 提供仪式形式，不是简单"好的"
  - 告别后小白档案状态变化
"""

import pytest

from journey_helpers import JourneySio, SioReply

pytestmark = pytest.mark.asyncio

_replies: dict[str, SioReply] = {}


async def test_p4c_farewell_initiation(
    journey_auth: dict[str, str],
):
    """发送"我想放下小白了"，验证告别引导。"""
    sio = JourneySio(token=journey_auth["token"])
    await sio.connect()
    assert sio.sio and sio.sio.connected

    try:
        r1 = await sio.send("我想放下小白了")
        _replies["farewell"] = r1
        assert len(r1.structured) > 0, "Farewell: no structured response"

        text = r1.full_text
        assert len(text) > 5, f"Farewell response too short: {text}"

        simple_dismissals = ["好的", "好吧", "ok"]
        is_just_ok = text.strip() in simple_dismissals
        assert not is_just_ok, (
            f"Farewell should provide ceremony/guidance, not just '{text}'"
        )
        print(f"[P4C] Farewell response: {text[:200]}")

    finally:
        await sio.disconnect()


@pytest.mark.xfail(
    reason="Migration gap: archive status depends on memory/relation system.",
    strict=False,
)
async def test_p4c_farewell_archive_status(http_client):
    """检查小白档案封存状态。"""
    import httpx

    resp = await http_client.get("/api/about/relations/小白")
    assert resp.status_code == 200
    data = resp.json()
    data_str = str(data)
    has_archive = any(
        kw in data_str.lower()
        for kw in ["archive", "封存", "archived", "closed"]
    )
    assert has_archive, f"小白 not archived: {data_str[:300]}"
