from __future__ import annotations

from typing import AsyncIterator, Protocol

from agno.agent import Agent

from .events import AgentEvent
from .event_normalizer import EventNormalizer


class AgentRunner(Protocol):
    async def run(self, history: list[dict], session_id: str) -> AsyncIterator[AgentEvent]: ...


class AgnoAgentRunner:
    """封装 agno Agent，输出标准化 AgentEvent 流。"""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    async def run(self, history: list[dict], session_id: str) -> AsyncIterator[AgentEvent]:
        normalizer = EventNormalizer()
        async for event in self._agent.arun(
            history,
            stream=True,
            stream_events=True,
            session_id=session_id,
        ):
            for ev in normalizer.feed(event):
                yield ev
        for ev in normalizer.flush():
            yield ev
        yield AgentEvent("done", {
            "segments": normalizer.segments,
            "full_response": normalizer.full_response,
        })
