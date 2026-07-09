import json
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)
router = APIRouter()


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data, ensure_ascii=False))


async def _handle_message(ws: WebSocket, text: str) -> None:
    await _send(ws, {"type": "text", "content": f"收到: {text}\n\n正在处理..."})

    tool_id = str(uuid4())
    await _send(ws, {
        "type": "tool_start",
        "id": tool_id,
        "tool": "search_files",
        "args": {"keyword": text},
    })

    import asyncio
    await asyncio.sleep(0.3)

    await _send(ws, {
        "type": "tool_result",
        "id": tool_id,
        "tool": "search_files",
        "result": json.dumps([
            {"name": "backup_2026.zip", "path": "/sata12/data/backup_2026.zip", "size": "1.2 GB"},
            {"name": "readme.md", "path": "/sata12/data/readme.md", "size": "4 KB"},
        ], ensure_ascii=False, indent=2),
    })

    await _send(ws, {"type": "text", "content": "查询完成，共找到 2 个文件。"})
    await _send(ws, {"type": "done"})


@router.websocket("/ws")
async def agent_ws(ws: WebSocket):
    await ws.accept()
    logger.info("agent WebSocket connected")

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "message":
                await _handle_message(ws, data.get("content", ""))
            elif msg_type == "confirm":
                logger.info("confirm: id=%s approved=%s", data.get("id"), data.get("approved"))
            else:
                await _send(ws, {"type": "error", "content": f"unknown message type: {msg_type}"})
    except WebSocketDisconnect:
        logger.info("agent WebSocket disconnected")
    except Exception as e:
        logger.error("agent WebSocket error: %s", e)
        try:
            await _send(ws, {"type": "error", "content": str(e)})
        except Exception:
            pass
