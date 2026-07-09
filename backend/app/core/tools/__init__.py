from __future__ import annotations

import logging
from typing import Any, Callable

from agno.tools.function import Function

from .confirm import ConfirmManager
from .zcli_mcp_wrapper import ZcliMCPWrapper
from .set_workdir import make_set_workdir_tool
from .show_directory import make_show_directory_tool


async def get_tools(
    confirm_mgr: ConfirmManager,
    workdir_ctx: Any | None = None,
    on_workdir_changed: Callable[[str], None] | None = None,
    send_to_frontend: Callable[[dict], None] | None = None,
) -> list[Function]:
    """获取所有可用工具列表（zcli MCP 工具 + 本地工具）"""
    wrapper = ZcliMCPWrapper(confirm_mgr, workdir_ctx)
    mcp_tools = await wrapper.wrap_functions()

    async def _on_set_workdir(path: str) -> None:
        if on_workdir_changed:
            await on_workdir_changed(path)

    local_tools = [
        make_set_workdir_tool(confirm_mgr, on_workdir_changed=_on_set_workdir),
        make_show_directory_tool(send_to_frontend),
    ]

    logger = logging.getLogger(__name__)
    logger.info("get_tools: %d mcp + %d local = %d tools",
                len(mcp_tools), len(local_tools), len(mcp_tools) + len(local_tools))

    return mcp_tools + local_tools
