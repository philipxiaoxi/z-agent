import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from app.core.config import settings
from app.core.context import ConversationContext
from app.core.prompt.prompts import SYSTEM_DESCRIPTION, SYSTEM_INSTRUCTIONS
from app.core.tools import get_tools
from app.core.tools.confirm import ConfirmManager
from app.core import session_store

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局会话 LLM 历史缓存（session_id -> list[dict]）
_session_histories: dict[str, list[dict]] = {}


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data, ensure_ascii=False))


def _make_send_to_frontend(ws: WebSocket, file_list_collector: list[dict]):
    """创建 send_to_frontend 回调，同时收集 file_list 事件用于持久化"""
    def _send_and_collect(data: dict):
        asyncio.ensure_future(_send(ws, data))
        if data.get("type") == "file_list":
            file_list_collector.append({
                "id": str(uuid4()),
                "type": "file_list",
                "fileList": data.get("data"),
                "collapsed": False,
            })
    return _send_and_collect


@router.websocket("/ws")
async def agent_ws(ws: WebSocket):
    await ws.accept()
    ctx = ConversationContext()
    file_list_collector: list[dict] = []

    confirm_mgr = ConfirmManager(lambda d: asyncio.ensure_future(_send(ws, d)))

    async def _on_workdir_changed(path: str) -> None:
        ctx.workdir = path
        await _send(ws, {"type": "workdir_changed", "path": path})

    try:
        tools = await get_tools(
            confirm_mgr, workdir_ctx=ctx,
            on_workdir_changed=_on_workdir_changed,
            send_to_frontend=_make_send_to_frontend(ws, file_list_collector),
        )
        logger.info("agent tools: %s", [t.name for t in tools])
    except Exception as e:
        logger.error("failed to load tools: %s", e)
        await _send(ws, {"type": "error", "content": f"工具加载失败: {e}"})
        return

    agent = Agent(
        model=DeepSeek(id="deepseek-v4-flash", api_key=settings.DEEPSEEK_API_KEY),
        tools=tools,
        markdown=True,
        description=SYSTEM_DESCRIPTION,
        instructions=SYSTEM_INSTRUCTIONS,
    )
    msg_queue: asyncio.Queue[dict] = asyncio.Queue()

    logger.info("agent WebSocket connected, session=%s", ctx.session_id)

    async def receiver():
        try:
            while True:
                raw = await ws.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type")
                if msg_type == "confirm":
                    confirm_mgr.resolve(data["id"], data.get("approved", False))
                elif msg_type in ("set_workdir", "restore_workdir"):
                    ctx.workdir = data.get("path", "")
                    await _send(ws, {"type": "workdir_changed", "path": ctx.workdir})
                    logger.info("workdir %s to %s", msg_type, ctx.workdir)
                elif msg_type == "set_session":
                    session_id = data.get("session_id", "")
                    if ctx.session_id:
                        _session_histories[ctx.session_id] = ctx.get_history()
                    ctx.restore_history(_session_histories.get(session_id, []))
                    ctx.session_id = session_id
                    logger.info("session switched to %s", session_id)
                elif msg_type == "workdir_changed":
                    pass
                else:
                    await msg_queue.put(data)
        except WebSocketDisconnect:
            pass
        finally:
            await msg_queue.put({"type": "__close__"})

    recv_task = asyncio.create_task(receiver())

    try:
        while True:
            data = await msg_queue.get()
            msg_type = data.get("type")

            if msg_type == "__close__":
                break

            if msg_type == "message":
                session_id = data.get("session_id", "") or ctx.session_id
                user_content = data.get("content", "")

                # 切换 session 时保存/恢复 LLM 历史
                if session_id and session_id != ctx.session_id:
                    if ctx.session_id:
                        _session_histories[ctx.session_id] = ctx.get_history()
                    ctx.restore_history(_session_histories.get(session_id, []))
                    ctx.session_id = session_id

                # 构建用户消息（rich 格式用于持久化）
                user_msg = {
                    "id": str(uuid4()),
                    "role": "user",
                    "blocks": [{"id": str(uuid4()), "type": "text", "content": user_content, "collapsed": False}],
                }

                user_content_for_llm = user_content
                if ctx.workdir:
                    user_content_for_llm = f"[当前工作目录：{ctx.workdir}]\n{user_content}"
                ctx.add_user(user_content_for_llm)

                file_list_collector.clear()
                assistant_blocks: list[dict] = []
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
                            assistant_blocks.append({"id": str(uuid4()), "type": "text", "content": text_buf, "collapsed": False})
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
                            assistant_blocks.append({
                                "id": str(uuid4()),
                                "type": "tool_call",
                                "tool": tool.tool_name or "",
                                "args": tool.tool_args or {},
                                "collapsed": True,
                            })

                    elif et in ("ToolCallCompleted",):
                        if text_buf:
                            assistant_blocks.append({"id": str(uuid4()), "type": "text", "content": text_buf, "collapsed": False})
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
                            assistant_blocks.append({
                                "id": str(uuid4()),
                                "type": "tool_result",
                                "tool": tool.tool_name or "",
                                "result": result,
                                "collapsed": True,
                            })

                    elif et == "ToolCallError":
                        if text_buf:
                            assistant_blocks.append({"id": str(uuid4()), "type": "text", "content": text_buf, "collapsed": False})
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
                            assistant_blocks.append({
                                "id": str(uuid4()),
                                "type": "tool_result",
                                "tool": tool.tool_name or "",
                                "result": f"错误: {tool.tool_call_error}",
                                "collapsed": True,
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
                    assistant_blocks.append({"id": str(uuid4()), "type": "text", "content": text_buf, "collapsed": False})
                    await _send(ws, {"type": "text", "content": text_buf})

                if full_response:
                    ctx.add_assistant(full_response)

                await _send(ws, {"type": "done"})

                # 写入 session store
                assistant_blocks.extend(file_list_collector)
                messages_to_save = [user_msg, {"id": str(uuid4()), "role": "assistant", "blocks": assistant_blocks}]
                if session_id and (messages_to_save[0]["blocks"] or messages_to_save[1]["blocks"]):
                    session_store.append_messages(session_id, messages_to_save)

            elif msg_type == "confirm":
                confirm_mgr.resolve(data["id"], data.get("approved", False))

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
    finally:
        recv_task.cancel()
