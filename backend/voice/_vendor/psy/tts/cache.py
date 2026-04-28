from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from services.shared.tts.types import MiniMaxSynthesisOptions

CACHE_NAMESPACE = "minimax_tts_audio"


def build_tts_cache_key(text: str, options: MiniMaxSynthesisOptions) -> str:
    raw = "|".join(
        [
            text,
            options.model,
            options.voice_id,
            str(options.speed),
            str(options.vol),
            str(options.pitch),
            str(options.voice_modify_pitch),
            str(options.voice_modify_intensity),
            str(options.voice_modify_timbre),
            options.file_format,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MiniMaxTTSCacheStore:
    def __init__(self, ttl_seconds: int = 4 * 60 * 60) -> None:
        self._ttl_seconds = ttl_seconds

    async def get_cached_result(
        self,
        text: str,
        options: MiniMaxSynthesisOptions,
    ) -> Optional[Dict[str, Any]]:
        from db.session import async_session_maker
        from services.cache_service import CacheService

        cache_key = build_tts_cache_key(text, options)
        async with async_session_maker() as session:
            payload = await CacheService(session).get(CACHE_NAMESPACE, cache_key)
        if not payload:
            return None
        expires_at_raw = payload.get("expires_at")
        if expires_at_raw:
            expires_at = datetime.fromisoformat(expires_at_raw)
            if expires_at <= datetime.now(timezone.utc):
                return None
        return payload

    async def set_cached_result(
        self,
        text: str,
        options: MiniMaxSynthesisOptions,
        value: Dict[str, Any],
    ) -> None:
        from db.session import async_session_maker
        from services.cache_service import CacheService

        cache_key = build_tts_cache_key(text, options)
        payload = dict(value)
        payload["expires_at"] = (
            (datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds))
            .replace(microsecond=0)
            .isoformat()
        )
        async with async_session_maker() as session:
            await CacheService(session).set(
                CACHE_NAMESPACE,
                cache_key,
                payload,
                ttl_seconds=self._ttl_seconds,
            )
