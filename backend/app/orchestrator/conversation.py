from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from app.agent.events import AgentEvent
from app.agent.runner import AgentRunner
from app.blocks import merge_segments, serialize_llm_messages
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


def _accumulate_segment(segments: list[dict], kind: str, data: dict) -> None:
    if kind in ("text", "thinking"):
        content = data["content"]
        if segments and segments[-1]["type"] == kind:
            segments[-1]["content"] += content
        else:
            segments.append({"type": kind, "content": content})
    elif kind == "tool_start":
        segments.append({"type": "tool_call", "tool": data["tool"], "args": data["args"]})
    elif kind == "tool_result":
        segments.append({"type": "tool_result", "tool": data["tool"], "result": data["result"]})


def _strip_orphan_tool_calls(segments: list[dict]) -> list[dict]:
    result: list[dict] = []
    pending: list[dict] = []
    for seg in segments:
        if seg["type"] == "tool_call":
            pending.append(seg)
        elif seg["type"] == "tool_result":
            if pending:
                result.append(pending.pop(0))
                result.append(seg)
        elif seg["type"] == "text":
            result.extend(pending)
            pending.clear()
            result.append(seg)
        else:
            result.append(seg)
    return result


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
                elif msg_type == "cancel_run":
                    self._confirm.cancel_run()
                    logger.info("user cancelled the current run")
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
        cancelled = False

        run_gen = self._runner.run(self._ctx.get_history(), self._ctx.session_id)
        try:
            async for ev in run_gen:
                if self._confirm.is_cancelled():
                    self._confirm.reset_cancel()
                    cancelled = True
                    break
                if ev.kind == "done":
                    continue
                msg = _agent_event_to_msg(ev)
                if msg:
                    await self._transport.emit(msg)
                    _accumulate_segment(segments, ev.kind, ev.data)
        finally:
            await run_gen.aclose()

        save_segments = None
        ctx_to_append = None

        if cancelled:
            save_segments = _strip_orphan_tool_calls(segments)
            save_segments.append({"type": "cancelled", "content": "对话已终止"})
            ctx_to_append = [{"role": "system", "content": "用户终止了上一轮 AI 回复，后续对话基于已有上下文继续。"}]
            await self._transport.emit({"type": "cancelled"})
        elif segments:
            has_substance = any(s["type"] in ("tool_call", "tool_result", "thinking") or s.get("content", "").strip() for s in segments)
            if has_substance:
                save_segments = merge_segments(segments)
                ctx_to_append = serialize_llm_messages(segments, store_thinking)

        if save_segments is not None and session_id:
            if ctx_to_append:
                self._ctx.append_messages(ctx_to_append)
            self._sessions.save(self._ctx.session_id,
                messages=[
                    {"id": str(uuid4()), "role": "user", "content": user_content},
                    {"id": str(uuid4()), "role": "assistant", "segments": save_segments},
                ])

        await self._transport.emit({"type": "done"})
