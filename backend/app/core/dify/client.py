from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from .config import DifyWorkflowConfig
from .streamer import DifyEventStreamer

logger = logging.getLogger(__name__)


class DifyClient:
    def __init__(self, config: DifyWorkflowConfig) -> None:
        self.base = config.api_base_url
        self.timeout = config.max_execution_time
        # read 超时覆盖整段工作流等待；connect/write 用更短默认值
        self._session = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(self.timeout + 10),
                write=30.0,
                pool=10.0,
            ),
        )

    async def get_parameters(self) -> list[dict]:
        res = await self._session.get(f"{self.base}/parameters")
        res.raise_for_status()
        data = res.json()
        return data.get("user_input_form", [])

    async def run_workflow(
        self,
        inputs: dict,
        user: str,
        response_mode: str = "streaming",
    ) -> str:
        """执行工作流并以 streaming 模式消费 SSE，返回累积文本。"""
        body = {
            "inputs": inputs,
            "response_mode": response_mode,
            "user": user,
        }
        logger.info(
            "running workflow user=%s inputs=%s",
            user,
            {
                key: value if not isinstance(value, str) or len(value) < 80 else value[:80] + "..."
                for key, value in inputs.items()
            },
        )
        async with self._session.stream(
            "POST",
            f"{self.base}/workflows/run",
            json=body,
        ) as response:
            response.raise_for_status()
            return await DifyEventStreamer.accumulate(response)

    async def upload_file(self, file_path: str, user: str) -> str:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        content = await asyncio.to_thread(path.read_bytes)
        files = {"file": (path.name, content)}
        data = {"user": user}
        res = await self._session.post(
            f"{self.base}/files/upload",
            files=files,
            data=data,
        )
        res.raise_for_status()
        upload_id = res.json().get("id", "")
        logger.info("uploaded file %s -> upload_file_id=%s", file_path, upload_id)
        return upload_id

    async def stream_events(
        self,
        workflow_run_id: str,
        user: str,
        include_state_snapshot: bool = False,
    ) -> httpx.Response:
        params = {"user": user}
        if include_state_snapshot:
            params["include_state_snapshot"] = "true"
        res = await self._session.get(
            f"{self.base}/workflow/{workflow_run_id}/events",
            params=params,
        )
        return res

    async def close(self) -> None:
        await self._session.aclose()
