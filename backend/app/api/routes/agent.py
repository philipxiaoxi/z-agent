import asyncio
import logging
import os

os.environ.setdefault("AGNO_TELEMETRY", "false")

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from app.agent.dispatch import SubAgentDispatchContext
from app.agent.runner import AgnoAgentRunner
from app.agent.subagent import SubAgentRunner
from app.core.config import settings
from app.core.context import ConversationContext
from app.core.prompt.prompts import SYSTEM_DESCRIPTION, SYSTEM_INSTRUCTIONS
from app.core.tools import get_tools
from app.core.tools.confirm import ConfirmManager
from app.core.tools.subagent_tools import make_subagent_tool
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

    confirm_mgr = ConfirmManager(lambda data: asyncio.create_task(transport.emit(data)))

    async def _on_workdir_changed(path: str) -> None:
        ctx.workdir = path
        await transport.emit({"type": "workdir_changed", "path": path})

    dify_pool = getattr(ws.app.state, "dify_pool", None)

    try:
        base_tools = await get_tools(
            confirm_mgr, workdir_ctx=ctx,
            on_workdir_changed=_on_workdir_changed,
            session_id=ctx.session_id,
            dify_pool=dify_pool,
        )
        logger.info("agent tools: %s", [t.name for t in base_tools])
    except Exception as e:
        logger.error("failed to load tools: %s", e)
        await transport.emit({"type": "error", "content": f"工具加载失败: {e}"})
        return

    model = DeepSeek(id="deepseek-v4-flash", api_key=settings.DEEPSEEK_API_KEY)

    sub_runner = SubAgentRunner(
        model=model,
        base_tools=base_tools,
        confirm_mgr=confirm_mgr,
        description=SYSTEM_DESCRIPTION,
        instructions=SYSTEM_INSTRUCTIONS,
    )
    dispatch_ctx = SubAgentDispatchContext(transport, sub_runner)
    dispatch_tool = make_subagent_tool(dispatch_ctx)

    agent = Agent(
        model=model,
        tools=base_tools + [dispatch_tool],
        markdown=True,
        description=SYSTEM_DESCRIPTION,
        instructions=SYSTEM_INSTRUCTIONS,
    )
    runner = AgnoAgentRunner(agent)
    sessions = SessionManager(ctx)
    orch = ConversationOrchestrator(transport, runner, ctx, confirm_mgr, sessions, dispatch_ctx)

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
