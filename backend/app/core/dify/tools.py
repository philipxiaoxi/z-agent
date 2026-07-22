from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agno.tools.function import Function

from .client import DifyClient
from .config import DifyWorkflowConfig
from .file_resolver import local_file_for_upload

if TYPE_CHECKING:
    from app.core.tools.confirm import ConfirmManager

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "text-input": "string",
    "paragraph": "string",
    "select": "string",
    "number": "number",
    "file": "string",
    "file-list": "array",
}

_IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff", ".tif", ".ico",
}
_AUDIO_EXTS = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".wma", ".amr",
}
_VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v",
}

_FILE_PATH_HINT = "NAS 路径（如 /pool/my/a.jpg）或本机路径；工具会自动拉取并上传"


def _build_schema(user_input_form: list[dict]) -> dict:
    properties: dict[str, dict] = {}
    required: list[str] = []

    for item in user_input_form:
        for field_type, field_def in item.items():
            var_name = field_def.get("variable", "")
            if not var_name:
                continue
            label = field_def.get("label", "") or ""
            prop: dict[str, Any] = {
                "type": _TYPE_MAP.get(field_type, "string"),
                "description": label,
            }
            if field_type in ("file", "file-list"):
                prop["description"] = f"{label}（{_FILE_PATH_HINT}）" if label else _FILE_PATH_HINT
            if field_type == "select":
                options = field_def.get("options")
                if options:
                    prop["enum"] = options
            if field_type == "file-list":
                prop["items"] = {"type": "string"}
            properties[var_name] = prop
            if field_def.get("required"):
                required.append(var_name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _extract_file_fields(user_input_form: list[dict]) -> set[str]:
    file_fields: set[str] = set()
    for item in user_input_form:
        for field_type, field_def in item.items():
            if field_type in ("file", "file-list"):
                var_name = field_def.get("variable", "")
                if var_name:
                    file_fields.add(var_name)
    return file_fields


def _infer_dify_file_type(file_path: str) -> str:
    """根据扩展名推断 Dify 文件 type（document/image/audio/video）。"""
    ext = Path(file_path).suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _VIDEO_EXTS:
        return "video"
    return "document"


def _collect_file_paths(file_fields: set[str], kwargs: dict) -> list[str]:
    """从工具参数中收集所有待上传文件路径（保持顺序、去重）。"""
    paths: list[str] = []
    seen: set[str] = set()
    for key in file_fields:
        value = kwargs.get(key)
        candidates: list[str] = []
        if isinstance(value, str) and value.strip():
            candidates.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    candidates.append(item)
        for path in candidates:
            if path not in seen:
                seen.add(path)
                paths.append(path)
    return paths


async def _confirm_file_uploads(
    confirm_mgr: ConfirmManager | None,
    tool_name: str,
    paths: list[str],
) -> str | None:
    """对本次调用中的全部文件上传做一次确认。

    Returns:
        None 表示通过；字符串表示拒绝/失败原因（直接作为 tool 返回值）。
    """
    if not paths:
        return None
    if confirm_mgr is None:
        logger.warning(
            "Dify tool %s has file uploads but no ConfirmManager; skip confirm",
            tool_name,
        )
        return None

    if len(paths) == 1:
        path_text = paths[0]
        question = (
            f"Dify 工作流 [{tool_name}] 将上传文件到外部服务：\n"
            f"{path_text}\n是否放行？"
        )
    else:
        path_text = "\n".join(f"- {path}" for path in paths)
        question = (
            f"Dify 工作流 [{tool_name}] 将上传 {len(paths)} 个文件到外部服务：\n"
            f"{path_text}\n是否放行？"
        )

    logger.info("Dify file upload confirm: tool=%s paths=%s", tool_name, paths)
    confirm_id, future = confirm_mgr.request({
        "type": "require_confirm",
        "title": "Dify 文件上传",
        "tool": tool_name,
        "path": paths[0],
        "paths": paths,
        "question": question,
    })
    approved = await future
    confirm_mgr.cleanup(confirm_id)
    if not approved:
        return f"❌ 用户拒绝了 Dify 文件上传：{', '.join(paths)}"
    return None


async def _resolve_file_inputs(
    client: DifyClient,
    file_fields: set[str],
    kwargs: dict,
    user: str,
) -> dict:
    inputs = dict(kwargs)
    for key, value in list(inputs.items()):
        if key not in file_fields:
            continue
        if isinstance(value, str):
            inputs[key] = await _build_file_input(client, value, user)
        elif isinstance(value, list):
            resolved: list[dict | str] = []
            for item in value:
                if isinstance(item, str):
                    resolved.append(await _build_file_input(client, item, user))
                else:
                    resolved.append(item)
            inputs[key] = resolved
    return inputs


async def _build_file_input(
    client: DifyClient,
    value: str,
    user: str,
) -> dict:
    # 本机存在则直传；否则 zcli download 从 NAS 拉取到临时目录再上传
    async with local_file_for_upload(value) as local_path:
        upload_id = await client.upload_file(str(local_path), user)
        return {
            "type": _infer_dify_file_type(value),
            "transfer_method": "local_file",
            "upload_file_id": upload_id,
        }


def build_dify_function(
    config: DifyWorkflowConfig,
    client: DifyClient,
    user_input_form: list[dict],
    user: str = "zagent-wf",
    confirm_mgr: ConfirmManager | None = None,
) -> Function:
    schema = _build_schema(user_input_form)
    file_fields = _extract_file_fields(user_input_form)
    tool_name = f"dify_{config.name}"

    # 补充工具说明：文件参数支持 NAS 路径
    description = config.description
    if file_fields and "NAS" not in description:
        description = f"{description}（文件参数支持 NAS/本机路径，自动拉取上传；上传前需用户确认）"

    async def entrypoint(**kwargs: str) -> str:
        file_paths = _collect_file_paths(file_fields, kwargs)
        denied = await _confirm_file_uploads(confirm_mgr, tool_name, file_paths)
        if denied is not None:
            return denied

        inputs = await _resolve_file_inputs(client, file_fields, kwargs, user)
        return await client.run_workflow(inputs, user, "streaming")

    return Function(
        name=tool_name,
        description=description,
        parameters=schema,
        entrypoint=entrypoint,
        skip_entrypoint_processing=True,
    )
