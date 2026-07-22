from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# NAS 大文件下载可能较慢，单独放宽超时
_ZCLI_DOWNLOAD_TIMEOUT_SEC = 180


class NasFileResolveError(RuntimeError):
    """无法将路径解析为可上传的本地文件。"""


async def _download_from_nas(nas_path: str, output_dir: str) -> Path:
    """调用 zcli download，将 NAS 文件落到 output_dir，返回本地路径。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "zcli",
            "download",
            nas_path,
            output_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise NasFileResolveError(
            "未找到 zcli 命令，无法从 NAS 下载文件"
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=_ZCLI_DOWNLOAD_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise NasFileResolveError(
            f"zcli download 超时（>{_ZCLI_DOWNLOAD_TIMEOUT_SEC}s）: {nas_path}"
        ) from exc

    if proc.returncode != 0:
        err_text = (stderr or b"").decode("utf-8", errors="replace").strip()
        out_text = (stdout or b"").decode("utf-8", errors="replace").strip()
        detail = err_text or out_text or f"exit={proc.returncode}"
        raise NasFileResolveError(f"zcli download 失败 [{nas_path}]: {detail}")

    dest = Path(output_dir) / Path(nas_path).name
    if not dest.is_file():
        raise NasFileResolveError(
            f"zcli download 完成但本地文件不存在: 期望 {dest}"
        )
    logger.info("NAS file downloaded: %s -> %s", nas_path, dest)
    return dest


async def resolve_to_local_file(file_path: str) -> tuple[Path, Path | None]:
    """将路径解析为本地可读文件。

    Returns:
        (local_path, temp_dir_to_cleanup)
        - 若本机已有该文件：temp_dir 为 None
        - 若从 NAS 下载：temp_dir 为临时目录，调用方负责清理
    """
    path = Path(file_path)
    if path.is_file():
        return path.resolve(), None

    # 非本机文件：按 NAS 路径走 zcli download
    temp_dir = Path(tempfile.mkdtemp(prefix="dify-nas-"))
    try:
        local = await _download_from_nas(file_path, str(temp_dir))
        return local, temp_dir
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@asynccontextmanager
async def local_file_for_upload(file_path: str) -> AsyncIterator[Path]:
    """解析路径为本地文件；退出时清理 NAS 下载产生的临时目录。"""
    local_path, temp_dir = await resolve_to_local_file(file_path)
    try:
        yield local_path
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)
