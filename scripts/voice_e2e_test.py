#!/usr/bin/env python3
"""Voice E2E smoke test — validates LiveKit server + API token endpoint + agent dispatch.

Prerequisites:
  1. docker compose -f docker-compose.voice.yml up -d
  2. Backend API running: uvicorn backend.api:app --port 8000
  3. Voice agent running: python -m livekit.agents start --url ws://localhost:7880 backend.voice.entrypoint

Usage:
  python scripts/voice_e2e_test.py [--api-url http://localhost:8000] [--lk-url ws://localhost:7880]

What it tests:
  - LiveKit server health (HTTP)
  - POST /api/voice/token returns a valid JWT + room_name
  - LiveKit room is created and accessible
  - Agent dispatch (if VOICE_AUTO_DISPATCH_AGENT=true)

What it does NOT test (requires browser/audio):
  - Actual STT/TTS audio pipeline
  - WebRTC media transport
  - Real conversation turns
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _log(tag: str, msg: str, **kw: object) -> None:
    extra = " ".join(f"{k}={v}" for k, v in kw.items())
    print(f"[{tag}] {msg} {extra}".strip())


async def check_livekit_health(lk_http_url: str) -> bool:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{lk_http_url}")
            _log("OK", "LiveKit server reachable", status=resp.status_code)
            return True
    except Exception as exc:
        _log("FAIL", f"LiveKit server unreachable: {exc}")
        return False


async def check_api_health(api_url: str) -> bool:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{api_url}/api/health")
            data = resp.json()
            _log("OK", "API health", status=data.get("status"))
            return data.get("status") == "ok"
    except Exception as exc:
        _log("FAIL", f"API health check failed: {exc}")
        return False


async def check_voice_token(api_url: str) -> dict | None:
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{api_url}/api/voice/token",
                json={"session_id": "e2e-test"},
            )
            if resp.status_code != 200:
                _log("FAIL", f"Voice token returned {resp.status_code}: {resp.text}")
                return None
            data = resp.json()
            _log(
                "OK",
                "Voice token issued",
                room=data.get("room_name"),
                identity=data.get("participant_identity"),
                ws_url=data.get("ws_url"),
            )
            return data
    except Exception as exc:
        _log("FAIL", f"Voice token request failed: {exc}")
        return None


async def check_room_exists(lk_http_url: str, room_name: str) -> bool:
    try:
        from livekit import api

        lkapi = api.LiveKitAPI(
            url=lk_http_url,
            api_key=os.environ.get("LIVEKIT_API_KEY", "devkey"),
            api_secret=os.environ.get("LIVEKIT_API_SECRET", "secret"),
        )
        try:
            rooms = await lkapi.room.list_rooms(api.ListRoomsRequest(names=[room_name]))
            found = any(r.name == room_name for r in rooms.rooms)
            if found:
                _log("OK", "Room exists in LiveKit", room=room_name)
            else:
                _log("WARN", "Room not found (agent may not have joined yet)", room=room_name)
            return found
        finally:
            await lkapi.aclose()
    except ImportError:
        _log("SKIP", "livekit-api not installed, skipping room check")
        return True
    except Exception as exc:
        _log("WARN", f"Room check failed: {exc}")
        return False


async def check_room_participants(lk_http_url: str, room_name: str) -> int:
    try:
        from livekit import api

        lkapi = api.LiveKitAPI(
            url=lk_http_url,
            api_key=os.environ.get("LIVEKIT_API_KEY", "devkey"),
            api_secret=os.environ.get("LIVEKIT_API_SECRET", "secret"),
        )
        try:
            resp = await lkapi.room.list_participants(
                api.ListParticipantsRequest(room=room_name)
            )
            count = len(resp.participants)
            for p in resp.participants:
                _log(
                    "INFO",
                    f"  participant: {p.identity}",
                    kind=getattr(p, "kind", "unknown"),
                )
            return count
        finally:
            await lkapi.aclose()
    except Exception as exc:
        _log("WARN", f"Participant check failed: {exc}")
        return -1


async def run_e2e(api_url: str, lk_ws_url: str) -> bool:
    lk_http_url = lk_ws_url.replace("ws://", "http://").replace("wss://", "https://")

    results: dict[str, bool] = {}

    _log("TEST", "1/5 — LiveKit server health")
    results["livekit_health"] = await check_livekit_health(lk_http_url)

    _log("TEST", "2/5 — Backend API health")
    results["api_health"] = await check_api_health(api_url)

    if not results["api_health"]:
        _log("SKIP", "API not available, skipping token + room tests")
        results["voice_token"] = False
        results["room_exists"] = False
        results["participants"] = False
    else:
        _log("TEST", "3/5 — Voice token endpoint")
        token_data = await check_voice_token(api_url)
        results["voice_token"] = token_data is not None

        if token_data:
            room_name = token_data["room_name"]
            await asyncio.sleep(2.0)

            _log("TEST", "4/5 — Room existence")
            results["room_exists"] = await check_room_exists(lk_http_url, room_name)

            _log("TEST", "5/5 — Room participants (agent dispatch)")
            count = await check_room_participants(lk_http_url, room_name)
            results["participants"] = count > 0
            if count <= 0:
                _log(
                    "WARN",
                    "No participants — voice agent may not be running. "
                    "Start with: python -m livekit.agents start "
                    "--url ws://localhost:7880 backend.voice.entrypoint",
                )
        else:
            results["room_exists"] = False
            results["participants"] = False

    print()
    _log("SUMMARY", "Voice E2E results:")
    all_pass = True
    for name, ok in results.items():
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {name}")
        if not ok:
            all_pass = False

    if all_pass:
        _log("RESULT", "All checks passed")
    else:
        _log("RESULT", "Some checks failed — see above for details")

    return all_pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice E2E smoke test")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--lk-url", default="ws://localhost:7880")
    args = parser.parse_args()

    ok = asyncio.run(run_e2e(args.api_url, args.lk_url))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
