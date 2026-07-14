from __future__ import annotations

import logging
from typing import Union

from mcp.client.stdio import StdioServerParameters
from agno.tools.mcp import MCPTools
from agno.tools.mcp.params import SSEClientParams, StreamableHTTPClientParams

from .config import ServerConfig

logger = logging.getLogger(__name__)

DynamicParams = Union[StdioServerParameters, SSEClientParams, StreamableHTTPClientParams]


class MCPRegistry:
    def __init__(self) -> None:
        self._instances: dict[str, MCPTools] = {}
        self._dynamic: dict[str, MCPTools] = {}

    async def get(self, cfg: ServerConfig) -> MCPTools:
        existing = self._instances.get(cfg.name)
        if existing is not None:
            return existing

        params = _build_server_params(cfg)
        mcp = MCPTools(server_params=params, name=f"mcp_{cfg.name}")
        await mcp.connect()
        logger.info("MCP [%s] connected, tools: %s", cfg.name, list(mcp.functions.keys()))
        self._instances[cfg.name] = mcp
        return mcp

    async def connect_dynamic(self, name: str, params: DynamicParams) -> MCPTools:
        existing = self._dynamic.get(name)
        if existing is not None:
            return existing

        mcp = MCPTools(server_params=params, name=name)
        await mcp.connect()
        logger.info("dynamic MCP [%s] connected, tools: %s", name, list(mcp.functions.keys()))
        self._dynamic[name] = mcp
        return mcp

    async def disconnect_dynamic(self, name: str) -> None:
        mcp = self._dynamic.pop(name, None)
        if mcp is None:
            return
        try:
            await mcp.close()
        except Exception:
            logger.warning("dynamic MCP [%s] cleanup error", name)

    def get_dynamic(self, name: str) -> MCPTools | None:
        return self._dynamic.get(name)

    async def close_all(self) -> None:
        for d in (self._dynamic, self._instances):
            for name in list(d.keys()):
                mcp = d.pop(name)
                try:
                    await mcp.close()
                except Exception:
                    logger.warning("MCP [%s] cleanup error", name)

    async def close(self, name: str) -> None:
        mcp = self._instances.pop(name, None)
        if mcp is None:
            return
        try:
            await mcp.close()
        except Exception:
            logger.warning("MCP [%s] cleanup error", name)


def _build_server_params(cfg: ServerConfig):
    if cfg.transport == "stdio":
        return StdioServerParameters(command=cfg.command, args=cfg.args)
    if cfg.transport == "sse":
        return SSEClientParams(url=cfg.url, headers=cfg.headers)
    if cfg.transport == "streamable-http":
        return StreamableHTTPClientParams(url=cfg.url, headers=cfg.headers)
    raise ValueError(f"unsupported MCP transport: {cfg.transport}")


_registry: MCPRegistry | None = None


def get_registry() -> MCPRegistry:
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry
