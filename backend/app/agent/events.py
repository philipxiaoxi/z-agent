from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AgentEventKind = Literal[
    "text",
    "thinking",
    "tool_start",
    "tool_result",
    "run_error",
    "done",
]

# 子 Agent 派发工具的名称，供 dispatch / serializer / prompt 共享，
# 单点定义避免散落字面量在重命名时漏改。
SUBAGENT_TOOL_NAME = "dispatch_subagent"


@dataclass
class AgentEvent:
    kind: AgentEventKind
    data: dict = field(default_factory=dict)
