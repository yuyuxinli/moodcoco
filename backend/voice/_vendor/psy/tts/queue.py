from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Tuple

from backend.voice._vendor.psy.tts.router import MiniMaxAccountLease, MiniMaxAccountRouter


class MiniMaxTTSQueueCoordinator:
    def __init__(self, router: MiniMaxAccountRouter, poll_interval: float = 0.05) -> None:
        self._router = router
        self._poll_interval = poll_interval

    async def dispatch(
        self,
        operation: Callable[[MiniMaxAccountLease], Awaitable[Tuple]],
        timeout_seconds: float,
    ) -> Tuple:
        deadline = time.monotonic() + timeout_seconds
        while True:
            lease = await self._router.acquire()
            if lease:
                return await operation(lease)
            if time.monotonic() >= deadline:
                raise TimeoutError("TTS queue wait timed out")
            await asyncio.sleep(self._poll_interval)
