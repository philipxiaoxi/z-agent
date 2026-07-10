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


@router.websocket("/ws")
async def agent_ws(ws: WebSocket):
    await ws.accept()
    ctx = ConversationContext()

    confirm_mgr = ConfirmManager(lambda d: asyncio.ensure_future(_send(ws, d)))

    async def _on_workdir_changed(path: str) -> None:
        ctx.workdir = path
        await _send(ws, {"type": "workdir_changed", "path": path})

    try:
        tools = await get_tools(
            confirm_mgr, workdir_ctx=ctx,
            on_workdir_changed=_on_workdir_changed,
            send_to_frontend=lambda d: asyncio.ensure_future(_send(ws, d)),
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

                user_content_for_llm = user_content
                if ctx.workdir:
                    user_content_for_llm = f"[当前工作目录：{ctx.workdir}]\n{user_content}"
                ctx.add_user(user_content_for_llm)

                text_buf = ""
                full_response = ""
                segments: list[dict] = []

                def _flush_text() -> None:
                    nonlocal text_buf
                    if text_buf:
                        segments.append({"type": "text", "content": text_buf})

                async for event in agent.arun(
                    ctx.get_history(),
                    stream=True,
                    stream_events=True,
                    session_id=ctx.session_id,
                ):
                    et = event.event if hasattr(event, "event") else type(event).__name__

                    if et in ("ToolCallStarted",):
                        if text_buf:
                            _flush_text()
                            await _send(ws, {"type": "text", "content": text_buf})
                            text_buf = ""
                        tool = getattr(event, "tool", None)
                        if tool:
                            segments.append({"type": "tool_call", "tool": tool.tool_name or "", "args": tool.tool_args or {}})
                            await _send(ws, {
                                "type": "tool_start",
                                "id": tool.tool_call_id or str(uuid4()),
                                "tool": tool.tool_name or "",
                                "args": tool.tool_args or {},
                            })

                    elif et in ("ToolCallCompleted",):
                        if text_buf:
                            _flush_text()
                            await _send(ws, {"type": "text", "content": text_buf})
                            text_buf = ""
                        tool = getattr(event, "tool", None)
                        if tool:
                            result = tool.result
                            if isinstance(result, (dict, list)):
                                result = json.dumps(result, ensure_ascii=False, indent=2)
                            else:
                                result = str(result) if result is not None else ""
                            segments.append({"type": "tool_result", "tool": tool.tool_name or "", "result": result})
                            await _send(ws, {
                                "type": "tool_result",
                                "id": tool.tool_call_id or str(uuid4()),
                                "tool": tool.tool_name or "",
                                "result": result,
                            })

                    elif et == "ToolCallError":
                        if text_buf:
                            _flush_text()
                            await _send(ws, {"type": "text", "content": text_buf})
                            text_buf = ""
                        tool = getattr(event, "tool", None)
                        if tool:
                            err = f"错误: {tool.tool_call_error}"
                            segments.append({"type": "tool_result", "tool": tool.tool_name or "", "result": err})
                            await _send(ws, {
                                "type": "tool_result",
                                "id": tool.tool_call_id or str(uuid4()),
                                "tool": tool.tool_name or "",
                                "result": err,
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
                                segments.append({"type": "text", "content": text_buf})
                                await _send(ws, {"type": "text", "content": text_buf})
                                text_buf = ""

                if text_buf:
                    segments.append({"type": "text", "content": text_buf})
                    await _send(ws, {"type": "text", "content": text_buf})

                await _send(ws, {"type": "done"})

                if not session_id:
                    continue
                if not full_response and not any(s["type"] in ("tool_call", "tool_result") for s in segments):
                    continue

                # 合并连续文本片段，避免流式拆碎
                merged: list[dict] = []
                for seg in segments:
                    if seg["type"] == "text" and merged and merged[-1]["type"] == "text":
                        merged[-1]["content"] += seg["content"]
                    else:
                        merged.append(seg)

                # 从 merged 重建 blocks（给前端），以及 llm_content（给 ctx，含工具信息）
                blocks: list[dict] = []
                llm_parts: list[str] = []

                for seg in merged:
                    if seg["type"] == "text":
                        if seg["content"].strip():
                            blocks.append({"id": str(uuid4()), "type": "text", "content": seg["content"], "collapsed": False})
                            llm_parts.append(seg["content"])
                    elif seg["type"] == "tool_call":
                        blocks.append({"id": str(uuid4()), "type": "tool_call", "tool": seg["tool"], "args": seg["args"], "collapsed": True})
                        llm_parts.append(f"\n[调用工具: {seg['tool']}]\n参数: {json.dumps(seg['args'], ensure_ascii=False)}")
                    elif seg["type"] == "tool_result":
                        blocks.append({"id": str(uuid4()), "type": "tool_result", "tool": seg["tool"], "result": seg["result"], "collapsed": True})
                        llm_parts.append(f"返回: {seg['result']}\n")

                llm_content = "\n".join(llm_parts).strip()
                ctx.add_assistant(llm_content)

                # 写入 session store
                session_store.append_messages(session_id, [
                    {"id": str(uuid4()), "role": "user", "blocks": [{"id": str(uuid4()), "type": "text", "content": user_content, "collapsed": False}]},
                    {"id": str(uuid4()), "role": "assistant", "blocks": blocks},
                ])

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
