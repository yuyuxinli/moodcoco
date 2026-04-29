"""LiveKit voice agent entrypoint — wires plugins + decisions into AgentSession.

Per F1 §4.8: this module exposes ``voice_entrypoint(ctx: JobContext)`` which
the LiveKit Agents framework invokes for every accepted job.  The entrypoint:

1. Builds the Xfyun STT plugin (F3) and MiniMax TTS plugin (F4).
2. Builds two ``livekit.plugins.openai.LLM`` instances:

   * ``fast_llm`` — Doubao lite via ``DOUBAO_BASE_URL`` (filler + decisions).
   * ``slow_llm`` — Minimax m2.7 via ``OPENAI_BASE_URL`` (slow_v1 / slow_v2).

3. Constructs an ``SJTUSkillRouter`` (F7) so slow_v2 can inject SKILL.md
   content per the merged decision.
4. Instantiates ``FastSlowAgent`` (F8) with merged_decision + continue_decider
   passed as DI hooks (per agent constructor contract).
5. Starts an ``AgentSession`` bound to the room.

Failures in plugin construction are logged at ERROR with structured
``room_name`` context and re-raised so LiveKit can mark the job failed.

Logger: ``voice.entrypoint``.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from livekit.agents import AgentSession, JobContext, RoomInputOptions, stt as _agent_stt
from livekit.plugins import silero as _silero
from openai import AsyncOpenAI

from backend.voice.bridge_agent import VoiceBridgeAgent
from backend.voice.plugins._context import voice_session_ctx, voice_turn_ctx
from backend.voice.plugins.minimax_tts import MinimaxTTSPlugin
from backend.voice.plugins.xfyun_stt import XfyunSTTPlugin

logger = logging.getLogger("voice.entrypoint")

_DEFAULT_FAST_MODEL = "doubao-seed-2-0-lite-260215"
_DEFAULT_SLOW_MODEL = "minimax/minimax-m2.7"
_DEFAULT_DOUBAO_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
_DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_DEFAULT_INSTRUCTIONS = (
    "你是 moodcoco（可可），一位温柔、专业、共情的 AI 心理陪伴。"
    "用中文回应，短句优先，先承接情绪再视情况展开。"
    "不诊断、不评判、不替用户做决定。"
)


def _build_fast_llm() -> Any:
    """Build the Doubao lite LiveKit LLM client.

    Returns:
        ``livekit.plugins.openai.LLM`` configured with Doubao base URL.

    Raises:
        ValueError: If ``DOUBAO_API_KEY`` is missing.
    """
    from livekit.plugins import openai as lk_openai

    api_key = os.environ.get("DOUBAO_API_KEY")
    if not api_key:
        raise ValueError("DOUBAO_API_KEY env var is required for fast LLM")
    base_url = os.environ.get("DOUBAO_BASE_URL", _DEFAULT_DOUBAO_BASE_URL)
    model = os.environ.get("DOUBAO_MODEL", _DEFAULT_FAST_MODEL)
    return lk_openai.LLM(model=model, base_url=base_url, api_key=api_key)


def _build_slow_llm() -> Any:
    """Build the Minimax m2.7 LiveKit LLM client.

    Returns:
        ``livekit.plugins.openai.LLM`` configured with OpenRouter base URL.

    Raises:
        ValueError: If ``OPENAI_API_KEY`` is missing.
    """
    from livekit.plugins import openai as lk_openai

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY env var is required for slow LLM")
    base_url = os.environ.get("OPENAI_BASE_URL", _DEFAULT_OPENROUTER_BASE_URL)
    model = os.environ.get("OPENAI_MODEL", _DEFAULT_SLOW_MODEL)
    return lk_openai.LLM(model=model, base_url=base_url, api_key=api_key)


def _build_fast_client() -> AsyncOpenAI:
    api_key = os.environ.get("DOUBAO_API_KEY")
    if not api_key:
        raise ValueError("DOUBAO_API_KEY env var is required for fast LLM")
    base_url = os.environ.get("DOUBAO_BASE_URL", _DEFAULT_DOUBAO_BASE_URL)
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


def _build_slow_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY env var is required for slow LLM")
    base_url = os.environ.get("OPENAI_BASE_URL", _DEFAULT_OPENROUTER_BASE_URL)
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


async def voice_entrypoint(ctx: JobContext) -> None:
    """LiveKit Agents framework entrypoint for the moodcoco voice room.

    Args:
        ctx: LiveKit ``JobContext`` providing ``ctx.room`` for this session.

    Raises:
        ValueError: Re-raised from plugin builders when required env vars are
            missing (``DOUBAO_API_KEY``, ``OPENAI_API_KEY``, ``MINIMAX_API_KEY``,
            ``XFYUN_*``).  LiveKit marks the job failed.
        Exception: Any other unexpected failure during plugin or session setup
            is logged at ERROR with ``room_name`` and re-raised.
    """
    room_name = getattr(getattr(ctx, "room", None), "name", "unknown") or "unknown"

    try:
        await ctx.connect()
        voice_session_ctx.set(room_name)
        voice_turn_ctx.set(None)
        logger.info(
            "voice_entrypoint_connected",
            extra={"session_id": room_name, "room_name": room_name},
        )

        # XfyunSTTPlugin is file-based; LiveKit 1.5 requires streaming STT
        # to detect turn boundaries. Wrap with VAD + StreamAdapter.
        vad = _silero.VAD.load()
        stt_plugin = _agent_stt.StreamAdapter(stt=XfyunSTTPlugin(), vad=vad)
        tts_plugin = MinimaxTTSPlugin()
        slow_llm = _build_slow_llm()

        agent = VoiceBridgeAgent(instructions=_DEFAULT_INSTRUCTIONS)

        session = AgentSession(
            stt=stt_plugin,
            tts=tts_plugin,
            llm=slow_llm,
        )

        logger.info(
            "voice_session_starting",
            extra={
                "session_id": room_name,
                "room_name": room_name,
                "fast_model": os.environ.get("DOUBAO_MODEL", _DEFAULT_FAST_MODEL),
                "slow_model": os.environ.get("OPENAI_MODEL", _DEFAULT_SLOW_MODEL),
            },
        )

        def _on_track_subscribed(track, publication, participant):
            logger.info(
                "[STAGE_I1] room_track_subscribed",
                extra={
                    "session_id": room_name,
                    "phase": "room_io",
                    "participant": getattr(participant, "identity", None),
                    "participant_kind": str(getattr(participant, "kind", None)),
                    "track_kind": str(getattr(track, "kind", None)),
                    "track_sid": getattr(publication, "sid", None),
                    "track_source": str(getattr(publication, "source", None)),
                },
            )

        ctx.room.on("track_subscribed", _on_track_subscribed)

        def _on_participant_connected(participant):
            logger.info(
                "[STAGE_I2] room_participant_connected",
                extra={
                    "session_id": room_name,
                    "phase": "room_io",
                    "identity": getattr(participant, "identity", None),
                    "kind": str(getattr(participant, "kind", None)),
                },
            )

        ctx.room.on("participant_connected", _on_participant_connected)

        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(close_on_disconnect=False),
        )

        logger.info(
            "[STAGE_D] session_start_completed_state",
            extra={
                "session_id": room_name,
                "phase": "room_io",
                "session_input": type(getattr(session, "input", None)).__name__,
                "room_io": type(getattr(session, "_room_io", None)).__name__,
                "remote_participants": list(
                    getattr(ctx.room, "remote_participants", {}).keys()
                ),
            },
        )

        logger.info(
            "voice_session_started",
            extra={"session_id": room_name, "room_name": room_name},
        )
    except Exception as exc:
        logger.error(
            "voice_entrypoint_init_failed",
            extra={
                "session_id": room_name,
                "room_name": room_name,
                "error": str(exc),
                "error_class": exc.__class__.__name__,
            },
            exc_info=True,
        )
        raise
