from __future__ import annotations

import json
from uuid import uuid4

from .events import AgentEvent


class EventNormalizer:
    """将 agno 流式事件归一化为 AgentEvent，同时累积 segments 供后续 blocks/llm 序列化使用。"""

    def __init__(self) -> None:
        self._text_buf: str = ""
        self._thinking_buf: str = ""
        self._segments: list[dict] = []
        self._full_response: str = ""

    @property
    def segments(self) -> list[dict]:
        return list(self._segments)

    @property
    def full_response(self) -> str:
        return self._full_response

    def feed(self, event: object) -> list[AgentEvent]:
        et = event.event if hasattr(event, "event") else type(event).__name__

        if et == "ToolCallStarted":
            return self._on_tool_call_started(event)
        if et == "ToolCallCompleted":
            return self._on_tool_call_completed(event)
        if et == "ToolCallError":
            return self._on_tool_call_error(event)
        if et == "RunError":
            return self._on_run_error(event)
        if et in ("RunContent", "IntermediateRunContent"):
            return self._on_run_content(event)
        if et == "ReasoningContentDelta":
            return self._on_reasoning_delta(event)
        return []

    def flush(self) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        if self._text_buf:
            self._segments.append({"type": "text", "content": self._text_buf})
            events.append(AgentEvent("text", {"content": self._text_buf}))
            self._text_buf = ""
        if self._thinking_buf:
            self._segments.append({"type": "thinking", "content": self._thinking_buf})
            self._thinking_buf = ""
        return events

    def _flush_text(self) -> list[AgentEvent]:
        if self._text_buf:
            content = self._text_buf
            self._segments.append({"type": "text", "content": content})
            self._text_buf = ""
            return [AgentEvent("text", {"content": content})]
        return []

    def _flush_thinking_to_segments(self) -> None:
        if self._thinking_buf:
            self._segments.append({"type": "thinking", "content": self._thinking_buf})
            self._thinking_buf = ""

    def _on_tool_call_started(self, event: object) -> list[AgentEvent]:
        events = self._flush_text()
        self._flush_thinking_to_segments()
        tool = getattr(event, "tool", None)
        if tool:
            self._segments.append({
                "type": "tool_call",
                "tool": tool.tool_name or "",
                "args": tool.tool_args or {},
            })
            events.append(AgentEvent("tool_start", {
                "id": tool.tool_call_id or str(uuid4()),
                "tool": tool.tool_name or "",
                "args": tool.tool_args or {},
            }))
        return events

    def _on_tool_call_completed(self, event: object) -> list[AgentEvent]:
        events = self._flush_text()
        self._flush_thinking_to_segments()
        tool = getattr(event, "tool", None)
        if tool:
            result = tool.result
            if isinstance(result, (dict, list)):
                result = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                result = str(result) if result is not None else ""
            self._segments.append({
                "type": "tool_result",
                "tool": tool.tool_name or "",
                "result": result,
            })
            events.append(AgentEvent("tool_result", {
                "id": tool.tool_call_id or str(uuid4()),
                "tool": tool.tool_name or "",
                "result": result,
            }))
        return events

    def _on_tool_call_error(self, event: object) -> list[AgentEvent]:
        events = self._flush_text()
        self._flush_thinking_to_segments()
        tool = getattr(event, "tool", None)
        if tool:
            err = f"错误: {tool.tool_call_error}"
            self._segments.append({
                "type": "tool_result",
                "tool": tool.tool_name or "",
                "result": err,
            })
            events.append(AgentEvent("tool_result", {
                "id": tool.tool_call_id or str(uuid4()),
                "tool": tool.tool_name or "",
                "result": err,
            }))
        return events

    def _on_run_error(self, event: object) -> list[AgentEvent]:
        content = getattr(event, "content", None)
        return [AgentEvent("run_error", {
            "content": str(content) if content else "未知错误",
        })]

    def _on_run_content(self, event: object) -> list[AgentEvent]:
        events: list[AgentEvent] = []
        chunk = getattr(event, "content", None)
        reasoning_chunk = getattr(event, "reasoning_content", None)

        if chunk is None and not reasoning_chunk:
            return events

        if chunk is not None:
            if chunk == "":
                self._text_buf += "\n"
                self._full_response += "\n"
            else:
                self._text_buf += str(chunk)
                self._full_response += str(chunk)
                if "\n" in self._text_buf or len(self._text_buf) >= 2:
                    events.extend(self._flush_text())

        if reasoning_chunk:
            events.extend(self._on_reasoning(str(reasoning_chunk)))

        return events

    def _on_reasoning_delta(self, event: object) -> list[AgentEvent]:
        delta = getattr(event, "reasoning_content", None)
        if delta:
            return self._on_reasoning(str(delta))
        return []

    def _on_reasoning(self, delta: str) -> list[AgentEvent]:
        self._thinking_buf += delta
        return [AgentEvent("thinking", {"content": delta})]
