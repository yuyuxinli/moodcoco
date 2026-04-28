"""F9 — Unit tests for the voice entrypoint and ``POST /api/voice/token``.

5 tests per F1 §8 F9.  All run via ``fastapi.testclient.TestClient`` against
the existing FastAPI app — no real LiveKit network calls.

Coverage map (F1 §8 F9):
1. ``test_voice_token_happy_path`` — env vars set; POST succeeds (200), JWT
   has 3 segments, decodes with the same secret, claims include the room
   name and ``video.roomJoin``; ``ws_url`` echoes ``LIVEKIT_URL``.
2. ``test_voice_token_missing_secret_returns_500`` — ``LIVEKIT_API_SECRET``
   unset → HTTP 500 with detail mentioning the missing secret.
3. ``test_voice_token_default_room_name`` — POST without ``room_name`` → the
   canonical default ``"moodcoco-voice"`` is returned.
4. ``test_voice_token_request_validation`` — POST with the wrong field type
   (``room_name`` as int) → FastAPI returns HTTP 422.
5. ``test_existing_routes_still_work`` — ``GET /api/health`` still returns
   ``{"status": "ok"}`` (regression guard for the "do not break existing
   routes" constraint).

Implementation notes:
* ``backend.api`` is imported lazily inside each test so collection-time
  imports of pydantic_ai-backed agents (which open module-level httpx pools)
  do not leak background sockets into earlier tests via pytest's collection
  warning ``filterwarnings = ["error"]`` rule.
* JWT verification uses PyJWT (transitive dep of livekit-api) — no extra
  package install.
"""
from __future__ import annotations

import json

import jwt
import pytest

# LiveKit AccessToken signs HS256 JWTs; PyJWT warns when the HMAC key is
# shorter than 32 bytes (RFC 7518 §3.2). Pyproject sets
# ``filterwarnings = ["error"]`` so any warning fails the test — pad the key.
_FAKE_LK_KEY = "test-lk-api-key"
_FAKE_LK_SECRET = "test-lk-api-secret-32-bytes-padding"  # noqa: S105 - test-only fixture
_FAKE_LK_URL = "wss://test.livekit.cloud"


def _make_client(monkeypatch: pytest.MonkeyPatch, *, with_secret: bool = True):
    """Build a ``TestClient`` after wiring LiveKit env vars.

    The lazy ``from backend.api import app`` defers pydantic_ai-backed agent
    initialisation until the first time we actually need the FastAPI app.
    Pytest collects this file early (alphabetical) and any module-level
    HTTPX pools spun up here would otherwise surface as
    ``ResourceWarning`` during the cleanup of unrelated tests under
    ``filterwarnings = ["error"]``.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setenv("LIVEKIT_API_KEY", _FAKE_LK_KEY)
    if with_secret:
        monkeypatch.setenv("LIVEKIT_API_SECRET", _FAKE_LK_SECRET)
    else:
        monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    monkeypatch.setenv("LIVEKIT_URL", _FAKE_LK_URL)

    from backend.api import app

    return TestClient(app)


# ── Test 1: happy path — JWT structure + claims ─────────────────────────────


def test_voice_token_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 §8 F9 case 1: 200 + valid JWT + ws_url echoes env."""
    client = _make_client(monkeypatch)
    payload = {
        "session_id": "web-demo",
        "room_name": "moodcoco-voice-room-001",
        "participant_identity": "web-user-001",
    }
    resp = client.post("/api/voice/token", json=payload)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # Schema conforms to F2 §7: token, ws_url, room_name, participant_identity.
    assert set(body.keys()) >= {"token", "ws_url", "room_name", "participant_identity"}
    assert body["ws_url"] == _FAKE_LK_URL
    assert body["room_name"] == "moodcoco-voice-room-001"
    assert body["participant_identity"] == "web-user-001"

    token = body["token"]
    assert isinstance(token, str) and token, "token must be a non-empty string"
    # JWT format: 3 base64url segments separated by 2 dots.
    assert token.count(".") == 2

    # Decode + verify with the same secret used to sign — round-trips the
    # contract that the LiveKit JS SDK will see.
    claims = jwt.decode(
        token,
        _FAKE_LK_SECRET,
        algorithms=["HS256"],
        # AccessToken does NOT set an audience, so do not require one.
        options={"verify_aud": False},
    )
    assert claims["sub"] == "web-user-001", claims
    assert claims["iss"] == _FAKE_LK_KEY, claims
    # Required LiveKit JS SDK grants per F2 §7.
    video = claims.get("video") or {}
    assert video.get("roomJoin") is True, claims
    assert video.get("room") == "moodcoco-voice-room-001", claims
    assert video.get("canPublish") is True, claims
    assert video.get("canSubscribe") is True, claims


# ── Test 2: missing LIVEKIT_API_SECRET → 500 ────────────────────────────────


def test_voice_token_missing_secret_returns_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F1 §8 F9 case 3: secret missing → HTTP 500 with descriptive detail."""
    client = _make_client(monkeypatch, with_secret=False)
    resp = client.post("/api/voice/token", json={"session_id": "web-demo"})

    assert resp.status_code == 500
    detail = resp.json().get("detail") or ""
    # Detail must clearly point at the missing env var so operators can fix it.
    assert "LIVEKIT_API_SECRET" in detail, detail


# ── Test 3: default room_name ───────────────────────────────────────────────


def test_voice_token_default_room_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 §8 F9 case (default): omitted ``room_name`` → ``moodcoco-voice``."""
    client = _make_client(monkeypatch)
    resp = client.post("/api/voice/token", json={"session_id": "web-demo"})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["room_name"] == "moodcoco-voice"
    # The signed JWT must encode the same room — clients trust the JWT, not the body.
    claims = jwt.decode(
        body["token"],
        _FAKE_LK_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    assert (claims.get("video") or {}).get("room") == "moodcoco-voice", claims
    # Generated participant_identity should be deterministic-shaped.
    assert body["participant_identity"].startswith("web-user-web-demo-"), body


# ── Test 4: Pydantic validation → 422 ───────────────────────────────────────


def test_voice_token_request_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 §8 F9 case 5 (validation): wrong field type returns 422."""
    client = _make_client(monkeypatch)
    # ``room_name`` is typed as ``str | None`` — passing 12345 trips Pydantic.
    resp = client.post(
        "/api/voice/token",
        # Send the JSON body with an int where a string is expected.
        content=json.dumps({"session_id": "web-demo", "room_name": 12345}),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422, resp.text
    # Validation error body has FastAPI's standard ``detail`` array shape.
    payload = resp.json()
    assert "detail" in payload, payload


# ── Test 5: existing routes regression guard ────────────────────────────────


def test_existing_routes_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """F1 §8 F9 case 4: ``GET /api/health`` still returns 200 ok.

    Regression guard: F9 must NOT modify any existing route. Health is
    cheap, deterministic, and present since v0.1, so it's the safest probe.
    """
    client = _make_client(monkeypatch)
    resp = client.get("/api/health")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "ok"}
