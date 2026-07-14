from __future__ import annotations

import logging
from typing import Any, Callable

from agno.tools.function import Function
from agno.tools.mcp import MCPTools

from ..tools.confirm import ConfirmManager
from .config import ServerConfig

logger = logging.getLogger(__name__)

PATH_ARGS = {"path", "paths", "file_path", "source", "destination", "src", "dst"}


class MCPWrapper:
    def __init__(
        self,
        confirm_mgr: ConfirmManager,
        workdir_ctx: Any = None,
        server_cfg: ServerConfig | None = None,
    ) -> None:
        self._confirm = confirm_mgr
        self._ctx = workdir_ctx
        self._cfg = server_cfg

    async def wrap_functions(self, mcp: MCPTools) -> list[Function]:
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
        cfg = self._cfg

        async def wrapped(**kwargs: Any) -> object:
            if cfg is not None:
                result = await self._check_requires(name, kwargs)
                if result is not None:
                    return result
            return await original(**kwargs)
        return wrapped

    async def _check_requires(self, name: str, kwargs: dict) -> str | None:
        cfg = self._cfg
        if cfg is None:
            return None

        if cfg.path_gate:
            result = await self._check_path_gate(name, kwargs)
            if result is not None:
                return result

        return None

    async def _check_path_gate(self, name: str, kwargs: dict) -> str | None:
        path = _extract_path(kwargs)
        wd = self._ctx.workdir if self._ctx else ""
        if not path:
            return None
        if wd and path.startswith(wd):
            return None
        reason = "无工作目录" if not wd else f"不在工作目录 [{wd}] 内"
        logger.info("gate triggered: tool=%s path=%s %s", name, path, reason)
        cid, future = self._confirm.request({
            "type": "require_confirm",
            "title": "路径门禁",
            "tool": name,
            "path": path,
            "workdir": wd,
            "question": f"操作路径 [{path}] {reason}，是否放行？",
        })
        approved = await future
        self._confirm.cleanup(cid)
        if not approved:
            return f"❌ 操作已拒绝：{reason}"
        return None

def _extract_path(kwargs: dict) -> str | None:
    for key in PATH_ARGS:
        val = kwargs.get(key)
        if isinstance(val, str) and val.startswith("/"):
            return val
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.startswith("/"):
                    return item
    return None



