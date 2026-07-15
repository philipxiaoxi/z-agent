"""子 Agent 派发上下文：协调主 orchestrator segments 与子 agent 事件流。

主 orchestrator 在检测到 dispatch_subagent 的 tool_start 时，bind 当前 subagent
segment 引用到本上下文；子 agent 运行期间，每个 AgentEvent 经 emit_callback
累积为 step 到该 segment，并以 subagent_step 事件实时推送给前端。tool_result
时主 orchestrator 完成 segment 的 result/done 字段并 unbind。

这样子 agent 的中间过程对主 agent 的 LLM 历史不可见（仅记 tool_call/tool_result），
但在前端 subagent block 中完整可见。
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from app.agent.events import SUBAGENT_TOOL_NAME, AgentEvent
from app.agent.subagent import SubAgentRunner
from app.transport.base import Transport

logger = logging.getLogger(__name__)

SubagentEmit = Callable[[str, AgentEvent], Awaitable[None]]


def agent_event_to_step(ev: AgentEvent) -> dict | None:
    """把子 agent 的 AgentEvent 转成前端 step dict。返回 None 表示跳过。"""
    if ev.kind == "text":
        return {"step_type": "text", "content": ev.data["content"]}
    if ev.kind == "thinking":
        return {"step_type": "thinking", "content": ev.data["content"]}
    if ev.kind == "tool_start":
        return {"step_type": "tool_start", "tool": ev.data["tool"], "args": ev.data["args"]}
    if ev.kind == "tool_result":
        return {"step_type": "tool_result", "tool": ev.data["tool"], "result": ev.data["result"]}
    if ev.kind == "run_error":
        return {"step_type": "error", "content": ev.data["content"]}
    return None


def _accumulate_step(steps: list[dict], step: dict) -> None:
    """累积 step：连续的同类型 text/thinking chunk 合并，避免 steps 数组爆炸。"""
    step_type = step["step_type"]
    if step_type in ("text", "thinking") and steps and steps[-1]["step_type"] == step_type:
        steps[-1]["content"] += step["content"]
        return
    steps.append(step)


class SubAgentDispatchContext:
    """协调主 orchestrator 与子 agent 之间的状态传递。"""

    def __init__(self, transport: Transport, sub_runner: SubAgentRunner) -> None:
        self._transport = transport
        self._sub_runner = sub_runner
        # subagent_id -> 当前活跃的 subagent segment dict 引用
        self._active: dict[str, dict] = {}

    @property
    def tool_name(self) -> str:
        return SUBAGENT_TOOL_NAME

    def bind(self, subagent_id: str, segment: dict) -> None:
        """主 orchestrator 在 tool_start(dispatch_subagent) 时调用。"""
        self._active[subagent_id] = segment

    def unbind(self, subagent_id: str) -> None:
        self._active.pop(subagent_id, None)

    async def dispatch(self, task: str, subagent_id: str) -> str:
        """执行子 agent，事件实时推送 + 累积到 segment，返回最终文本。"""
        return await self._dispatch(task, subagent_id)

    async def dispatch_active(self, task: str) -> str:
        """供 dispatch_subagent 工具 entrypoint 调用。

        v1 不支持嵌套，同时只有一个 subagent 活跃，从 _active 取其 id。
        """
        if not self._active:
            return "❌ 子 agent 派发上下文未就绪"
        subagent_id = next(iter(self._active))
        return await self._dispatch(task, subagent_id)

    async def _dispatch(self, task: str, subagent_id: str) -> str:
        segment = self._active.get(subagent_id)
        await self._transport.emit({
            "type": "subagent_start", "id": subagent_id, "task": task,
        })
        try:
            result = await self._sub_runner.run(
                task=task,
                subagent_id=subagent_id,
                emit_callback=self._make_emit_cb(subagent_id, segment),
            )
        except Exception as exc:
            logger.exception("dispatch subagent %s failed", subagent_id)
            result = f"❌ 子 agent 执行失败: {exc}"
        if segment is not None:
            segment["result"] = result
            segment["done"] = True
        await self._transport.emit({
            "type": "subagent_end", "id": subagent_id, "result": result,
        })
        return result

    def _make_emit_cb(self, subagent_id: str, segment: dict | None) -> SubagentEmit:
        async def emit_cb(_sid: str, ev: AgentEvent) -> None:
            step = agent_event_to_step(ev)
            if step is None:
                return
            if segment is not None:
                _accumulate_step(segment["steps"], step)
            await self._transport.emit({
                "type": "subagent_step", "id": subagent_id, **step,
            })

        return emit_cb
