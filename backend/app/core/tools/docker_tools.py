"""
Docker 容器生命周期工具（创建/停止/列出/拉取镜像）。
这些操作影响宿主机，需用户确认。
"""

from __future__ import annotations

import logging
from agno.tools.function import Function

from .confirm import ConfirmManager

logger = logging.getLogger(__name__)


def make_docker_tools(confirm_mgr: ConfirmManager) -> list[Function]:
    tools: list[Function] = []

    def _client():
        import docker
        return docker.from_env()

    def _docker_ok() -> str | None:
        try:
            _client().ping()
            return None
        except Exception as e:
            return f"❌ Docker daemon 不可用: {e}"

    async def create_container(host_port: int | None = None) -> str:
        err = _docker_ok()
        if err:
            return err

        cid, future = confirm_mgr.request({
            "type": "require_confirm",
            "title": "创建容器",
            "tool": "create_container",
            "image": "ghcr.io/agent-infra/sandbox",
            "question": "极同学想创建 AIO Sandbox 容器，是否放行？",
        })
        approved = await future
        confirm_mgr.cleanup(cid)
        if not approved:
            return "❌ 用户拒绝了容器创建"

        client = _client()
        image = "ghcr.io/agent-infra/sandbox:latest"
        try:
            client.images.get(image)
        except Exception as _img_err:
            import docker.errors
            if isinstance(_img_err, docker.errors.ImageNotFound):
                return f"❌ 本地没有镜像 [{image}]，请先调 pull_image 拉取"
            return f"❌ 镜像检查失败: {_img_err}"

        if host_port is None:
            try:
                host_port = _pick_free_port()
            except RuntimeError as e:
                return f"❌ {e}"

        api_key = _get_api_key()

        try:
            container = client.containers.run(
                image=image,
                detach=True,
                ports={"8080/tcp": ("127.0.0.1", host_port)},
                security_opt=["seccomp=unconfined"],
                environment={"SANDBOX_API_KEY": api_key} if api_key else None,
                remove=True,
            )
            logger.info("sandbox created: id=%s port=%s", container.short_id[:12], host_port)

            lines = [
                f"✅ AIO Sandbox 容器已创建",
                f"  镜像: {image}",
                f"  ID: {container.short_id[:12]}",
                f"  Port: {host_port}",
            ]
            if api_key:
                lines.append(f"  Web: http://127.0.0.1:{host_port}/?api_key={api_key}")
            else:
                lines.append(f"  Web: http://127.0.0.1:{host_port}/")
            lines.append("")
            lines.append(f"已将 port={host_port} 传入 sandbox 工具操作容器。")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 创建失败: {e}"

    tools.append(Function(
        name="create_container",
        description="创建标准 AIO Sandbox 容器（ghcr.io/agent-infra/sandbox）。自动配置 seccomp 和 API Key，是创建沙箱的推荐方式。",
        parameters={
            "type": "object",
            "properties": {
                "host_port": {
                    "type": "integer",
                    "description": "宿主机端口，默认自动分配 18080-18090",
                },
            },
        },
        entrypoint=create_container,
    ))

    async def pull_image(image: str) -> str:
        err = _docker_ok()
        if err:
            return err

        cid, future = confirm_mgr.request({
            "type": "require_confirm", "title": "拉取镜像",
            "tool": "pull_image", "image": image,
            "question": f"极同学想拉取 Docker 镜像 [{image}]，是否放行？",
        })
        approved = await future
        confirm_mgr.cleanup(cid)
        if not approved:
            return "❌ 用户拒绝了镜像拉取"

        try:
            _client().images.pull(image)
            return f"✅ 镜像已拉取: {image}"
        except Exception as e:
            return f"❌ 拉取失败: {e}"

    tools.append(Function(
        name="pull_image",
        description="拉取 Docker 镜像到本地。本地无镜像时先调此工具。",
        parameters={
            "type": "object",
            "properties": {
                "image": {"type": "string", "description": "镜像名称/标签"},
            },
            "required": ["image"],
        },
        entrypoint=pull_image,
    ))

    async def stop_container(container_id: str) -> str:
        err = _docker_ok()
        if err:
            return err

        cid, future = confirm_mgr.request({
            "type": "require_confirm", "title": "停止容器",
            "tool": "stop_container", "container_id": container_id,
            "question": f"极同学想停止并删除容器 [{container_id[:12]}]，是否放行？",
        })
        approved = await future
        confirm_mgr.cleanup(cid)
        if not approved:
            return "❌ 用户拒绝了容器停止"

        try:
            _client().containers.get(container_id).stop(timeout=5)
            return f"✅ 容器已停止: {container_id[:12]}"
        except Exception as e:
            import docker.errors
            if isinstance(e, docker.errors.NotFound):
                return f"❌ 容器不存在: {container_id[:12]}"
            return f"❌ 停止失败: {e}"

    tools.append(Function(
        name="stop_container",
        description="停止并删除 Sandbox 容器。用完容器后调此工具释放资源。",
        parameters={
            "type": "object",
            "properties": {
                "container_id": {"type": "string", "description": "容器 ID"},
            },
            "required": ["container_id"],
        },
        entrypoint=stop_container,
    ))

    async def list_containers(all_containers: bool = False) -> str:
        err = _docker_ok()
        if err:
            return err
        try:
            containers = _client().containers.list(all=all_containers)
            if not containers:
                return "(无容器)"
            lines = ["容器列表:"]
            for c in containers:
                tags = c.image.tags[0] if c.image.tags else "<untagged>"
                lines.append(f"  {c.short_id[:12]}  {tags}  {c.status}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 查询失败: {e}"

    tools.append(Function(
        name="list_containers",
        description="列出 Sandbox 容器。默认只列出运行中的，设置 all_containers=true 包含已停止的。",
        parameters={
            "type": "object",
            "properties": {
                "all_containers": {"type": "boolean", "description": "是否包括已停止的容器，默认 false"},
            },
        },
        entrypoint=list_containers,
    ))

    async def list_images() -> str:
        err = _docker_ok()
        if err:
            return err
        try:
            images = _client().images.list()
            if not images:
                return "(无镜像)"
            lines = ["本地镜像列表:"]
            for img in images:
                tags = ", ".join(img.tags) if img.tags else "<untagged>"
                size = _fmt_size(img.attrs.get("Size", 0))
                lines.append(f"  {tags}  ({size})")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 查询失败: {e}"

    tools.append(Function(
        name="list_images",
        description="列出本地所有 Docker 镜像。创建容器前可先查一下是否已有镜像。",
        parameters={
            "type": "object",
            "properties": {},
        },
        entrypoint=list_images,
    ))

    return tools


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _get_api_key() -> str:
    from app.core.config import settings
    return settings.SANDBOX_API_KEY or ""


def cleanup_leftover_containers() -> None:
    """Stop all containers created from SANDBOX_IMAGE (called on app shutdown)."""
    import docker

    from app.core.config import settings

    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        return
    for c in client.containers.list(all=True, filters={"ancestor": settings.SANDBOX_IMAGE}):
        try:
            c.stop(timeout=5)
            logger.info("leftover container cleaned: %s", c.short_id[:12])
        except Exception:
            pass


def _pick_free_port() -> int:
    import socket
    from app.core.config import settings

    range_str = settings.SANDBOX_HOST_PORT_RANGE or "18080-18090"
    parts = range_str.split("-", 1)
    try:
        lo, hi = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        lo, hi = 18080, 18090

    for port in range(lo, hi + 1):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        finally:
            s.close()
    raise RuntimeError(f"端口范围 {lo}-{hi} 全部被占用，无法分配可用端口")
