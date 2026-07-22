from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agno.tools.function import Function

from .client import DifyClient
from .config import DifyWorkflowConfig, load_dify_config
from .tools import build_dify_function

if TYPE_CHECKING:
    from app.core.tools.confirm import ConfirmManager

logger = logging.getLogger(__name__)


class DifyClientPool:
    def __init__(self) -> None:
        self._entries: list[tuple[DifyWorkflowConfig, DifyClient, list[dict]]] = []

    async def initialize(self, config_path: str | None) -> None:
        configs = load_dify_config(config_path)
        for cfg in configs:
            if not cfg.enabled:
                logger.info("Dify workflow [%s] disabled, skip", cfg.name)
                continue
            if not cfg.api_key or not cfg.api_base_url:
                logger.warning(
                    "Dify workflow [%s] missing api_key or api_base_url, skip",
                    cfg.name,
                )
                continue
            try:
                client = DifyClient(cfg)
                params = await client.get_parameters()
                self._entries.append((cfg, client, params))
                logger.info(
                    "Dify workflow [%s] initialized: %d form fields",
                    cfg.name, len(params),
                )
            except Exception as e:
                logger.warning("Dify workflow [%s] init failed: %s", cfg.name, e)

    def build_tools(
        self,
        user: str = "zagent-wf",
        confirm_mgr: ConfirmManager | None = None,
    ) -> list[Function]:
        tools: list[Function] = []
        for cfg, client, params in self._entries:
            fn = build_dify_function(
                cfg, client, params, user=user, confirm_mgr=confirm_mgr,
            )
            tools.append(fn)
            logger.info("Dify tool registered: %s (user=%s)", fn.name, user)
        return tools

    async def close(self) -> None:
        for _cfg, client, _params in self._entries:
            try:
                await client.close()
            except Exception as e:
                logger.warning("Dify client [%s] close error: %s", _cfg.name, e)
        self._entries.clear()
