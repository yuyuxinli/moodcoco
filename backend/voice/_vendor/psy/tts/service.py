from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import httpx

from services.shared.tts.cache import MiniMaxTTSCacheStore
from services.shared.tts.client import MiniMaxTTSClient
from services.shared.tts.queue import MiniMaxTTSQueueCoordinator
from services.shared.tts.router import MiniMaxAccountRouter, MiniMaxAccountState
from services.shared.tts.types import MiniMaxAccountConfig, MiniMaxSynthesisOptions

log = logging.getLogger(__name__)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(float(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


def _classify_exception(exc: Exception) -> tuple[str, Optional[int], str]:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            return "auth_error", status_code, exc.response.text
        if status_code >= 500:
            return "upstream_5xx", status_code, exc.response.text
        return f"http_{status_code}", status_code, exc.response.text
    if isinstance(exc, httpx.RequestError):
        return "network_error", None, str(exc)
    return "unexpected_error", None, str(exc)


def load_minimax_account_configs(raw_settings: Any) -> list[MiniMaxAccountConfig]:
    raw_accounts = getattr(raw_settings, "MINIMAX_TTS_ACCOUNTS_JSON", None)
    if raw_accounts:
        account_items = json.loads(raw_accounts)
        configs = []
        for index, item in enumerate(account_items):
            configs.append(
                MiniMaxAccountConfig(
                    account_id=item.get("account_id") or f"account-{index + 1}",
                    api_key=item["api_key"],
                    model=item.get("model", getattr(raw_settings, "MINIMAX_TTS_MODEL", "speech-2.6-hd")),
                    voice_id=item.get("voice_id", getattr(raw_settings, "MINIMAX_TTS_VOICE_ID", "male-qn-qingse")),
                    speed=_safe_float(item.get("speed"), 1.0),
                    vol=_safe_float(item.get("vol"), 1.0),
                    pitch=_safe_int(item.get("pitch"), 0),
                    voice_modify_pitch=_safe_int(item.get("voice_modify_pitch"), getattr(raw_settings, "MINIMAX_TTS_VOICE_MODIFY_PITCH", -16)),
                    voice_modify_intensity=_safe_int(item.get("voice_modify_intensity"), getattr(raw_settings, "MINIMAX_TTS_VOICE_MODIFY_INTENSITY", -24)),
                    voice_modify_timbre=_safe_int(item.get("voice_modify_timbre"), getattr(raw_settings, "MINIMAX_TTS_VOICE_MODIFY_TIMBRE", 0)),
                    file_format=item.get("file_format", "mp3"),
                    enabled=bool(item.get("enabled", True)),
                    priority=_safe_int(item.get("priority"), 100),
                    max_inflight=_safe_int(item.get("max_inflight"), 8),
                )
            )
        return configs

    api_key = getattr(raw_settings, "MINIMAX_API_KEY", None)
    if not api_key:
        return []
    return [
        MiniMaxAccountConfig(
            account_id="default",
            api_key=api_key,
            model=getattr(raw_settings, "MINIMAX_TTS_MODEL", "speech-2.6-hd"),
            voice_id=getattr(raw_settings, "MINIMAX_TTS_VOICE_ID", "male-qn-qingse"),
            speed=_safe_float(getattr(raw_settings, "MINIMAX_TTS_SPEED", 1.0), 1.0),
            vol=_safe_float(getattr(raw_settings, "MINIMAX_TTS_VOLUME", 1.0), 1.0),
            pitch=_safe_int(getattr(raw_settings, "MINIMAX_TTS_PITCH", 0.0), 0),
            voice_modify_pitch=_safe_int(getattr(raw_settings, "MINIMAX_TTS_VOICE_MODIFY_PITCH", -16), -16),
            voice_modify_intensity=_safe_int(getattr(raw_settings, "MINIMAX_TTS_VOICE_MODIFY_INTENSITY", -24), -24),
            voice_modify_timbre=_safe_int(getattr(raw_settings, "MINIMAX_TTS_VOICE_MODIFY_TIMBRE", 0), 0),
            file_format="mp3",
            enabled=True,
            priority=100,
            max_inflight=_safe_int(getattr(raw_settings, "MINIMAX_TTS_MAX_INFLIGHT", 8), 8),
        )
    ]


class MiniMaxTTSService:
    def __init__(
        self,
        *,
        router: MiniMaxAccountRouter,
        cache_store: Optional[MiniMaxTTSCacheStore] = None,
        queue_coordinator: Optional[MiniMaxTTSQueueCoordinator] = None,
        queue_timeout_seconds: float = 10.0,
    ) -> None:
        self._router = router
        self._cache_store = cache_store
        self._queue = queue_coordinator or MiniMaxTTSQueueCoordinator(router)
        self._queue_timeout_seconds = queue_timeout_seconds

    @classmethod
    def from_settings(cls, raw_settings: Any) -> "MiniMaxTTSService":
        account_configs = load_minimax_account_configs(raw_settings)
        states = [
            MiniMaxAccountState(
                config=config,
                client=MiniMaxTTSClient(config, getattr(raw_settings, "AUDIO_OUTPUT_DIR", "audio_outputs")),
            )
            for config in account_configs
        ]
        router = MiniMaxAccountRouter(
            states,
            cooldown_seconds=_safe_int(getattr(raw_settings, "MINIMAX_TTS_COOLDOWN_SECONDS", 30), 30),
        )
        cache_store = MiniMaxTTSCacheStore(
            ttl_seconds=_safe_int(getattr(raw_settings, "MINIMAX_TTS_CACHE_TTL_SECONDS", 4 * 60 * 60), 4 * 60 * 60)
        )
        return cls(
            router=router,
            cache_store=cache_store,
            queue_coordinator=MiniMaxTTSQueueCoordinator(router),
            queue_timeout_seconds=_safe_float(getattr(raw_settings, "MINIMAX_TTS_QUEUE_TIMEOUT_SECONDS", 10.0), 10.0),
        )

    def _default_options(self) -> MiniMaxSynthesisOptions:
        if not self._router.accounts:
            return MiniMaxSynthesisOptions()
        return self._router.accounts[0].config.to_synthesis_options()

    async def synthesize_url(self, text: str) -> tuple[Optional[str], dict]:
        if not text or not text.strip():
            return None, {}
        options = self._default_options()
        if self._cache_store:
            try:
                cached = await self._cache_store.get_cached_result(text, options)
            except Exception:
                log.warning("MiniMax TTS cache lookup failed", exc_info=True)
                cached = None
            if cached:
                extra = dict(cached)
                audio_url = extra.pop("audio_url", None)
                return audio_url, extra

        async def _run(lease):
            started_at = time.perf_counter()
            try:
                audio_url, extra = await lease.account.client.synthesize_url(text, options)
                latency_ms = (time.perf_counter() - started_at) * 1000
                if audio_url:
                    await self._router.mark_success(lease.account, latency_ms=latency_ms)
                    if self._cache_store:
                        try:
                            await self._cache_store.set_cached_result(
                                text,
                                options,
                                {
                                    "audio_url": audio_url,
                                    "audio_length": extra.get("audio_length"),
                                    "subtitles": extra.get("subtitles"),
                                    "source_account_id": lease.account.config.account_id,
                                },
                            )
                        except Exception:
                            log.warning("MiniMax TTS cache write failed", exc_info=True)
                else:
                    log.warning(
                        "MiniMax TTS request returned empty audio url",
                        extra={
                            "account_id": lease.account.config.account_id,
                            "voice_id": options.voice_id,
                            "model": options.model,
                            "request_id": extra.get("request_id"),
                            "failure_reason": extra.get("failure_reason"),
                            "failure_status_code": extra.get("failure_status_code"),
                            "failure_status_msg": extra.get("failure_status_msg"),
                        },
                    )
                    await self._router.mark_failure(
                        lease.account,
                        failure_reason=extra.get("failure_reason"),
                        failure_status_code=extra.get("failure_status_code"),
                        failure_status_msg=extra.get("failure_status_msg"),
                    )
                return audio_url, extra
            except Exception as exc:
                failure_reason, failure_status_code, failure_status_msg = _classify_exception(exc)
                await self._router.mark_failure(
                    lease.account,
                    failure_reason=failure_reason,
                    failure_status_code=failure_status_code,
                    failure_status_msg=failure_status_msg,
                )
                raise
            finally:
                await lease.release()

        try:
            return await self._queue.dispatch(_run, self._queue_timeout_seconds)
        except TimeoutError:
            log.warning("MiniMax TTS queue timeout")
            return None, {}

    async def synthesize(self, text: str) -> tuple[Optional[str], dict]:
        if not self._router.accounts:
            return None, {}
        return await self._router.accounts[0].client.synthesize(text)

    async def synthesize_bytes(self, text: str) -> tuple[Optional[bytes], dict]:
        if not self._router.accounts:
            return None, {}
        return await self._router.accounts[0].client.synthesize_bytes(text)

    def get_audio_url(self, filename: str) -> str:
        return f"/api/speech/get_audio/{filename}"

    async def close(self) -> None:
        for account in self._router.accounts:
            await account.client.close()
