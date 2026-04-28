"""DP-continue decider — Doubao lite second-pass gate for slow_v2.

After ``slow_v1`` finishes, ``should_continue()`` calls Doubao lite once with the
slow_v1 output and recent conversation context, asking the model whether the
assistant should add a second deeper response (``slow_v2``).  The call is
guarded by a hard ``DP_CONTINUE_TIMEOUT_MS`` (default 200 ms, per F1 §2):

* On timeout / API error / JSON parse failure the public function returns
  ``ContinueDecision(yes=False, reason=...)`` instead of raising — the user must
  never be blocked waiting on the decision pipeline.
* Internal errors are still classified into the ``ContinueDecider*Error`` types
  so tests and structured logs can distinguish a timeout from a parse failure.

The module mirrors :mod:`backend.voice.decisions.merged_decision` for logger
naming (``voice.decisions.continue_decider``), exception hierarchy
(``ContinueDeciderError`` base + Timeout/Parse/API leafs), ContextVar usage
(``voice_session_ctx`` / ``voice_turn_ctx`` from ``plugins/_context``), and the
fallback pattern (timeout → ``error`` log; parse → ``warning`` log).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI

from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx

logger = logging.getLogger("voice.decisions.continue_decider")

_DEFAULT_MODEL = "doubao-seed-2-0-lite-260215"
DP_CONTINUE_TIMEOUT_MS: int = int(os.getenv("DP_CONTINUE_TIMEOUT_MS", "200"))

_PROMPT = """\
You are evaluating whether an AI emotional-support assistant should add a
SECOND deeper response (slow_v2) right after its first reply (slow_v1).

Output ONLY valid JSON of the form:
{"yes": <bool>, "reason": "<short reason>"}

Return {"yes": true} only when slow_v1 is clearly too shallow — for example it
only asked an open question, missed a named emotion, or stopped at a single
acknowledgement when the user shared a heavy moment. Otherwise return
{"yes": false}. Keep "reason" under 30 characters.
"""


# ---------------------------------------------------------------------------
# Exception hierarchy (mirrors merged_decision)
# ---------------------------------------------------------------------------


class ContinueDeciderError(Exception):
    """Base class for internally classified ContinueDecider failures."""


class ContinueDeciderTimeoutError(ContinueDeciderError):
    """Doubao DP-continue exceeded ``DP_CONTINUE_TIMEOUT_MS``."""


class ContinueDeciderParseError(ContinueDeciderError):
    """Doubao DP-continue returned malformed JSON or an invalid shape."""


class ContinueDeciderAPIError(ContinueDeciderError):
    """Doubao DP-continue API call failed (non-timeout, non-parse)."""


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContinueDecision:
    """Result of a DP-continue call.

    Attributes:
        yes: Whether the assistant should run slow_v2.
        reason: Short human-readable rationale (or ``"timeout"`` /
            ``"parse_error"`` / ``"api_error"`` for fallbacks).
        latency_ms: Wall-clock time spent on the decision (including timeout
            wait).
    """

    yes: bool = False
    reason: str = ""
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def should_continue(
    slow_v1_text: str, recent_ctx: list[dict]
) -> ContinueDecision:
    """Ask Doubao lite whether to run slow_v2 after slow_v1.

    Args:
        slow_v1_text: Full text returned by slow_v1.
        recent_ctx: Recent conversation context as JSON-serializable dicts
            (e.g. ``[{"role": "user", "content": "..."}, ...]``).

    Returns:
        ``ContinueDecision``.  Any timeout, API error, or JSON parse failure
        returns the graceful fallback ``ContinueDecision(yes=False, reason=...)``
        — the public API never raises so the user's turn cannot be blocked.

    Raises:
        None. Internal failures are classified as
        :class:`ContinueDeciderTimeoutError`,
        :class:`ContinueDeciderParseError`, or
        :class:`ContinueDeciderAPIError` for tests and structured logs, then
        caught and converted to a fallback result.
    """
    session_id = voice_session_ctx.get()
    turn_id = voice_turn_ctx.get()
    started_at = time.monotonic()
    timeout_s = DP_CONTINUE_TIMEOUT_MS / 1000.0

    logger.info(
        "continue_decider_start",
        extra={
            "session_id": session_id,
            "turn_id": turn_id,
            "slow_v1_len": len(slow_v1_text or ""),
            "timeout_ms": DP_CONTINUE_TIMEOUT_MS,
        },
    )

    try:
        raw_json = await asyncio.wait_for(
            _call_doubao(slow_v1_text=slow_v1_text, recent_ctx=recent_ctx),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as exc:
        latency_ms = _latency_ms(started_at)
        classified = ContinueDeciderTimeoutError(str(exc) or "timeout")
        logger.error(
            "continue_decider_timeout",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "error_class": classified.__class__.__name__,
                "timeout_ms": DP_CONTINUE_TIMEOUT_MS,
                "latency_ms": latency_ms,
            },
        )
        return ContinueDecision(yes=False, reason="timeout", latency_ms=latency_ms)
    except httpx.TimeoutException as exc:
        latency_ms = _latency_ms(started_at)
        classified = ContinueDeciderTimeoutError(str(exc))
        logger.error(
            "continue_decider_timeout",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "error_class": classified.__class__.__name__,
                "timeout_ms": DP_CONTINUE_TIMEOUT_MS,
                "error": str(exc),
                "latency_ms": latency_ms,
            },
        )
        return ContinueDecision(yes=False, reason="timeout", latency_ms=latency_ms)
    except Exception as exc:  # network / API error
        latency_ms = _latency_ms(started_at)
        classified = ContinueDeciderAPIError(str(exc))
        logger.warning(
            "continue_decider_api_fallback",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "error_class": classified.__class__.__name__,
                "error": str(exc),
                "latency_ms": latency_ms,
            },
        )
        return ContinueDecision(yes=False, reason="api_error", latency_ms=latency_ms)

    try:
        decision = _parse_decision(raw_json, _latency_ms(started_at))
    except ContinueDeciderParseError as exc:
        latency_ms = _latency_ms(started_at)
        logger.warning(
            "continue_decider_json_fallback",
            extra={
                "session_id": session_id,
                "turn_id": turn_id,
                "raw_response": raw_json,
                "error_class": exc.__class__.__name__,
                "latency_ms": latency_ms,
            },
        )
        return ContinueDecision(
            yes=False, reason="parse_error", latency_ms=latency_ms
        )

    logger.info(
        "continue_decider_success",
        extra={
            "session_id": session_id,
            "turn_id": turn_id,
            "yes": decision.yes,
            "reason": decision.reason,
            "latency_ms": decision.latency_ms,
        },
    )
    return decision


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _call_doubao(*, slow_v1_text: str, recent_ctx: list[dict]) -> str:
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
                    {"slow_v1": slow_v1_text, "recent_ctx": recent_ctx},
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    if not isinstance(content, str):
        raise ContinueDeciderParseError("missing message content")
    return content


def _parse_decision(raw_json: str, latency_ms: float) -> ContinueDecision:
    try:
        payload: Any = json.loads(raw_json)
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        yes_value = payload.get("yes")
        reason_value = payload.get("reason", "")
    except Exception as exc:
        raise ContinueDeciderParseError(str(exc)) from exc

    yes = bool(yes_value) if isinstance(yes_value, bool) else False
    reason = reason_value if isinstance(reason_value, str) else ""
    return ContinueDecision(yes=yes, reason=reason, latency_ms=latency_ms)


def _latency_ms(started_at: float) -> float:
    return (time.monotonic() - started_at) * 1000
