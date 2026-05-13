from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from backend.voice._vendor.psy.tts.types import MiniMaxSynthesisOptions

# NOTE: vendored into moodcoco — DB-backed cache replaced with in-memory TTL dict.
# Original psychologists implementation used db.session + services.cache_service.

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
    """In-memory TTL cache for MiniMax TTS results (moodcoco vendored version)."""

    def __init__(self, ttl_seconds: int = 4 * 60 * 60) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    async def get_cached_result(
        self,
        text: str,
        options: MiniMaxSynthesisOptions,
    ) -> Optional[Dict[str, Any]]:
        cache_key = build_tts_cache_key(text, options)
        payload = self._store.get(cache_key)
        if not payload:
            return None
        expires_at_raw = payload.get("expires_at")
        if expires_at_raw:
            expires_at = datetime.fromisoformat(expires_at_raw)
            if expires_at <= datetime.now(timezone.utc):
                del self._store[cache_key]
                return None
        return payload

    async def set_cached_result(
        self,
        text: str,
        options: MiniMaxSynthesisOptions,
        value: Dict[str, Any],
    ) -> None:
        cache_key = build_tts_cache_key(text, options)
        payload = dict(value)
        payload["expires_at"] = (
            (datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds))
            .replace(microsecond=0)
            .isoformat()
        )
        self._store[cache_key] = payload
