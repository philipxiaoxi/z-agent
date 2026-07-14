from __future__ import annotations

from uuid import uuid4


def merge_segments(segments: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for seg in segments:
        if seg["type"] == "text" and merged and merged[-1]["type"] == "text":
            merged[-1]["content"] += seg["content"]
        else:
            merged.append(dict(seg))
    return merged


def extract_thinking(merged: list[dict]) -> str:
    thinking_content = ""
    for seg in merged:
        if seg["type"] == "thinking":
            thinking_content += seg["content"]
    return thinking_content


def build_blocks(segments: list[dict]) -> list[dict]:
    merged = merge_segments(segments)
    thinking_content = extract_thinking(merged)

    blocks: list[dict] = []
    for seg in merged:
        if seg["type"] == "thinking":
            continue
        if seg["type"] == "text":
            if seg["content"].strip():
                blocks.append({
                    "id": str(uuid4()),
                    "type": "text",
                    "content": seg["content"],
                    "collapsed": False,
                })
        elif seg["type"] == "tool_call":
            blocks.append({
                "id": str(uuid4()),
                "type": "tool_call",
                "tool": seg["tool"],
                "args": seg["args"],
                "collapsed": True,
            })
        elif seg["type"] == "tool_result":
            blocks.append({
                "id": str(uuid4()),
                "type": "tool_result",
                "tool": seg["tool"],
                "result": seg["result"],
                "collapsed": True,
            })
        elif seg["type"] == "cancelled":
            blocks.append({
                "id": str(uuid4()),
                "type": "cancelled",
                "content": seg.get("content", "对话已终止"),
                "collapsed": False,
            })

    if thinking_content:
        blocks.insert(0, {
            "id": str(uuid4()),
            "type": "thinking",
            "content": thinking_content,
            "collapsed": False,
        })

    return blocks
