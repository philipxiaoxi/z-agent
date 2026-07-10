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

logger = logging.getLogger(__name__)
router = APIRouter()


async def _send(ws: WebSocket, data: dict) -> None:
    """向 WebSocket 客户端发送 JSON 消息"""
    await ws.send_text(json.dumps(data, ensure_ascii=False))


@router.websocket("/ws")
async def agent_ws(ws: WebSocket):
    """WebSocket 主入口：每个连接承载一次对话"""
    await ws.accept()
    ctx = ConversationContext()

    # --- 确认管理器 ---
    confirm_mgr = ConfirmManager(lambda d: asyncio.ensure_future(_send(ws, d)))

    # --- AI 设置工作目录后的回调（通知前端） ---
    async def _on_workdir_changed(path: str) -> None:
        ctx.workdir = path
        await _send(ws, {"type": "workdir_changed", "path": path})

    # --- 获取工具列表 ---
    try:
        tools = await get_tools(confirm_mgr, workdir_ctx=ctx,
                                on_workdir_changed=_on_workdir_changed,
                                send_to_frontend=lambda d: asyncio.ensure_future(_send(ws, d)))
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

    # ===================== 后台接收任务 =====================
    # 独立协程持续读取 WebSocket，将消息分类处理：
    #   confirm       → 直接 resolve，唤醒等待中的工具调用
    #   set_workdir   → 更新上下文 + 通知前端
    #   其余          → 放入 msg_queue 由主循环处理
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
                elif msg_type == "workdir_changed":
                    pass  # 服务端→客户端，忽略回环
                else:
                    await msg_queue.put(data)
        except WebSocketDisconnect:
            pass
        finally:
            await msg_queue.put({"type": "__close__"})

    recv_task = asyncio.create_task(receiver())

    # ===================== 主循环 =====================
    try:
        while True:
            data = await msg_queue.get()
            msg_type = data.get("type")

            if msg_type == "__close__":
                break

            # ---------- 用户消息 → Agent.arun() 流式响应 ----------
            if msg_type == "message":
                user_content = data.get("content", "")
                if ctx.workdir:
                    user_content = f"[当前工作目录：{ctx.workdir}]\n{user_content}"
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

                    # AI 开始调用工具 → 通知前端展示 tool_start 卡片
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

                    # 工具执行完成 → 通知前端展示 tool_result 卡片
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

                    # 工具调用出错
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

                    # Agent 整体运行出错
                    elif et == "RunError":
                        content = getattr(event, "content", None)
                        await _send(ws, {"type": "error", "content": str(content) if content else "未知错误"})

                    # 流式文本块 → 累积后发送前端
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

                # 流式结束：刷残留文本 + 保存助手回复到对话历史
                if text_buf:
                    await _send(ws, {"type": "text", "content": text_buf})
                if full_response:
                    ctx.add_assistant(full_response)
                await _send(ws, {"type": "done"})

            # ---------- 用户对确认弹窗的回应（兜底，通常由 receiver 直接处理）----------
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
