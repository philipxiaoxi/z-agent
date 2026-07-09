from __future__ import annotations

import asyncio
from typing import Callable, Coroutine

from agno.tools.function import Function

from .confirm import ConfirmManager


def make_set_workdir_tool(confirm_mgr: ConfirmManager,
                           on_workdir_changed: Callable[[str], Coroutine | None] | None = None) -> Function:
    """创建 set_workdir 工具函数"""

    async def set_workdir(path: str) -> str:
        cid, future = confirm_mgr.request({
            "type": "require_confirm",
            "confirm_type": "set_workdir",
            "tool": "set_workdir",
            "path": path,
            "question": f"AI 想将工作目录设为 [{path}]，是否同意？",
        })

        approved = await future
        confirm_mgr.cleanup(cid)

        if not approved:
            return "❌ 用户拒绝了工作目录设置"

        if on_workdir_changed:
            result = on_workdir_changed(path)
            if asyncio.iscoroutine(result):
                await result
        return f"✅ 工作目录已设置为 {path}，后续文件操作将限定在此目录范围内"

    return Function(
        name="set_workdir",
        description="用户明确同意设置某个路径为工作目录后调用此工具。调用后用户需二次确认。仅用于执行设置，不要用它来询问用户。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "工作目录路径，格式如 /pool_name/my/path",
                },
            },
            "required": ["path"],
        },
        entrypoint=set_workdir,
    )
