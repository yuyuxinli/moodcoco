"""
Journey E2E 测试公共 fixtures。

跨阶段共享同一个 guest 用户：
  - 首次运行时创建 guest -> 存到 tests/.journey_state.json
  - 后续阶段读取同一 user_id/token
  - 如果 token 过期，自动重新认证
"""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent))

from journey_helpers import API_BASE, BASE_URL, load_state, save_state


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def journey_state() -> dict:
    """Mutable dict shared across the entire session."""
    return load_state()


@pytest_asyncio.fixture(scope="session")
async def journey_auth(journey_state: dict) -> dict[str, str]:
    """
    Session-scoped guest auth. Reuses stored credentials if valid,
    otherwise creates a new guest.
    """
    token = journey_state.get("token")
    user_id = journey_state.get("user_id")

    if token and user_id:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{API_BASE}/user/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                print(f"\n[fixture] Reusing journey user: {user_id}")
                return {"token": token, "user_id": user_id}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{API_BASE}/auth/guest/session")
        assert resp.status_code == 200, (
            f"Guest auth failed: {resp.status_code} {resp.text}"
        )
        data = resp.json()
        assert "token" in data
        assert "user_id" in data
        journey_state["token"] = data["token"]
        journey_state["user_id"] = data["user_id"]
        save_state(journey_state)
        print(f"\n[fixture] New journey user: {data['user_id']}")
        return {"token": data["token"], "user_id": data["user_id"]}


@pytest_asyncio.fixture(scope="session")
async def http_client(journey_auth: dict[str, str]):
    """Authenticated async HTTP client."""
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=30,
        headers={"Authorization": f"Bearer {journey_auth['token']}"},
    )
    yield client
    await client.aclose()
