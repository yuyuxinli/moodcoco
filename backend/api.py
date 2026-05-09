"""FastAPI HTTP 层 —— 给 Web UI 暴露 Coco 和 Persona 对话接口。"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.coordinator import reset_guidance_for_demo, run_turn
from backend.persona import list_personas, run_persona_turn
from backend.slow import reset_memory_file_for_demo

_voice_api_logger = logging.getLogger("voice.api")
_DEFAULT_ROOM_NAME = "moodcoco-voice"
_DEFAULT_LK_URL = "wss://your-livekit-server.livekit.cloud"
_DEFAULT_VOICE_AGENT_NAME = "moodcoco-coco"

app = FastAPI(title="moodcoco API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----- Pydantic models -----


class ToolCall(BaseModel):
    name: str
    args: dict


class ChatHistoryItem(BaseModel):
    role: Literal["coco", "persona"]
    text: str
    tool_calls: list[ToolCall] | None = None


class CocoChatReq(BaseModel):
    user_msg: str
    session_id: str = "web-demo"


class CocoChatResp(BaseModel):
    reply_text: str
    tool_calls: list[ToolCall]
    needs_deep: bool
    slow_history: list[str]


class PersonaChatReq(BaseModel):
    persona_id: str
    history: list[ChatHistoryItem] = Field(default_factory=list)
    latest_coco_msg: str | None = None


class PersonaChatResp(BaseModel):
    text: str


class AutoConvReq(BaseModel):
    persona_id: str
    turns: int = Field(default=4, ge=1, le=8)
    starter: Literal["persona", "coco"] = "persona"
    session_id: str = "web-demo"


class AutoConvResp(BaseModel):
    history: list[ChatHistoryItem]
    error: str | None = None


# ----- endpoints -----


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/personas")
async def personas_endpoint() -> list[dict]:
    return list_personas()


@app.post("/api/coco/chat", response_model=CocoChatResp)
async def coco_chat(req: CocoChatReq) -> CocoChatResp:
    try:
        result = await run_turn(req.user_msg, session_id=req.session_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"coco run_turn failed: {exc}") from exc
    return CocoChatResp(
        reply_text=result.get("fast_reply_text") or "",
        tool_calls=[ToolCall(**tc) for tc in result.get("fast_tool_calls", [])],
        needs_deep=bool(result.get("needs_deep")),
        slow_history=list(result.get("slow_history") or []),
    )


@app.post("/api/persona/chat", response_model=PersonaChatResp)
async def persona_chat(req: PersonaChatReq) -> PersonaChatResp:
    try:
        text = await run_persona_turn(
            req.persona_id,
            [item.model_dump() for item in req.history],
            req.latest_coco_msg,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"persona run failed: {exc}") from exc
    return PersonaChatResp(text=text)


@app.post("/api/auto-conversation", response_model=AutoConvResp)
async def auto_conversation(req: AutoConvReq) -> AutoConvResp:
    """N 轮 persona ↔ coco 自动对话，一次性返回整段历史。

    一个 "回合" = persona 说一句 + coco 回一句。
    starter='persona'（默认）时 persona 先开口；coco 先开口时 persona 再回应。
    """
    history: list[ChatHistoryItem] = []
    latest_coco_msg: str | None = None
    error: str | None = None

    try:
        if req.starter == "coco":
            # coco 先来一句（用模拟的"进场招呼"作为 user prompt）
            greeting_input = "（你好）"
            result = await run_turn(greeting_input, session_id=req.session_id)
            coco_text = result.get("fast_reply_text") or ""
            history.append(
                ChatHistoryItem(
                    role="coco",
                    text=coco_text,
                    tool_calls=[ToolCall(**tc) for tc in result.get("fast_tool_calls", [])],
                )
            )
            latest_coco_msg = coco_text

        for _ in range(req.turns):
            persona_text = await run_persona_turn(
                req.persona_id,
                [item.model_dump() for item in history],
                latest_coco_msg,
            )
            history.append(ChatHistoryItem(role="persona", text=persona_text))

            coco_result = await run_turn(persona_text, session_id=req.session_id)
            coco_text = coco_result.get("fast_reply_text") or ""
            history.append(
                ChatHistoryItem(
                    role="coco",
                    text=coco_text,
                    tool_calls=[ToolCall(**tc) for tc in coco_result.get("fast_tool_calls", [])],
                )
            )
            latest_coco_msg = coco_text
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    return AutoConvResp(history=history, error=error)


@app.post("/api/reset")
async def reset_endpoint() -> dict:
    """清空 Coco 的 SLOW_GUIDANCE 和 MEMORY（切 persona / 重开会话时调用）。"""
    reset_guidance_for_demo()
    reset_memory_file_for_demo()
    return {"status": "reset"}


# ─────────────────────────────────────────────────────────────────────────────
# F9 — POST /api/voice/token  (LiveKit JWT signing for the web voice client)
#
# Contract per F2 §7 (authoritative for F10 web client):
#   request:  { session_id?, room_name?, participant_identity? }
#   response: { token, ws_url, room_name, participant_identity }
#
# JWT claims (per F2 §7):
#   identity = participant_identity (defaults to "web-user-{session_id}")
#   roomJoin=true, room=<room_name>, canPublish=true, canSubscribe=true
#   ttl = 3600s (LiveKit AccessToken default)
#
# Error semantics:
#   500 — LIVEKIT_API_KEY / LIVEKIT_API_SECRET missing in env
#   422 — Pydantic-level validation failure (FastAPI default)
# ─────────────────────────────────────────────────────────────────────────────


class VoiceTokenReq(BaseModel):
    """Voice token request body (F2 §7).

    All fields optional so the web client can connect with sensible defaults
    during demo. ``session_id`` ties the LiveKit room back to the same logical
    session as the text chat (``web-demo`` in current UI).
    """

    session_id: str | None = Field(default=None, max_length=128)
    room_name: str | None = Field(default=None, min_length=1, max_length=128)
    participant_identity: str | None = Field(default=None, min_length=1, max_length=128)


class VoiceTokenResp(BaseModel):
    """Voice token response body (F2 §7)."""

    token: str = Field(..., description="LiveKit JWT access token")
    ws_url: str = Field(..., description="LiveKit SFU WebSocket URL")
    room_name: str = Field(..., description="Canonical room name (echo or generated)")
    participant_identity: str = Field(..., description="Participant identity baked into the JWT")


def _voice_auto_dispatch_enabled() -> bool:
    return os.environ.get("VOICE_AUTO_DISPATCH_AGENT", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _livekit_http_url(ws_url: str) -> str:
    return ws_url.replace("ws://", "http://").replace("wss://", "https://")


async def _dispatch_voice_agent(*, room_name: str, agent_name: str) -> None:
    from livekit import api

    lkapi = api.LiveKitAPI(
        url=_livekit_http_url(os.environ.get("LIVEKIT_URL", _DEFAULT_LK_URL)),
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    try:
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=room_name,
                metadata="",
            )
        )
    finally:
        await lkapi.aclose()


@app.post("/api/voice/token", response_model=VoiceTokenResp)
async def voice_token(req: VoiceTokenReq) -> VoiceTokenResp:
    """Issue a LiveKit room access token for the browser voice client.

    Signs a JWT locally using ``LIVEKIT_API_KEY`` / ``LIVEKIT_API_SECRET``;
    the LiveKit SFU is not contacted by this route.

    Args:
        req: Optional ``session_id`` / ``room_name`` / ``participant_identity``.
            Missing fields default to demo-friendly values.

    Returns:
        ``VoiceTokenResp`` with the signed JWT, the LiveKit WebSocket URL
        (``LIVEKIT_URL`` env var, falling back to a clearly-fake placeholder),
        the canonical ``room_name``, and the ``participant_identity`` that was
        baked into the JWT.

    Raises:
        HTTPException: 500 when ``LIVEKIT_API_KEY`` or ``LIVEKIT_API_SECRET``
            are missing from the environment.
    """
    lk_api_key = os.environ.get("LIVEKIT_API_KEY")
    lk_api_secret = os.environ.get("LIVEKIT_API_SECRET")
    lk_url = os.environ.get("LIVEKIT_URL", _DEFAULT_LK_URL)

    if not lk_api_key or not lk_api_secret:
        _voice_api_logger.error(
            "voice_token_env_missing",
            extra={
                "session_id": req.session_id or "",
                "has_key": bool(lk_api_key),
                "has_secret": bool(lk_api_secret),
            },
        )
        raise HTTPException(
            status_code=500,
            detail="LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set",
        )

    # Resolve canonical room_name + participant_identity with stable defaults.
    session_id = req.session_id or "web-demo"
    safe_session_id = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "-"
        for ch in session_id
    )[:48]
    room_name = req.room_name or f"{_DEFAULT_ROOM_NAME}-{safe_session_id}-{uuid.uuid4().hex[:8]}"
    participant_identity = (
        req.participant_identity
        or f"web-user-{session_id}-{uuid.uuid4().hex[:8]}"
    )

    # Lazy import keeps the API module importable without livekit-api installed
    # (e.g., in environments that only run the text chat).
    from livekit.api import AccessToken, VideoGrants

    # Browser listeners (session_id="browser-listener") only need to subscribe;
    # giving them can_publish=True confuses LiveKit AgentSession's auto-pick of
    # the user-input track when there are multiple publishers in the room.
    is_browser_listener = (req.session_id or "").startswith("browser-listener")
    grants_kwargs = dict(
        room_join=True,
        room=room_name,
        can_subscribe=True,
        can_publish=not is_browser_listener,
    )

    try:
        token = (
            AccessToken(lk_api_key, lk_api_secret)
            .with_identity(participant_identity)
            .with_name(participant_identity)
            .with_grants(VideoGrants(**grants_kwargs))
            .to_jwt()
        )
    except ValueError as exc:
        _voice_api_logger.error(
            "voice_token_signing_failed",
            extra={
                "session_id": session_id,
                "room_name": room_name,
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=500, detail=f"token signing failed: {exc}") from exc

    _voice_api_logger.info(
        "voice_token_issued",
        extra={
            "session_id": session_id,
            "room_name": room_name,
            "participant_identity": participant_identity,
        },
    )

    if _voice_auto_dispatch_enabled() and not is_browser_listener:
        agent_name = os.environ.get("VOICE_AGENT_NAME", _DEFAULT_VOICE_AGENT_NAME)
        try:
            await _dispatch_voice_agent(room_name=room_name, agent_name=agent_name)
        except Exception as exc:  # noqa: BLE001
            _voice_api_logger.error(
                "voice_agent_dispatch_failed",
                extra={
                    "session_id": session_id,
                    "room_name": room_name,
                    "agent_name": agent_name,
                    "error": str(exc),
                },
            )
            raise HTTPException(
                status_code=503,
                detail=f"voice agent dispatch failed: {exc}",
            ) from exc
        _voice_api_logger.info(
            "voice_agent_dispatched",
            extra={
                "session_id": session_id,
                "room_name": room_name,
                "agent_name": agent_name,
            },
        )

    return VoiceTokenResp(
        token=token,
        ws_url=lk_url,
        room_name=room_name,
        participant_identity=participant_identity,
    )


# F-e2e — persona stop signal (used by /voice-room/index.html "结束" button)
class _PersonaStopReq(BaseModel):
    identity: str = "persona-yuyu"


@app.post("/api/voice/persona-stop")
async def voice_persona_stop(req: _PersonaStopReq) -> dict[str, str]:
    """Touch /tmp/{identity}.stop so persona_agent's loop exits cleanly."""
    safe = "".join(ch for ch in req.identity if ch.isalnum() or ch in ("-", "_"))
    if not safe:
        raise HTTPException(status_code=400, detail="invalid identity")
    Path(f"/tmp/{safe}.stop").touch()
    return {"status": "ok", "stop_file": f"/tmp/{safe}.stop"}
