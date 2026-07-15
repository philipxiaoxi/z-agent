from __future__ import annotations

import json
from uuid import uuid4

from app.agent.events import SUBAGENT_TOOL_NAME

from .builder import merge_segments, extract_thinking


def serialize_llm_messages(segments: list[dict], store_thinking: bool) -> list[dict]:
    """把展示用 segments 反序列化为 LLM tool_calling 格式的消息列表。

    subagent 段会被转为一对 dispatch_subagent 的 tool_call + tool_result，
    使主 agent 的 LLM 历史只记得"派发了子 agent 处理 X，返回 Y"，
    子 agent 的中间过程（text/thinking/工具调用）不进 LLM 历史。
    """
    merged = merge_segments(segments)
    thinking_content = extract_thinking(merged)

    llm_msgs: list[dict] = []
    pending_text: str = ""
    tool_call_queue: list[str] = []

    def flush_pending_text() -> None:
        nonlocal pending_text
        if not pending_text.strip():
            return
        msg = {"role": "assistant", "content": pending_text.strip()}
        if store_thinking and thinking_content:
            msg["reasoning_content"] = thinking_content
        llm_msgs.append(msg)
        pending_text = ""

    def emit_tool_call(tool_name: str, args: dict) -> None:
        flush_pending_text()
        call_id = f"call_{uuid4().hex[:8]}"
        tool_call_queue.append(call_id)
        last = llm_msgs[-1] if llm_msgs else None
        tool_call_entry = {
            "id": call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(args, ensure_ascii=False),
            },
        }
        if last and last["role"] == "assistant" and last.get("tool_calls"):
            last["tool_calls"].append(tool_call_entry)
        else:
            llm_msgs.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [tool_call_entry],
            })

    def emit_tool_result(tool_name: str, result: str) -> None:
        call_id = tool_call_queue.pop(0) if tool_call_queue else f"call_{uuid4().hex[:8]}"
        llm_msgs.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": result,
            "name": tool_name,
        })

    for seg in merged:
        seg_type = seg["type"]
        if seg_type == "text":
            pending_text += seg["content"]
        elif seg_type == "tool_call":
            emit_tool_call(seg["tool"], seg["args"])
        elif seg_type == "tool_result":
            emit_tool_result(seg["tool"], seg["result"])
        elif seg_type == "subagent":
            emit_tool_call(SUBAGENT_TOOL_NAME, {"task": seg.get("task", "")})
            emit_tool_result(SUBAGENT_TOOL_NAME, seg.get("result", ""))
        elif seg_type == "cancelled":
            llm_msgs.append({"role": "system", "content": "用户终止了上一轮 AI 回复，后续对话基于已有上下文继续。"})

    flush_pending_text()
    return llm_msgs
