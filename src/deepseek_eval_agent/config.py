from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .schemas import AppConfig


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_app_config(project_root: Path) -> AppConfig:
    load_dotenv(project_root / ".env")
    raw = load_yaml_config(project_root / "config.yaml")

    env = {
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "timeout": int(os.getenv("LLM_TIMEOUT", "60")),
        "max_retries": int(os.getenv("LLM_MAX_RETRIES", "2")),
    }

    return AppConfig(
        env=env,
        report=raw.get("report", {}),
        analysis=raw.get("analysis", {}),
        llm=raw.get("llm", {}),
    )
