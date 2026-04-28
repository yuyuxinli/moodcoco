"""Shared ContextVar definitions for voice plugin structured logging.

Both XfyunSTTPlugin (F3) and MinimaxTTSPlugin (F4) import from here so that
FastSlowAgent (F5/F9) can set session_id / turn_id once and have them flow
through to every TTS and STT log line without passing extra kwargs.

Usage::

    from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx

    # Before dispatching a turn:
    voice_session_ctx.set("session-abc")
    voice_turn_ctx.set("turn-xyz")
"""
from __future__ import annotations

from contextvars import ContextVar

voice_session_ctx: ContextVar[str | None] = ContextVar(
    "voice_session_ctx", default=None
)
voice_turn_ctx: ContextVar[str | None] = ContextVar("voice_turn_ctx", default=None)
