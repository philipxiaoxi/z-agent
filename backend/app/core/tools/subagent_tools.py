"""dispatch_subagent 工具：主 agent 通过此工具派发子 agent 执行复杂子任务。

子 agent 拥有与主 agent 相同的工具集（除本工具外，不能递归派发），独立完成
多步工具调用后返回最终文本回复。中间过程不进主 agent 的 LLM 历史，只通过
subagent_* 事件实时推送到前端 subagent block。
"""
from __future__ import annotations

import logging

from agno.tools.function import Function

from app.agent.dispatch import SubAgentDispatchContext

logger = logging.getLogger(__name__)


def make_subagent_tool(dispatch_ctx: SubAgentDispatchContext) -> Function:
    async def dispatch_subagent(task: str) -> str:
        return await dispatch_ctx.dispatch_active(task)

    return Function(
        name="dispatch_subagent",
        description=(
            "派发子 agent 执行复杂子任务。子 agent 拥有与主 agent 相同的工具集"
            "（除本工具外，不能递归派发），独立完成多步工具调用后返回最终文本回复。"
            "适用于：需要多步工具链的独立子任务（如「整理某目录所有图片并统计」、"
            "「搜索全盘大于 1GB 的文件并汇总」）。"
            "不适用于：单步工具调用或简单问答——这些直接用对应工具即可。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "交给子 agent 的任务描述，应清晰、自包含、可独立执行",
                },
            },
            "required": ["task"],
        },
        entrypoint=dispatch_subagent,
    )
