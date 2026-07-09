from __future__ import annotations

import json
from typing import Callable

from agno.tools.function import Function


def make_show_directory_tool(send_to_frontend: Callable[[dict], None] | None = None) -> Function:
    """创建 show_directory 工具——将文件列表以可视化文件浏览器呈现给用户"""

    async def show_directory(path: str, items: list) -> str:
        if not isinstance(items, list):
            return "错误：items 参数必须为数组"

        normalized = []
        folder_count = 0
        file_count = 0
        for item in items:
            if not isinstance(item, dict) or "name" not in item:
                continue
            name = str(item.get("name", ""))
            raw_type = item.get("type", "")
            is_dir = raw_type in ("folder", "directory", "dir")
            if is_dir:
                folder_count += 1
            else:
                file_count += 1

            normalized.append({
                "name": name,
                "type": "folder" if is_dir else "file",
                "size": int(item.get("size", 0) or 0),
                "modified_at": str(item.get("modified_at", "")),
            })

        summary_parts = []
        if folder_count:
            summary_parts.append(f"{folder_count} 个文件夹")
        if file_count:
            summary_parts.append(f"{file_count} 个文件")
        total_str = "，".join(summary_parts) if summary_parts else "空目录"

        file_list_data = {
            "current_path": path,
            "items": normalized,
            "total": len(normalized),
        }

        if send_to_frontend:
            send_to_frontend({
                "type": "file_list",
                "data": file_list_data,
            })

        return f"📁 {path} — {total_str}"

    return Function(
        name="show_directory",
        description="将文件列表以可视化文件浏览器展示给用户。先调用 zspace-cli_list_files 获取文件列表，再把获取到的数据传给此工具进行展示。不要自己编造文件列表。",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径，如 /sata12/my/data，显示在文件浏览器顶部",
                },
                "items": {
                    "type": "array",
                    "description": "文件/文件夹列表，每项需包含 name、type（'file' 或 'folder'）、size（字节）、modified_at（修改时间戳）。从 zspace-cli_list_files 的返回结果中提取，不要编造。",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "文件名"},
                            "type": {"type": "string", "description": "类型：'file' 或 'folder'", "enum": ["file", "folder"]},
                            "size": {"type": "number", "description": "文件大小（字节）"},
                            "modified_at": {"type": "string", "description": "修改时间戳"},
                        },
                        "required": ["name", "type"],
                    },
                },
            },
            "required": ["path", "items"],
        },
        entrypoint=show_directory,
    )
