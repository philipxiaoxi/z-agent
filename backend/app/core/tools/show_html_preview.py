from __future__ import annotations

from typing import Callable

from agno.tools.function import Function


def make_show_html_preview_tool(send_to_frontend: Callable[[dict], None] | None = None) -> Function:
    """创建 show_html_preview 工具——在对话中渲染 HTML 交互页面"""

    async def show_html_preview(title: str, html: str, height: int = 400) -> str:
        data = {
            "title": title,
            "html": html,
            "height": height,
        }

        if send_to_frontend:
            send_to_frontend({
                "type": "html_preview",
                "data": data,
            })

        return f"前端已展示 HTML 预览卡片：{title}，高度 {height}px。"

    return Function(
        name="show_html_preview",
        description="在对话中渲染一个 HTML 交互页面（含 JS/CSS），以可展开卡片形式展示。适用于数据可视化、交互式演示、临时小程序等场景。传入完整的 HTML 文档字符串，将被渲染在沙盒 iframe 中。title 为卡片标题，html 为完整 HTML（可含 <style>、<script>），height 为预览高度（默认 400）。不要用于敏感操作。",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "预览卡片标题，简短描述内容",
                },
                "html": {
                    "type": "string",
                    "description": "完整的 HTML 内容（含 <style> 和 <script> 标签），将被渲染在沙盒 iframe 中。可以是数据可视化、交互式演示等。",
                },
                "height": {
                    "type": "integer",
                    "description": "预览区域高度（像素），默认 400",
                    "default": 400,
                },
            },
            "required": ["title", "html"],
        },
        entrypoint=show_html_preview,
    )
