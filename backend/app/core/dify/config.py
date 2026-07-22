from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")
_dotenv_loaded = False


def _ensure_dotenv() -> None:
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv()
        _dotenv_loaded = True


def _resolve_env(value: Any) -> Any:
    _ensure_dotenv()

    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            env_name = match.group(1)
            resolved = os.environ.get(env_name)
            if resolved is None:
                logger.warning("Dify config env var not set: ${%s}", env_name)
                return ""
            return resolved
        return _ENV_VAR_RE.sub(_replace, value)
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


@dataclass
class DifyWorkflowConfig:
    name: str
    description: str
    api_base_url: str
    api_key: str
    enabled: bool = True
    max_execution_time: int = 60


def load_dify_config(config_path: str | None) -> list[DifyWorkflowConfig]:
    if not config_path or not Path(config_path).is_file():
        return []

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    if not raw or "workflows" not in raw:
        return []

    configs: list[DifyWorkflowConfig] = []
    for name, data in raw["workflows"].items():
        resolved = _resolve_env(data)
        cfg = DifyWorkflowConfig(
            name=resolved.get("name", name),
            description=resolved.get("description", ""),
            api_base_url=resolved.get("api_base_url", "").rstrip("/"),
            api_key=resolved.get("api_key", ""),
            enabled=resolved.get("enabled", True),
            max_execution_time=int(resolved.get("max_execution_time", 60)),
        )
        if cfg.enabled and not cfg.api_key:
            logger.warning(
                "Dify workflow [%s] enabled but api_key is empty",
                cfg.name,
            )
        if cfg.enabled and not cfg.api_base_url:
            logger.warning(
                "Dify workflow [%s] enabled but api_base_url is empty",
                cfg.name,
            )
        configs.append(cfg)

    return configs
