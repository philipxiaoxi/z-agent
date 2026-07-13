from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from app.agent.events import AgentEvent
from app.agent.runner import AgentRunner
from app.blocks import build_blocks, serialize_llm_messages
from app.core.config import settings
from app.core.context import ConversationContext
from app.core.tools.confirm import ConfirmManager
from app.session import SessionManager
from app.transport.base import Transport

logger = logging.getLogger(__name__)


def _agent_event_to_msg(ev: AgentEvent) -> dict | None:
    if ev.kind == "text":
        return {"type": "text", "content": ev.data["content"]}
    if ev.kind == "thinking":
        return {"type": "thinking", "content": ev.data["content"]}
    if ev.kind == "tool_start":
        return {"type": "tool_start", "id": ev.data["id"], "tool": ev.data["tool"], "args": ev.data["args"]}
    if ev.kind == "tool_result":
        return {"type": "tool_result", "id": ev.data["id"], "tool": ev.data["tool"], "result": ev.data["result"]}
    if ev.kind == "run_error":
        return {"type": "error", "content": ev.data["content"]}
    return None


class ConversationOrchestrator:
    def __init__(
        self,
        transport: Transport,
        runner: AgentRunner,
        ctx: ConversationContext,
        confirm_mgr: ConfirmManager,
        sessions: SessionManager,
    ) -> None:
        self._transport = transport
        self._runner = runner
        self._ctx = ctx
        self._confirm = confirm_mgr
        self._sessions = sessions
        self._msg_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def serve(self) -> None:
        recv_task = asyncio.create_task(self._receiver())
        try:
            while True:
                data = await self._msg_queue.get()
                if data.get("type") == "__close__":
                    break
                await self._handle_message(data)
        finally:
            recv_task.cancel()

    async def _receiver(self) -> None:
        try:
            while True:
                data = await self._transport.receive()
                if data is None:
                    break
                msg_type = data.get("type")
                if msg_type == "confirm":
                    self._confirm.resolve(data["id"], data.get("approved", False))
                elif msg_type in ("set_workdir", "restore_workdir"):
                    self._ctx.workdir = data.get("path", "")
                    await self._transport.emit({"type": "workdir_changed", "path": self._ctx.workdir})
                    logger.info("workdir %s to %s", msg_type, self._ctx.workdir)
                elif msg_type == "set_session":
                    self._sessions.switch(data.get("session_id", ""))
                    logger.info("session switched to %s", data.get("session_id", ""))
                elif msg_type == "workdir_changed":
                    pass
                else:
                    await self._msg_queue.put(data)
        finally:
            await self._msg_queue.put({"type": "__close__"})

    async def _handle_message(self, data: dict) -> None:
        msg_type = data.get("type")
        if msg_type == "message":
            await self._handle_chat(data)
        elif msg_type == "confirm":
            self._confirm.resolve(data["id"], data.get("approved", False))
        else:
            await self._transport.emit({"type": "error", "content": f"unknown message type: {msg_type}"})

    async def _handle_chat(self, data: dict) -> None:
        session_id = data.get("session_id", "") or self._ctx.session_id
        user_content = data.get("content", "")

        if session_id and session_id != self._ctx.session_id:
            self._sessions.switch(session_id)

        user_content_for_llm = user_content
        if self._ctx.workdir:
            user_content_for_llm = f"[当前工作目录：{self._ctx.workdir}]\n{user_content}"
        self._ctx.add_user(user_content_for_llm)

        store_thinking = settings.STORE_THINKING_IN_CONTEXT
        segments: list[dict] = []
        full_response = ""

        async for ev in self._runner.run(self._ctx.get_history(), self._ctx.session_id):
            if ev.kind == "done":
                segments = ev.data["segments"]
                full_response = ev.data["full_response"]
            else:
                msg = _agent_event_to_msg(ev)
                if msg:
                    await self._transport.emit(msg)

        if session_id and (full_response or any(s["type"] in ("tool_call", "tool_result", "thinking") for s in segments)):
            blocks = build_blocks(segments)
            llm_msgs = serialize_llm_messages(segments, store_thinking)

            if llm_msgs:
                self._ctx.append_messages(llm_msgs)

            self._sessions.save(self._ctx.session_id,
                history=self._ctx.get_history(),
                messages=[
                    {"id": str(uuid4()), "role": "user", "blocks": [{"id": str(uuid4()), "type": "text", "content": user_content, "collapsed": False}]},
                    {"id": str(uuid4()), "role": "assistant", "blocks": blocks},
                ])

        await self._transport.emit({"type": "done"})
