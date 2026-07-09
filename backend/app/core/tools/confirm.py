from __future__ import annotations

import asyncio
from uuid import uuid4
from typing import Any, Callable


class ConfirmManager:
    """确认管理器：发送确认请求到前端，异步等待用户回应"""

    def __init__(self, send_fn: Callable[[dict], None]) -> None:
        self._send = send_fn
        self._pending: dict[str, asyncio.Future] = {}

    def request(self, payload: dict) -> tuple[str, asyncio.Future]:
        """发送确认请求，返回 (confirm_id, Future)，用户回应后 Future.set_result(True/False)"""
        cid = payload.get("id") or uuid4().hex[:12]
        payload["id"] = cid
        future = asyncio.get_event_loop().create_future()
        self._pending[cid] = future
        self._send(payload)
        return cid, future

    def resolve(self, confirm_id: str, approved: bool) -> None:
        """外部调用（receiver 任务）唤醒等待中的 Future"""
        future = self._pending.get(confirm_id)
        if future is not None and not future.done():
            future.set_result(approved)

    def cleanup(self, confirm_id: str) -> None:
        self._pending.pop(confirm_id, None)

    @property
    def pending_count(self) -> int:
        return len(self._pending)
