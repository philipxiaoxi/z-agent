import asyncio
import logging
import os

os.environ.setdefault("AGNO_TELEMETRY", "false")

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from app.agent.runner import AgnoAgentRunner
from app.core.config import settings
from app.core.context import ConversationContext
from app.core.prompt.prompts import SYSTEM_DESCRIPTION, SYSTEM_INSTRUCTIONS
from app.core.tools import get_tools
from app.core.tools.confirm import ConfirmManager
from app.orchestrator.conversation import ConversationOrchestrator
from app.session import SessionManager
from app.transport.websocket import WebSocketTransport

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def agent_ws(ws: WebSocket):
    await ws.accept()
    transport = WebSocketTransport(ws)
    ctx = ConversationContext()

    confirm_mgr = ConfirmManager(lambda d: asyncio.ensure_future(transport.emit(d)))

    async def _on_workdir_changed(path: str) -> None:
        ctx.workdir = path
        await transport.emit({"type": "workdir_changed", "path": path})

    try:
        tools = await get_tools(
            confirm_mgr, workdir_ctx=ctx,
            on_workdir_changed=_on_workdir_changed,
            session_id=ctx.session_id,
        )
        logger.info("agent tools: %s", [t.name for t in tools])
    except Exception as e:
        logger.error("failed to load tools: %s", e)
        await transport.emit({"type": "error", "content": f"工具加载失败: {e}"})
        return

    agent = Agent(
        model=DeepSeek(id="deepseek-v4-flash", api_key=settings.DEEPSEEK_API_KEY),
        tools=tools,
        markdown=True,
        description=SYSTEM_DESCRIPTION,
        instructions=SYSTEM_INSTRUCTIONS,
    )
    runner = AgnoAgentRunner(agent)
    sessions = SessionManager(ctx)
    orch = ConversationOrchestrator(transport, runner, ctx, confirm_mgr, sessions)

    logger.info("agent WebSocket connected, session=%s", ctx.session_id)

    try:
        await orch.serve()
    except WebSocketDisconnect:
        logger.info("agent WebSocket disconnected")
    except Exception as e:
        logger.error("agent WebSocket error: %s", e)
        try:
            await transport.emit({"type": "error", "content": str(e)})
        except Exception:
            pass
