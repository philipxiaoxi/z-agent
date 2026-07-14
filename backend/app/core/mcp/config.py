from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    name: str
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    enabled: bool = True
    path_gate: bool = False

    command: str | None = None
    args: list[str] = field(default_factory=list)

    url: str | None = None
    headers: dict[str, str] | None = None

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "ServerConfig":
        return cls(
            name=name,
            transport=d.get("transport", "stdio"),
            enabled=d.get("enabled", True),
            path_gate=d.get("path_gate", False),
            command=d.get("command"),
            args=d.get("args", []),
            url=d.get("url"),
            headers=d.get("headers"),
        )


def load_mcp_config(path: str | None = None) -> list[ServerConfig]:
    import yaml

    if path is None:
        p = Path(__file__).parent.parent.parent.parent / "mcp_servers.yaml"
    else:
        p = Path(path)

    if not p.exists():
        logger.info("MCP config not found at %s, skip", p)
        return []

    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    servers = (raw or {}).get("servers", {})
    configs = [ServerConfig.from_dict(name, cfg) for name, cfg in servers.items()]
    logger.info("loaded %d MCP server config(s): %s", len(configs), [c.name for c in configs if c.enabled])
    return configs
