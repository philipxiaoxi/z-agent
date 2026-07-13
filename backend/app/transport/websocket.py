from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect


class WebSocketTransport:
    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def emit(self, event: dict) -> None:
        await self._ws.send_text(json.dumps(event, ensure_ascii=False))

    async def receive(self) -> dict | None:
        try:
            raw = await self._ws.receive_text()
            return json.loads(raw)
        except WebSocketDisconnect:
            return None

    async def aclose(self) -> None:
        pass
