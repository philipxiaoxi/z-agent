from __future__ import annotations

import json
from uuid import uuid4

from .builder import merge_segments, extract_thinking


def serialize_llm_messages(segments: list[dict], store_thinking: bool) -> list[dict]:
    merged = merge_segments(segments)
    thinking_content = extract_thinking(merged)

    llm_msgs: list[dict] = []
    pending_text = ""
    tool_call_queue: list[str] = []

    for seg in merged:
        if seg["type"] == "text":
            pending_text += seg["content"]
        elif seg["type"] == "tool_call":
            if pending_text.strip():
                msg: dict = {"role": "assistant", "content": pending_text.strip()}
                if store_thinking and thinking_content:
                    msg["reasoning_content"] = thinking_content
                llm_msgs.append(msg)
                pending_text = ""
            call_id = f"call_{uuid4().hex[:8]}"
            tool_call_queue.append(call_id)
            last = llm_msgs[-1] if llm_msgs else None
            if last and last["role"] == "assistant" and last.get("tool_calls"):
                last["tool_calls"].append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": seg["tool"],
                        "arguments": json.dumps(seg["args"], ensure_ascii=False),
                    },
                })
            else:
                llm_msgs.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": seg["tool"],
                            "arguments": json.dumps(seg["args"], ensure_ascii=False),
                        },
                    }],
                })
        elif seg["type"] == "tool_result":
            call_id = tool_call_queue.pop(0) if tool_call_queue else f"call_{uuid4().hex[:8]}"
            llm_msgs.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": seg["result"],
                "name": seg["tool"],
            })

    if pending_text.strip():
        msg = {"role": "assistant", "content": pending_text.strip()}
        if store_thinking and thinking_content:
            msg["reasoning_content"] = thinking_content
        llm_msgs.append(msg)

    return llm_msgs
