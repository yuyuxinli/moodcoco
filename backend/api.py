"""FastAPI HTTP 层 —— 给 Web UI 暴露 Coco 和 Persona 对话接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.coordinator import reset_guidance_for_demo, run_turn
from backend.persona import list_personas, run_persona_turn
from backend.slow import reset_memory_file_for_demo

app = FastAPI(title="moodcoco API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
