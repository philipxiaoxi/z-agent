"""子 Agent 运行器：派发独立 Agno Agent 实例执行子任务。

子 agent 与主 agent 共享同一批工具与模型，但拥有独立的 EventNormalizer
与 session_id，其中间过程（text/thinking/工具调用）不进主 agent 的 LLM 历史，
只通过 emit_callback 实时推送到前端 subagent block。
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from app.agent.event_normalizer import EventNormalizer
from app.agent.events import AgentEvent
from app.core.tools.confirm import ConfirmManager

logger = logging.getLogger(__name__)

EmitCallback = Callable[[str, AgentEvent], Awaitable[None]]


class SubAgentRunner:
    """派发独立 Agno Agent 执行子任务。

    每次调用创建新的 Agent 实例（Agno Agent 持有 per-run state），
    工具集由调用方提供（应过滤掉 dispatch_subagent 自身以防递归）。
    """

    def __init__(
        self,
        model: DeepSeek,
        base_tools: list,
        confirm_mgr: ConfirmManager,
        description: str,
        instructions: str,
    ) -> None:
        self._model = model
        self._base_tools = base_tools
        self._confirm_mgr = confirm_mgr
        self._description = description
        self._instructions = instructions

    async def run(
        self,
        task: str,
        subagent_id: str,
        emit_callback: EmitCallback,
    ) -> str:
        """执行子 agent，事件经 emit_callback 实时推送，返回最终文本。"""
        normalizer = EventNormalizer()
        sub_agent = Agent(
            model=self._model,
            tools=self._base_tools,
            markdown=True,
            description=self._description,
            instructions=self._instructions,
        )
        history = [{"role": "user", "content": task}]
        cancelled = False
        try:
            async for event in sub_agent.arun(
                history,
                stream=True,
                stream_events=True,
                session_id=f"sub_{subagent_id}",
            ):
                if self._confirm_mgr.is_cancelled():
                    cancelled = True
                    break
                for ev in normalizer.feed(event):
                    await emit_callback(subagent_id, ev)
            for ev in normalizer.flush():
                await emit_callback(subagent_id, ev)
        except Exception as exc:
            logger.exception("subagent %s failed", subagent_id)
            return f"❌ 子 agent 执行失败: {exc}"

        if cancelled:
            logger.info("subagent %s cancelled by user", subagent_id)
        return normalizer.full_response or ""
