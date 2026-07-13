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


@dataclass
class AgentEvent:
    kind: AgentEventKind
    data: dict = field(default_factory=dict)
