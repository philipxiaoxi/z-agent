import json
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from mcp.client.stdio import StdioServerParameters

from agno.agent import Agent
from agno.tools.mcp import MCPTools
from agno.models.deepseek import DeepSeek

from app.core.config import settings
from app.core.context import ConversationContext
from app.core.prompts import SYSTEM_DESCRIPTION, SYSTEM_INSTRUCTIONS

logger = logging.getLogger(__name__)
router = APIRouter()

mcp_params = StdioServerParameters(command="zcli", args=["mcp"])
_mcp: MCPTools | None = None
_agent: Agent | None = None


async def _ensure_agent() -> Agent:
    global _mcp, _agent

    if _agent is not None:
        return _agent

    if _mcp is None:
        _mcp = MCPTools(server_params=mcp_params)
        await _mcp.connect()
        logger.info("MCPTools connected, tools: %s", list(_mcp.functions.keys()))

    _agent = Agent(
        model=DeepSeek(id="deepseek-v4-flash", api_key=settings.DEEPSEEK_API_KEY),
        tools=[_mcp],
        markdown=True,
        description=SYSTEM_DESCRIPTION,
        instructions=SYSTEM_INSTRUCTIONS,
    )
    return _agent


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data, ensure_ascii=False))


@router.websocket("/ws")
async def agent_ws(ws: WebSocket):
    await ws.accept()
    ctx = ConversationContext()
    logger.info("agent WebSocket connected, session=%s", ctx.session_id)

    try:
        agent = await _ensure_agent()
        logger.info("agent ready, tools: %s", [t.name for t in agent.tools])

        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "message":
                user_content = data.get("content", "")
                ctx.add_user(user_content)
                text_buf = ""
                full_response = ""

                async for event in agent.arun(
                    ctx.get_history(),
                    stream=True,
                    stream_events=True,
                    session_id=ctx.session_id,
                ):
                    et = event.event if hasattr(event, "event") else type(event).__name__

                    if et in ("ToolCallStarted",):
                        if text_buf:
                            await _send(ws, {"type": "text", "content": text_buf})
                            text_buf = ""
                        tool = getattr(event, "tool", None)
                        if tool:
                            await _send(ws, {
                                "type": "tool_start",
                                "id": tool.tool_call_id or str(uuid4()),
                                "tool": tool.tool_name or "",
                                "args": tool.tool_args or {},
                            })

                    elif et in ("ToolCallCompleted",):
                        if text_buf:
                            await _send(ws, {"type": "text", "content": text_buf})
                            text_buf = ""
                        tool = getattr(event, "tool", None)
                        if tool:
                            result = tool.result
                            if isinstance(result, (dict, list)):
                                result = json.dumps(result, ensure_ascii=False, indent=2)
                            else:
                                result = str(result) if result is not None else ""
                            await _send(ws, {
                                "type": "tool_result",
                                "id": tool.tool_call_id or str(uuid4()),
                                "tool": tool.tool_name or "",
                                "result": result,
                            })

                    elif et == "ToolCallError":
                        if text_buf:
                            await _send(ws, {"type": "text", "content": text_buf})
                            text_buf = ""
                        tool = getattr(event, "tool", None)
                        if tool:
                            await _send(ws, {
                                "type": "tool_result",
                                "id": tool.tool_call_id or str(uuid4()),
                                "tool": tool.tool_name or "",
                                "result": f"错误: {tool.tool_call_error}",
                            })

                    elif et == "RunError":
                        content = getattr(event, "content", None)
                        await _send(ws, {"type": "error", "content": str(content) if content else "未知错误"})

                    elif et in ("RunContent", "IntermediateRunContent"):
                        chunk = getattr(event, "content", None)
                        if chunk is None:
                            continue
                        if chunk == "":
                            text_buf += "\n"
                            full_response += "\n"
                        else:
                            text_buf += str(chunk)
                            full_response += str(chunk)
                            if "\n" in text_buf or len(text_buf) >= 2:
                                await _send(ws, {"type": "text", "content": text_buf})
                                text_buf = ""

                if text_buf:
                    await _send(ws, {"type": "text", "content": text_buf})
                if full_response:
                    ctx.add_assistant(full_response)
                await _send(ws, {"type": "done"})

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
