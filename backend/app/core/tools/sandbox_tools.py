"""
Sandbox 容器操作工具。通过 httpx 直接调用 AIO Sandbox REST API。
"""

from __future__ import annotations

import logging

import httpx
from agno.tools.function import Function

logger = logging.getLogger(__name__)


def _api_key() -> str:
    from app.core.config import settings
    return settings.SANDBOX_API_KEY or ""


def _headers() -> dict[str, str]:
    key = _api_key()
    return {"X-AIO-API-Key": key} if key else {}


def make_sandbox_tools() -> list[Function]:
    tools: list[Function] = []

    async def sandbox_exec(port: int, command: str, timeout: float = 30) -> str:
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers=_headers()) as c:
                r = c.post("v1/shell/exec", json={"command": command, "timeout": timeout})
                data = r.json()
            out = (data.get("data") or {}).get("output") or ""
            return f"```\n{out}\n```"
        except Exception as e:
            return f"❌ 执行失败: {e}"

    tools.append(Function(
        name="sandbox_exec",
        description="在容器内执行 shell 命令。如 ls/find/grep/sed/echo 等均可通过此工具完成。port 为 create_container 返回的端口。",
        parameters={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "容器映射的宿主机端口"},
                "command": {"type": "string", "description": "shell 命令"},
                "timeout": {"type": "number", "description": "超时秒数，默认 30"},
            },
            "required": ["port", "command"],
        },
        entrypoint=sandbox_exec,
    ))

    async def sandbox_read_file(port: int, path: str) -> str:
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers=_headers()) as c:
                r = c.post("v1/file/read", json={"file": path})
                data = r.json()
            content = (data.get("data") or {}).get("content")
            return content if content is not None else "❌ 文件为空"
        except Exception as e:
            return f"❌ 读取失败: {e}"

    tools.append(Function(
        name="sandbox_read_file",
        description="读取容器内文本文件内容。比 sandbox_exec cat 更简洁，结果无 shell 包装。",
        parameters={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "容器映射的宿主机端口"},
                "path": {"type": "string", "description": "容器内文件路径"},
            },
            "required": ["port", "path"],
        },
        entrypoint=sandbox_read_file,
    ))

    async def sandbox_write_file(port: int, path: str, content: str) -> str:
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers=_headers()) as c:
                c.post("v1/file/write", json={"file": path, "content": content})
            return f"✅ 文件已写入 [{path}]"
        except Exception as e:
            return f"❌ 写入失败: {e}"

    tools.append(Function(
        name="sandbox_write_file",
        description="写入内容到容器内文件。支持多行文本，比 sandbox_exec echo 更适合写代码/配置文件。",
        parameters={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "容器映射的宿主机端口"},
                "path": {"type": "string", "description": "容器内文件路径"},
                "content": {"type": "string", "description": "文件内容（支持多行）"},
            },
            "required": ["port", "path", "content"],
        },
        entrypoint=sandbox_write_file,
    ))

    async def sandbox_get_context(port: int) -> str:
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", headers=_headers()) as c:
                r = c.get("v1/sandbox")
                data = r.json()
            return (
                f"Home: {data.get('home_dir', 'N/A')}\n"
                f"Workspace: {data.get('workspace') or 'N/A'}\n"
                f"Version: {data.get('version', 'N/A')}"
            )
        except Exception as e:
            return f"❌ 获取失败: {e}"

    tools.append(Function(
        name="sandbox_get_context",
        description="获取容器基本信息（home_dir、工作空间路径、版本号等）。",
        parameters={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "容器映射的宿主机端口"},
            },
            "required": ["port"],
        },
        entrypoint=sandbox_get_context,
    ))

    return tools
