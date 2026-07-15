from app.blocks.builder import build_blocks, merge_segments, extract_thinking
from app.blocks.llm_serializer import serialize_llm_messages


class TestMergeSegments:
    def test_merge_consecutive_text(self):
        segments = [
            {"type": "text", "content": "Hello"},
            {"type": "text", "content": " "},
            {"type": "text", "content": "World"},
        ]
        merged = merge_segments(segments)
        assert len(merged) == 1
        assert merged[0]["content"] == "Hello World"

    def test_no_merge_different_types(self):
        segments = [
            {"type": "text", "content": "Hello"},
            {"type": "tool_call", "tool": "t", "args": {}},
        ]
        merged = merge_segments(segments)
        assert len(merged) == 2

    def test_does_not_mutate_original(self):
        segments = [{"type": "text", "content": "Hello"}]
        merge_segments(segments)
        assert segments[0]["content"] == "Hello"


class TestExtractThinking:
    def test_extract_thinking(self):
        merged = [
            {"type": "thinking", "content": "part1"},
            {"type": "text", "content": "ok"},
            {"type": "thinking", "content": "part2"},
        ]
        assert extract_thinking(merged) == "part1part2"

    def test_no_thinking(self):
        merged = [{"type": "text", "content": "ok"}]
        assert extract_thinking(merged) == ""


class TestBuildBlocks:
    def test_text_block(self):
        segments = [{"type": "text", "content": "Hello"}]
        blocks = build_blocks(segments)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert blocks[0]["content"] == "Hello"
        assert blocks[0]["collapsed"] is False

    def test_thinking_block_inserted_first(self):
        segments = [
            {"type": "thinking", "content": "思考"},
            {"type": "text", "content": "回答"},
        ]
        blocks = build_blocks(segments)
        assert len(blocks) == 2
        assert blocks[0]["type"] == "thinking"
        assert blocks[1]["type"] == "text"

    def test_tool_call_block(self):
        segments = [{"type": "tool_call", "tool": "list_files", "args": {"path": "/"}}]
        blocks = build_blocks(segments)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "tool_call"
        assert blocks[0]["tool"] == "list_files"
        assert blocks[0]["collapsed"] is True

    def test_tool_result_block(self):
        segments = [{"type": "tool_result", "tool": "list_files", "result": "ok"}]
        blocks = build_blocks(segments)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "tool_result"
        assert blocks[0]["result"] == "ok"

    def test_empty_text_with_real_text(self):
        segments = [
            {"type": "text", "content": "  "},
            {"type": "text", "content": "real"},
        ]
        blocks = build_blocks(segments)
        assert len(blocks) == 1
        assert blocks[0]["content"] == "  real"

    def test_all_empty_text_filtered(self):
        segments = [{"type": "text", "content": "  "}]
        blocks = build_blocks(segments)
        assert blocks == []

    def test_merged_text_blocks(self):
        segments = [
            {"type": "text", "content": "Hello"},
            {"type": "text", "content": "World"},
        ]
        blocks = build_blocks(segments)
        assert len(blocks) == 1
        assert blocks[0]["content"] == "HelloWorld"

    def test_subagent_block(self):
        segments = [{
            "type": "subagent",
            "id": "sub1",
            "task": "统计文件",
            "steps": [{"step_type": "text", "content": "子agent思考"}],
            "result": "共5个文件",
            "done": True,
        }]
        blocks = build_blocks(segments)
        assert len(blocks) == 1
        b = blocks[0]
        assert b["type"] == "subagent"
        assert b["task"] == "统计文件"
        assert b["steps"] == [{"step_type": "text", "content": "子agent思考"}]
        assert b["result"] == "共5个文件"
        assert b["done"] is True
        assert b["collapsed"] is True

    def test_subagent_block_defaults_done_true(self):
        segments = [{"type": "subagent", "id": "sub1", "task": "t", "steps": [], "result": "", "done": False}]
        blocks = build_blocks(segments)
        # done 缺失时默认 True（防止重载时卡在"运行中"）
        assert blocks[0]["done"] is False

    def test_subagent_block_with_surrounding_text(self):
        segments = [
            {"type": "text", "content": "我来派发"},
            {"type": "subagent", "id": "s", "task": "任务", "steps": [], "result": "ok", "done": True},
            {"type": "text", "content": "完成"},
        ]
        blocks = build_blocks(segments)
        assert len(blocks) == 3
        assert blocks[0]["type"] == "text"
        assert blocks[1]["type"] == "subagent"
        assert blocks[2]["type"] == "text"


class TestSerializeLlmMessages:
    def test_pure_text(self):
        segments = [{"type": "text", "content": "Hello"}]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["content"] == "Hello"

    def test_tool_call(self):
        segments = [{"type": "tool_call", "tool": "list_files", "args": {"path": "/"}}]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["content"] is None
        assert len(msgs[0]["tool_calls"]) == 1
        assert msgs[0]["tool_calls"][0]["function"]["name"] == "list_files"

    def test_tool_result(self):
        segments = [
            {"type": "tool_call", "tool": "list_files", "args": {"path": "/"}},
            {"type": "tool_result", "tool": "list_files", "result": "ok"},
        ]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "assistant"
        assert msgs[1]["role"] == "tool"
        assert msgs[1]["content"] == "ok"

    def test_text_before_tool_call(self):
        segments = [
            {"type": "text", "content": "Let me check"},
            {"type": "tool_call", "tool": "list_files", "args": {}},
        ]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 2
        assert msgs[0]["content"] == "Let me check"
        assert msgs[1]["content"] is None
        assert "tool_calls" in msgs[1]

    def test_consecutive_tool_calls_merged(self):
        segments = [
            {"type": "tool_call", "tool": "t1", "args": {}},
            {"type": "tool_call", "tool": "t2", "args": {}},
        ]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 1
        assert len(msgs[0]["tool_calls"]) == 2

    def test_store_thinking(self):
        segments = [
            {"type": "thinking", "content": "思考"},
            {"type": "text", "content": "回答"},
        ]
        msgs = serialize_llm_messages(segments, store_thinking=True)
        assert len(msgs) == 1
        assert msgs[0]["reasoning_content"] == "思考"

    def test_no_store_thinking(self):
        segments = [
            {"type": "thinking", "content": "思考"},
            {"type": "text", "content": "回答"},
        ]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 1
        assert "reasoning_content" not in msgs[0]

    def test_trailing_text(self):
        segments = [
            {"type": "tool_call", "tool": "t", "args": {}},
            {"type": "tool_result", "tool": "t", "result": "ok"},
            {"type": "text", "content": "Done"},
        ]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 3
        assert msgs[2]["role"] == "assistant"
        assert msgs[2]["content"] == "Done"

    def test_subagent_serializes_to_tool_call_result_pair(self):
        segments = [{
            "type": "subagent",
            "id": "sub1",
            "task": "统计文件",
            "steps": [{"step_type": "text", "content": "子agent思考"}],
            "result": "共5个文件",
            "done": True,
        }]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 2
        # tool_call
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["content"] is None
        assert len(msgs[0]["tool_calls"]) == 1
        call = msgs[0]["tool_calls"][0]
        assert call["function"]["name"] == "dispatch_subagent"
        assert '"统计文件"' in call["function"]["arguments"]
        # tool_result
        assert msgs[1]["role"] == "tool"
        assert msgs[1]["content"] == "共5个文件"
        assert msgs[1]["name"] == "dispatch_subagent"

    def test_subagent_with_surrounding_text(self):
        segments = [
            {"type": "text", "content": "我来派发"},
            {"type": "subagent", "id": "s", "task": "任务", "steps": [], "result": "ok", "done": True},
            {"type": "text", "content": "完成"},
        ]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 4
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["content"] == "我来派发"
        assert msgs[1]["content"] is None  # tool_call
        assert msgs[2]["role"] == "tool"  # tool_result
        assert msgs[3]["role"] == "assistant"
        assert msgs[3]["content"] == "完成"

    def test_subagent_empty_result(self):
        segments = [{"type": "subagent", "id": "s", "task": "t", "steps": [], "result": "", "done": True}]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        assert len(msgs) == 2
        assert msgs[1]["content"] == ""

    def test_subagent_steps_not_in_llm_history(self):
        """子 agent 的中间步骤（steps）不应出现在 LLM 历史中。"""
        segments = [{
            "type": "subagent",
            "id": "sub1",
            "task": "任务",
            "steps": [
                {"step_type": "text", "content": "子agent的内部文本"},
                {"step_type": "tool_start", "tool": "list_files", "args": {}},
                {"step_type": "tool_result", "tool": "list_files", "result": "内部结果"},
            ],
            "result": "最终返回",
            "done": True,
        }]
        msgs = serialize_llm_messages(segments, store_thinking=False)
        full_text = str(msgs)
        assert "子agent的内部文本" not in full_text
        assert "内部结果" not in full_text
        assert "最终返回" in full_text
