"""Merged Doubao-lite decision for voice search and skill routing."""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI

from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx

logger = logging.getLogger("voice.decisions.merged_decision")

_DEFAULT_MODEL = "doubao-seed-2-0-lite-260215"
_ALLOWED_SKILLS = {
    "listen",
    "crisis",
    "face-decision",
    "untangle",
    "calm-body",
    "base-communication",
    "validation",
}
_PROMPT = """\
You are a MoodCoco routing assistant. Output ONLY valid JSON:
{"search":{"yes":bool,"kw":string},"skill":string|null}

Allowed skill values: listen, crisis, face-decision, untangle, calm-body,
base-communication, validation, null.
Prefer crisis for self-harm/suicide/safety risk; calm-body for panic, insomnia,
breathlessness, shaking, or overwhelmed body cues; face-decision for choices;
untangle for messy stories; validation for affirmation; listen for emotional
holding; base-communication for communication guidance. Set search.yes true
only when historical people/events/context would help, with a short Chinese kw.
If unsure, return {"search":{"yes":false,"kw":""},"skill":null}.
"""


class MergedDecisionError(Exception):
    """Base class for internally classified merged-decision failures."""


class MergedDecisionTimeoutError(MergedDecisionError):
    """Doubao merged decision timed out."""


class MergedDecisionParseError(MergedDecisionError):
    """Doubao returned malformed JSON or an invalid decision shape."""


class MergedDecisionAPIError(MergedDecisionError):
    """Doubao merged decision API call failed."""


@dataclass(frozen=True)
class MergedDecisionResult:
    """Parsed merged decision result returned by :func:`decide`."""

    search_yes: bool = False
    search_kw: str = ""
    skill: str | None = None
    raw_json: str = ""
    latency_ms: float = 0.0


async def decide(user_msg: str, recent_ctx: list[dict]) -> MergedDecisionResult:
    """Call Doubao lite once to decide memory search and SJTU skill routing.

    Args:
        user_msg: Latest user message text.
        recent_ctx: Recent conversation context as JSON-serializable dicts.

    Returns:
        ``MergedDecisionResult``. Any timeout, API error, or JSON parse failure
        returns the graceful fallback: no search and no skill.

    Raises:
        None. Internal failures are classified as ``MergedDecisionTimeoutError``,
        ``MergedDecisionParseError``, or ``MergedDecisionAPIError`` for tests and
        logging, then caught and converted to a fallback result.
    """
    session_id = voice_session_ctx.get()
    turn_id = voice_turn_ctx.get()
    started_at = time.monotonic()
    logger.info(
        "merged_decision_start",
        extra={"session_id": session_id, "turn_id": turn_id},
    )

    raw_json = ""
    try:
        raw_json = await _call_doubao(user_msg=user_msg, recent_ctx=recent_ctx)
        result = _parse_decision(raw_json, _latency_ms(started_at))
    except httpx.TimeoutException as exc:
        latency_ms = _latency_ms(started_at)
        classified = MergedDecisionTimeoutError(str(exc))
        logger.error(
            "merged_decision_timeout",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "error_class": classified.__class__.__name__,
                "error": str(exc),
                "latency_ms": latency_ms,
            },
        )
        return _fallback(str(exc), latency_ms)
    except MergedDecisionParseError as exc:
        latency_ms = _latency_ms(started_at)
        logger.warning(
            "merged_decision_json_fallback",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "raw_response": raw_json,
                "error_class": exc.__class__.__name__,
                "latency_ms": latency_ms,
            },
        )
        return _fallback(raw_json, latency_ms)
    except Exception as exc:
        latency_ms = _latency_ms(started_at)
        classified = MergedDecisionAPIError(str(exc))
        logger.warning(
            "merged_decision_api_fallback",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "error_class": classified.__class__.__name__,
                "error": str(exc),
                "latency_ms": latency_ms,
            },
        )
        return _fallback(str(exc), latency_ms)

    logger.info(
        "merged_decision_success",
        extra={
            "session_id": session_id,
            "turn_id": turn_id,
            "search_yes": result.search_yes,
            "search_kw": result.search_kw,
            "skill": result.skill,
            "latency_ms": result.latency_ms,
        },
    )
    return result


async def _call_doubao(*, user_msg: str, recent_ctx: list[dict]) -> str:
    client = AsyncOpenAI(
        base_url=os.environ["DOUBAO_BASE_URL"],
        api_key=os.environ["DOUBAO_API_KEY"],
    )
    response = await client.chat.completions.create(
        model=os.environ.get("DOUBAO_MODEL", _DEFAULT_MODEL),
        messages=[
            {"role": "system", "content": _PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"user_msg": user_msg, "recent_ctx": recent_ctx},
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    if not isinstance(content, str):
        raise MergedDecisionParseError("missing message content")
    return content


def _parse_decision(raw_json: str, latency_ms: float) -> MergedDecisionResult:
    try:
        payload: Any = json.loads(raw_json)
        search = payload.get("search") if isinstance(payload, dict) else None
        if not isinstance(search, dict):
            raise ValueError("search must be an object")
        search_kw_value = search.get("kw", "")
        skill_value = payload.get("skill")
    except Exception as exc:
        raise MergedDecisionParseError(str(exc)) from exc

    skill = (
        skill_value
        if isinstance(skill_value, str) and skill_value in _ALLOWED_SKILLS
        else None
    )
    return MergedDecisionResult(
        search_yes=bool(search.get("yes", False)),
        search_kw=search_kw_value if isinstance(search_kw_value, str) else "",
        skill=skill,
        raw_json=raw_json,
        latency_ms=latency_ms,
    )


def _fallback(raw_or_error: str, latency_ms: float) -> MergedDecisionResult:
    return MergedDecisionResult(raw_json=raw_or_error, latency_ms=latency_ms)


def _latency_ms(started_at: float) -> float:
    return (time.monotonic() - started_at) * 1000
