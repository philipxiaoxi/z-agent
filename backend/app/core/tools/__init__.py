from __future__ import annotations

import logging
from typing import Any, Callable

from agno.tools.function import Function

from app.core.mcp import load_mcp_config, get_registry, MCPWrapper
from app.core.config import settings
from .confirm import ConfirmManager
from .set_workdir import make_set_workdir_tool
from .docker_tools import make_docker_tools
from .sandbox_tools import make_sandbox_tools


async def get_tools(
    confirm_mgr: ConfirmManager,
    workdir_ctx: Any | None = None,
    on_workdir_changed: Callable[[str], None] | None = None,
    session_id: str = "",
    dify_pool: Any | None = None,
) -> list[Function]:
    logger = logging.getLogger(__name__)
    all_tools: list[Function] = []

    configs = load_mcp_config(settings.MCP_SERVERS_CONFIG or None)
    registry = get_registry()
    for cfg in configs:
        if not cfg.enabled:
            continue
        try:
            mcp = await registry.get(cfg)
        except Exception as e:
            logger.warning("MCP [%s] skip: %s", cfg.name, e)
            continue
        wrapper = MCPWrapper(confirm_mgr, workdir_ctx, server_cfg=cfg)
        tools = await wrapper.wrap_functions(mcp)
        all_tools.extend(tools)
        logger.info("MCP [%s]: %d tools loaded", cfg.name, len(tools))

    local_tools: list[Function] = []

    async def _on_set_workdir(path: str) -> None:
        if on_workdir_changed:
            await on_workdir_changed(path)

    local_tools.append(make_set_workdir_tool(confirm_mgr, on_workdir_changed=_on_set_workdir))
    local_tools.extend(make_docker_tools(confirm_mgr))
    local_tools.extend(make_sandbox_tools())

    dify_tools: list[Function] = []
    if dify_pool is not None:
        dify_user = f"zagent-{session_id}" if session_id else "zagent-wf"
        dify_tools = dify_pool.build_tools(user=dify_user, confirm_mgr=confirm_mgr)
        all_tools.extend(dify_tools)
        logger.info("Dify: %d workflow tools loaded (user=%s)", len(dify_tools), dify_user)

    mcp_count = len(all_tools) - len(dify_tools)
    total = mcp_count + len(local_tools) + len(dify_tools)
    logger.info(
        "get_tools: %d mcp + %d local + %d dify = %d tools",
        mcp_count,
        len(local_tools),
        len(dify_tools),
        total,
    )
    return all_tools + local_tools
