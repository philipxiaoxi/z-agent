from __future__ import annotations

import logging
from typing import Any, Callable

from mcp.client.stdio import StdioServerParameters

from agno.tools.function import Function
from agno.tools.mcp import MCPTools

from .confirm import ConfirmManager

logger = logging.getLogger(__name__)

_zcli_params = StdioServerParameters(command="zcli", args=["mcp"])
_zcli_mcp: MCPTools | None = None
PATH_ARGS = {"path", "file_path", "source", "destination", "src", "dst"}


async def get_zcli_mcp() -> MCPTools:
    global _zcli_mcp
    if _zcli_mcp is None:
        _zcli_mcp = MCPTools(server_params=_zcli_params)
        await _zcli_mcp.connect()
        logger.info("zcli MCP connected, tools: %s", list(_zcli_mcp.functions.keys()))
    return _zcli_mcp


class ZcliMCPWrapper:
    """包装 zcli MCP 工具函数，加入工作目录路径门禁"""

    def __init__(self, confirm_mgr: ConfirmManager, workdir_ctx: Any = None) -> None:
        self._confirm = confirm_mgr
        self._ctx = workdir_ctx

    async def wrap_functions(self) -> list[Function]:
        mcp = await get_zcli_mcp()
        wrapped: list[Function] = []
        for name, func in mcp.functions.items():
            f = Function(
                name=name,
                description=func.description,
                parameters=func.parameters,
                entrypoint=self._build_entrypoint(name, func.entrypoint),
                skip_entrypoint_processing=True,
            )
            wrapped.append(f)
        return wrapped

    def _build_entrypoint(self, name: str, original: Callable) -> Callable:
        async def wrapped(**kwargs: Any) -> object:
            path = _extract_path(kwargs)
            wd = self._ctx.workdir if self._ctx else ""
            logger.info("gate check: tool=%s path=%s workdir=%s", name, path, wd)
            if path and (not wd or not path.startswith(wd)):
                reason = "无工作目录" if not wd else f"不在工作目录 [{wd}] 内"
                logger.info("gate triggered: %s %s", path, reason)
                cid, future = self._confirm.request({
                    "type": "require_confirm",
                    "confirm_type": "path_gate",
                    "tool": name,
                    "path": path,
                    "workdir": wd,
                    "question": f"操作路径 [{path}] {reason}，是否放行？",
                })
                approved = await future
                self._confirm.cleanup(cid)
                if not approved:
                    return f"❌ 操作已拒绝：{reason}"
            result = await original(**kwargs)
            return result
        return wrapped


def _extract_path(kwargs: dict) -> str | None:
    for key in PATH_ARGS:
        val = kwargs.get(key)
        if isinstance(val, str) and val.startswith("/"):
            return val
    return None
