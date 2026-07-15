"""SubAgentDispatchContext 及相关纯逻辑函数的单元测试。

用 asyncio.run() 驱动 async 方法，不引入 pytest-asyncio 依赖。
"""
from __future__ import annotations

import asyncio

from app.agent.dispatch import (
    SubAgentDispatchContext,
    _accumulate_step,
    agent_event_to_step,
)
from app.agent.events import AgentEvent


class FakeTransport:
    """记录所有 emit 调用，供断言。"""

    def __init__(self) -> None:
        self.emitted: list[dict] = []

    async def emit(self, event: dict) -> None:
        self.emitted.append(event)


class FakeSubRunner:
    """模拟 SubAgentRunner：调用时依次触发预设事件，返回最终文本。"""

    def __init__(self, events: list[AgentEvent], final_response: str = "done") -> None:
        self._events = events
        self._final_response = final_response
        self.call_count = 0
        self.last_task: str | None = None
        self.last_subagent_id: str | None = None

    async def run(self, task: str, subagent_id: str, emit_callback) -> str:
        self.call_count += 1
        self.last_task = task
        self.last_subagent_id = subagent_id
        for ev in self._events:
            await emit_callback(subagent_id, ev)
        return self._final_response


class FailingSubRunner:
    """总是抛异常的 SubRunner。"""

    async def run(self, task: str, subagent_id: str, emit_callback) -> str:
        raise RuntimeError("boom")


def _make_segment(subagent_id: str = "s1") -> dict:
    return {
        "type": "subagent",
        "id": subagent_id,
        "task": "",
        "steps": [],
        "result": "",
        "done": False,
    }


class TestAgentEventToStep:
    def test_text(self):
        step = agent_event_to_step(AgentEvent("text", {"content": "hello"}))
        assert step == {"step_type": "text", "content": "hello"}

    def test_thinking(self):
        step = agent_event_to_step(AgentEvent("thinking", {"content": "思考"}))
        assert step == {"step_type": "thinking", "content": "思考"}

    def test_tool_start(self):
        ev = AgentEvent("tool_start", {"id": "1", "tool": "list_files", "args": {"path": "/"}})
        step = agent_event_to_step(ev)
        assert step == {"step_type": "tool_start", "tool": "list_files", "args": {"path": "/"}}

    def test_tool_result(self):
        ev = AgentEvent("tool_result", {"id": "1", "tool": "list_files", "result": "ok"})
        step = agent_event_to_step(ev)
        assert step == {"step_type": "tool_result", "tool": "list_files", "result": "ok"}

    def test_run_error(self):
        step = agent_event_to_step(AgentEvent("run_error", {"content": "failed"}))
        assert step == {"step_type": "error", "content": "failed"}

    def test_done_returns_none(self):
        assert agent_event_to_step(AgentEvent("done", {})) is None

    def test_unknown_kind_returns_none(self):
        assert agent_event_to_step(AgentEvent("unknown_kind", {})) is None


class TestAccumulateStep:
    def test_consecutive_text_merged(self):
        steps: list[dict] = []
        _accumulate_step(steps, {"step_type": "text", "content": "a"})
        _accumulate_step(steps, {"step_type": "text", "content": "b"})
        assert len(steps) == 1
        assert steps[0]["content"] == "ab"

    def test_consecutive_thinking_merged(self):
        steps: list[dict] = []
        _accumulate_step(steps, {"step_type": "thinking", "content": "x"})
        _accumulate_step(steps, {"step_type": "thinking", "content": "y"})
        assert len(steps) == 1
        assert steps[0]["content"] == "xy"

    def test_text_then_thinking_creates_new(self):
        steps: list[dict] = []
        _accumulate_step(steps, {"step_type": "text", "content": "a"})
        _accumulate_step(steps, {"step_type": "thinking", "content": "b"})
        assert len(steps) == 2
        assert steps[0]["step_type"] == "text"
        assert steps[1]["step_type"] == "thinking"

    def test_tool_start_always_new_entry(self):
        steps: list[dict] = []
        _accumulate_step(steps, {"step_type": "tool_start", "tool": "t1", "args": {}})
        _accumulate_step(steps, {"step_type": "tool_start", "tool": "t2", "args": {}})
        assert len(steps) == 2

    def test_first_step_on_empty_list(self):
        steps: list[dict] = []
        _accumulate_step(steps, {"step_type": "text", "content": "first"})
        assert len(steps) == 1
        assert steps[0]["content"] == "first"


class TestSubAgentDispatchContext:
    def test_tool_name_is_dispatch_subagent(self):
        ctx = SubAgentDispatchContext(FakeTransport(), FakeSubRunner([], "x"))
        assert ctx.tool_name == "dispatch_subagent"

    def test_dispatch_active_without_bind_returns_error(self):
        ctx = SubAgentDispatchContext(FakeTransport(), FakeSubRunner([], "x"))
        result = asyncio.run(ctx.dispatch_active("task"))
        assert "未就绪" in result

    def test_full_dispatch_flow(self):
        events = [
            AgentEvent("text", {"content": "子agent开始"}),
            AgentEvent("tool_start", {"id": "t1", "tool": "list_files", "args": {"path": "/"}}),
            AgentEvent("tool_result", {"id": "t1", "tool": "list_files", "result": "ok"}),
        ]
        transport = FakeTransport()
        runner = FakeSubRunner(events, final_response="共5个文件")
        ctx = SubAgentDispatchContext(transport, runner)

        segment = _make_segment("s1")
        ctx.bind("s1", segment)

        result = asyncio.run(ctx.dispatch_active("统计文件"))

        assert result == "共5个文件"
        assert runner.last_task == "统计文件"
        assert runner.last_subagent_id == "s1"
        # steps 累积到 segment
        assert len(segment["steps"]) == 3
        assert segment["steps"][0] == {"step_type": "text", "content": "子agent开始"}
        assert segment["steps"][1] == {"step_type": "tool_start", "tool": "list_files", "args": {"path": "/"}}
        assert segment["steps"][2] == {"step_type": "tool_result", "tool": "list_files", "result": "ok"}
        # emit 顺序: start → 3x step → end
        emit_types = [e["type"] for e in transport.emitted]
        assert emit_types == ["subagent_start", "subagent_step", "subagent_step", "subagent_step", "subagent_end"]
        assert transport.emitted[0] == {"type": "subagent_start", "id": "s1", "task": "统计文件"}
        assert transport.emitted[-1] == {"type": "subagent_end", "id": "s1", "result": "共5个文件"}

    def test_text_chunks_accumulated_in_steps(self):
        events = [
            AgentEvent("text", {"content": "a"}),
            AgentEvent("text", {"content": "b"}),
            AgentEvent("text", {"content": "c"}),
        ]
        transport = FakeTransport()
        runner = FakeSubRunner(events, final_response="ok")
        ctx = SubAgentDispatchContext(transport, runner)

        segment = _make_segment("s1")
        ctx.bind("s1", segment)
        asyncio.run(ctx.dispatch_active("task"))

        assert len(segment["steps"]) == 1
        assert segment["steps"][0]["content"] == "abc"

    def test_runner_exception_still_emits_end(self):
        transport = FakeTransport()
        ctx = SubAgentDispatchContext(transport, FailingSubRunner())

        segment = _make_segment("s1")
        ctx.bind("s1", segment)

        result = asyncio.run(ctx.dispatch_active("task"))

        assert "失败" in result
        emit_types = [e["type"] for e in transport.emitted]
        assert emit_types == ["subagent_start", "subagent_end"]
        assert transport.emitted[-1]["result"] == result

    def test_unbind_clears_active(self):
        ctx = SubAgentDispatchContext(FakeTransport(), FakeSubRunner([], "x"))
        ctx.bind("s1", _make_segment("s1"))
        ctx.unbind("s1")
        result = asyncio.run(ctx.dispatch_active("task"))
        assert "未就绪" in result

    def test_explicit_dispatch_with_subagent_id(self):
        """直接调 dispatch(task, subagent_id) 而非 dispatch_active。"""
        events = [AgentEvent("text", {"content": "hi"})]
        transport = FakeTransport()
        runner = FakeSubRunner(events, final_response="ret")
        ctx = SubAgentDispatchContext(transport, runner)

        segment = _make_segment("fixed_id")
        ctx.bind("fixed_id", segment)

        result = asyncio.run(ctx.dispatch("go", "fixed_id"))

        assert result == "ret"
        assert segment["steps"] == [{"step_type": "text", "content": "hi"}]
        assert transport.emitted[0]["id"] == "fixed_id"
