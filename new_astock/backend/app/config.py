# -*- coding: utf-8 -*-
"""应用配置与数据目录。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8765"))
    debug: bool = _as_bool(os.getenv("APP_DEBUG"))
    retention_days: int = int(os.getenv("DATA_RETENTION_DAYS", "30"))
    market_refresh_seconds: int = int(os.getenv("MARKET_REFRESH_SECONDS", "10"))
    list_refresh_seconds: int = int(os.getenv("LIST_REFRESH_SECONDS", "30"))
    http_timeout_seconds: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
    longhuvip_token: str = os.getenv("LONGHUVIP_TOKEN", "")
    longhuvip_user_id: str = os.getenv("LONGHUVIP_USER_ID", "")

    @property
    def data_dir(self) -> Path:
        return ROOT_DIR / "data"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'new_astock.db').as_posix()}"

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.cache_dir, self.export_dir, self.data_dir / "logs"):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
