from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)


class DifyEventStreamer:
    """消耗 Dify SSE 流，累积最终结果文本。

    一期直接累积返回；后续可扩展为 yield 原始事件流供人工介入使用。

    结果策略：
    - 若收到过 text_chunk，只用流式文本（避免与 outputs 重复）
    - 否则回退到 workflow_finished.outputs 中的字符串字段
    """

    @staticmethod
    async def accumulate(response: httpx.Response) -> str:
        text_chunks: list[str] = []
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:]
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if not isinstance(event, dict):
                continue

            event_type = event.get("event")
            data = event.get("data", {})

            if event_type == "text_chunk":
                text = data.get("text", "")
                if text:
                    text_chunks.append(text)

            elif event_type == "workflow_finished":
                status = data.get("status", "")
                if status == "failed":
                    error = data.get("error", "未知错误")
                    raise RuntimeError(f"工作流执行失败: {error}")

                if text_chunks:
                    return "".join(text_chunks)

                outputs = data.get("outputs") or {}
                output_parts: list[str] = []
                if isinstance(outputs, dict):
                    for val in outputs.values():
                        if isinstance(val, str) and val.strip():
                            output_parts.append(val)
                return "\n".join(output_parts)

            elif event_type == "error":
                msg = data.get("message", "工作流执行错误")
                raise RuntimeError(msg)

            elif event_type == "workflow_paused":
                raise NotImplementedError("人工介入尚未支持")

        # 流意外结束（无 workflow_finished）时，尽量返回已收到的文本
        return "".join(text_chunks)

    @staticmethod
    async def iter_events(response: httpx.Response) -> AsyncIterator[dict]:
        """yield 原始 Dify 事件，供后续扩展使用。"""
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:]
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            yield event
