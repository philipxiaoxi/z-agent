from types import SimpleNamespace

from app.agent.event_normalizer import EventNormalizer


def _text_event(content):
    return SimpleNamespace(event="RunContent", content=content)


def _reasoning_event(content):
    return SimpleNamespace(event="ReasoningContentDelta", reasoning_content=content)


def _tool_start_event(tool_name="list_files", tool_args=None, tool_call_id="call_1"):
    tool = SimpleNamespace(
        tool_name=tool_name,
        tool_args=tool_args or {},
        tool_call_id=tool_call_id,
        result=None,
        tool_call_error=None,
    )
    return SimpleNamespace(event="ToolCallStarted", tool=tool)


def _tool_complete_event(tool_name="list_files", result="ok", tool_call_id="call_1"):
    tool = SimpleNamespace(
        tool_name=tool_name,
        tool_args={},
        tool_call_id=tool_call_id,
        result=result,
        tool_call_error=None,
    )
    return SimpleNamespace(event="ToolCallCompleted", tool=tool)


def _tool_error_event(tool_name="list_files", error="boom", tool_call_id="call_1"):
    tool = SimpleNamespace(
        tool_name=tool_name,
        tool_args={},
        tool_call_id=tool_call_id,
        result=None,
        tool_call_error=error,
    )
    return SimpleNamespace(event="ToolCallError", tool=tool)


def _run_error_event(content="something went wrong"):
    return SimpleNamespace(event="RunError", content=content)


class TestEventNormalizer:
    def test_pure_text_flush(self):
        n = EventNormalizer()
        events = n.feed(_text_event("Hello"))
        assert len(events) == 1
        assert events[0].kind == "text"
        assert events[0].data["content"] == "Hello"
        assert n.full_response == "Hello"
        assert n.segments == [{"type": "text", "content": "Hello"}]

    def test_text_buffering(self):
        n = EventNormalizer()
        events = n.feed(_text_event("a"))
        assert events == []
        events = n.feed(_text_event("b"))
        assert len(events) == 1
        assert events[0].data["content"] == "ab"

    def test_empty_chunk_adds_newline(self):
        n = EventNormalizer()
        events = n.feed(_text_event(""))
        assert events == []
        assert n.full_response == "\n"
        events = n.flush()
        assert len(events) == 1
        assert events[0].data["content"] == "\n"

    def test_thinking_immediate(self):
        n = EventNormalizer()
        events = n.feed(_reasoning_event("思考中"))
        assert len(events) == 1
        assert events[0].kind == "thinking"
        assert events[0].data["content"] == "思考中"
        assert n.segments == []
        n.flush()
        assert n.segments == [{"type": "thinking", "content": "思考中"}]

    def test_tool_call_flushes_text_and_thinking(self):
        n = EventNormalizer()
        n.feed(_text_event("ab"))
        n.feed(_reasoning_event("思考"))
        assert n.segments == [{"type": "text", "content": "ab"}]
        events = n.feed(_tool_start_event())
        kinds = [e.kind for e in events]
        assert "tool_start" in kinds
        seg_types = [s["type"] for s in n.segments]
        assert seg_types == ["text", "thinking", "tool_call"]

    def test_tool_complete(self):
        n = EventNormalizer()
        events = n.feed(_tool_complete_event(result="file1\nfile2"))
        assert len(events) == 1
        assert events[0].kind == "tool_result"
        assert events[0].data["result"] == "file1\nfile2"

    def test_tool_complete_dict_result(self):
        n = EventNormalizer()
        events = n.feed(_tool_complete_event(result={"key": "value"}))
        assert events[0].kind == "tool_result"
        assert '"key"' in events[0].data["result"]

    def test_tool_error(self):
        n = EventNormalizer()
        events = n.feed(_tool_error_event(error="boom"))
        assert len(events) == 1
        assert events[0].kind == "tool_result"
        assert "错误" in events[0].data["result"]
        assert "boom" in events[0].data["result"]

    def test_run_error(self):
        n = EventNormalizer()
        events = n.feed(_run_error_event("failed"))
        assert len(events) == 1
        assert events[0].kind == "run_error"
        assert events[0].data["content"] == "failed"

    def test_run_error_no_content(self):
        n = EventNormalizer()
        events = n.feed(_run_error_event(None))
        assert events[0].data["content"] == "未知错误"

    def test_flush_remaining_text(self):
        n = EventNormalizer()
        n.feed(_text_event("a"))
        events = n.flush()
        assert len(events) == 1
        assert events[0].kind == "text"
        assert events[0].data["content"] == "a"

    def test_mixed_scenario(self):
        n = EventNormalizer()
        all_events: list = []
        all_events.extend(n.feed(_text_event("Hello")))
        all_events.extend(n.feed(_reasoning_event("思考")))
        all_events.extend(n.feed(_tool_start_event(tool_name="list_files", tool_args={"path": "/"})))
        all_events.extend(n.feed(_tool_complete_event(result="ok")))
        all_events.extend(n.feed(_text_event("World")))
        all_events.extend(n.flush())

        kinds = [e.kind for e in all_events]
        assert kinds == ["text", "thinking", "tool_start", "tool_result", "text"]

        seg_types = [s["type"] for s in n.segments]
        assert seg_types == ["text", "thinking", "tool_call", "tool_result", "text"]
        assert n.full_response == "HelloWorld"
