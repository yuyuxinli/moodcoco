from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from services.shared.tts.types import MiniMaxAccountConfig


@dataclass
class MiniMaxAccountState:
    config: MiniMaxAccountConfig
    client: Any
    current_inflight: int = 0
    failure_count: int = 0
    success_count: int = 0
    recent_failure_count: int = 0
    recent_avg_latency_ms: Optional[float] = None
    last_failure_reason: Optional[str] = None
    last_failure_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None

    def is_available(self, now: Optional[datetime] = None) -> bool:
        current_time = now or datetime.now(timezone.utc)
        if not self.config.enabled:
            return False
        if self.cooldown_until and self.cooldown_until > current_time:
            return False
        return self.current_inflight < self.config.max_inflight

    def mark_failure(
        self,
        *,
        failure_reason: str,
        cooldown_seconds: int,
        occurred_at: datetime,
    ) -> None:
        self.failure_count += 1
        self.recent_failure_count += 1
        self.last_failure_reason = failure_reason
        self.last_failure_at = occurred_at
        self.cooldown_until = occurred_at + timedelta(seconds=cooldown_seconds)

    def mark_success(self, *, latency_ms: float) -> None:
        self.success_count += 1
        self.failure_count = 0
        self.recent_failure_count = 0
        self.last_failure_reason = None
        self.cooldown_until = None
        if self.recent_avg_latency_ms is None:
            self.recent_avg_latency_ms = latency_ms
        else:
            self.recent_avg_latency_ms = round((self.recent_avg_latency_ms * 0.7) + (latency_ms * 0.3), 3)


class MiniMaxAccountLease:
    def __init__(self, router: "MiniMaxAccountRouter", account: MiniMaxAccountState) -> None:
        self._router = router
        self.account = account
        self._released = False

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        await self._router.release(self.account)


@dataclass
class MiniMaxAccountRouter:
    accounts: list[MiniMaxAccountState]
    cooldown_seconds: int = 30
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self) -> Optional[MiniMaxAccountLease]:
        async with self._lock:
            if not self.accounts:
                return None
            now = datetime.now(timezone.utc)
            ordered = sorted(self.accounts, key=lambda item: (item.config.priority, item.config.account_id))
            available = [account for account in ordered if account.is_available(now)]
            if not available:
                return None
            best_priority = min(account.config.priority for account in available)
            priority_pool = [account for account in available if account.config.priority == best_priority]
            if len(priority_pool) == 1:
                selected = priority_pool[0]
            else:
                candidates = random.sample(priority_pool, 2) if len(priority_pool) > 2 else priority_pool[:2]
                selected = min(candidates, key=self._selection_score)
            selected.current_inflight += 1
            return MiniMaxAccountLease(self, selected)
        return None

    async def release(self, account: MiniMaxAccountState) -> None:
        async with self._lock:
            account.current_inflight = max(0, account.current_inflight - 1)

    async def mark_failure(
        self,
        account: MiniMaxAccountState,
        *,
        failure_reason: Optional[str] = None,
        failure_status_code: Optional[int] = None,
        failure_status_msg: Optional[str] = None,
    ) -> None:
        async with self._lock:
            normalized_reason = self._normalize_failure_reason(
                failure_reason=failure_reason,
                failure_status_code=failure_status_code,
                failure_status_msg=failure_status_msg,
            )
            cooldown_seconds = self._cooldown_seconds_for(account, normalized_reason)
            account.mark_failure(
                failure_reason=normalized_reason,
                cooldown_seconds=cooldown_seconds,
                occurred_at=datetime.now(timezone.utc),
            )

    async def mark_success(self, account: MiniMaxAccountState, *, latency_ms: float) -> None:
        async with self._lock:
            account.mark_success(latency_ms=latency_ms)

    @staticmethod
    def _selection_score(account: MiniMaxAccountState) -> tuple[float, int, float, str]:
        latency = account.recent_avg_latency_ms if account.recent_avg_latency_ms is not None else float("inf")
        return (
            float(account.current_inflight),
            account.failure_count,
            latency,
            account.config.account_id,
        )

    @staticmethod
    def _normalize_failure_reason(
        *,
        failure_reason: Optional[str],
        failure_status_code: Optional[int],
        failure_status_msg: Optional[str],
    ) -> str:
        status_msg = (failure_status_msg or "").lower()
        if failure_status_code == 1008 or "insufficient balance" in status_msg:
            return "insufficient_balance"
        if failure_reason == "empty_audio":
            return "empty_audio"
        if failure_reason in {"http_401", "http_403", "auth_error"}:
            return "auth_error"
        if failure_reason in {"network_error", "upstream_5xx"}:
            return failure_reason
        return failure_reason or "unknown_error"

    def _cooldown_seconds_for(self, account: MiniMaxAccountState, normalized_reason: str) -> int:
        if normalized_reason in {"insufficient_balance", "auth_error"}:
            return 60 * 60 * 24
        if normalized_reason == "empty_audio":
            return 5
        if normalized_reason in {"network_error", "upstream_5xx"}:
            return min(20, max(5, 5 * (2 ** max(0, account.failure_count))))
        return self.cooldown_seconds
