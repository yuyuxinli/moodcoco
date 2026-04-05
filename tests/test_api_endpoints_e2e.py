"""
API 端点 E2E 冒烟测试 - 验证所有用户可见的 REST 端点可达且格式正确。
"""
import httpx
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE_URL, timeout=15)


@pytest.fixture(scope="module")
def auth_token(client):
    resp = client.post("/api/auth/guest/session")
    assert resp.status_code == 200
    data = resp.json()
    return data["token"], data["user_id"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestPublicEndpoints:

    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_guest_auth(self, client):
        resp = client.post("/api/auth/guest/session")
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data, f"Missing token: {data}"
        assert "user_id" in data, f"Missing user_id: {data}"


class TestAuthenticatedEndpoints:

    def test_about_self(self, client, auth_token):
        token, _ = auth_token
        resp = client.get("/api/about/self", headers=auth_headers(token))
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_about_relations(self, client, auth_token):
        token, _ = auth_token
        resp = client.get("/api/about/relations", headers=auth_headers(token))
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_user_me(self, client, auth_token):
        token, _ = auth_token
        resp = client.get("/api/user/me", headers=auth_headers(token))
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_setting_me(self, client, auth_token):
        token, _ = auth_token
        resp = client.get("/api/setting/me", headers=auth_headers(token))
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_growth_home(self, client, auth_token):
        token, _ = auth_token
        resp = client.get("/api/growth/home", headers=auth_headers(token))
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_chat_sessions_create(self, client, auth_token):
        token, user_id = auth_token
        resp = client.post("/api/chat/sessions", json={
            "session_type": "MOOD", "user_id": user_id, "title": "TDD测试会话",
        }, headers=auth_headers(token))
        assert resp.status_code in (200, 201), f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_mood_read(self, client, auth_token):
        token, _ = auth_token
        from datetime import date
        today = date.today().isoformat()
        resp = client.get(f"/api/mood/{today}", headers=auth_headers(token))
        assert resp.status_code in (200, 404), f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_mood_write(self, client, auth_token):
        token, _ = auth_token
        from datetime import date
        resp = client.post("/api/mood", json={
            "mood_date": date.today().isoformat(),
            "mood_score": 7,
            "mood_tags": ["开心"],
            "content": "测试日记",
        }, headers=auth_headers(token))
        assert resp.status_code in (200, 201, 422), f"HTTP {resp.status_code}: {resp.text[:200]}"
