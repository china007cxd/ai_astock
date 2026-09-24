# -*- coding: utf-8 -*-
"""支持陈旧回退的内存与磁盘 JSON 缓存。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .config import settings


@dataclass(slots=True)
class CacheEntry:
    value: Any
    expires_at: float
    saved_at: float


class CacheStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def key_for(*parts: Any) -> str:
        raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str, allow_stale: bool = False) -> tuple[Any, bool] | None:
        now = time.time()
        entry = self._memory.get(key)
        if entry and (allow_stale or entry.expires_at > now):
            return entry.value, entry.expires_at <= now
        path = self._path(key)
        if not path.exists():
            return None
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            entry = CacheEntry(body["value"], body["expires_at"], body["saved_at"])
            self._memory[key] = entry
            if allow_stale or entry.expires_at > now:
                return entry.value, entry.expires_at <= now
        except (OSError, ValueError, KeyError):
            return None
        return None

    def set(self, key: str, value: Any, ttl: int) -> None:
        now = time.time()
        entry = CacheEntry(value, now + ttl, now)
        self._memory[key] = entry
        payload = {"value": value, "expires_at": entry.expires_at, "saved_at": now}
        tmp = self._path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(self._path(key))

    async def remember(
        self,
        key: str,
        ttl: int,
        loader: Callable[[], Awaitable[Any]],
    ) -> tuple[Any, bool, bool]:
        hit = self.get(key)
        if hit:
            value, stale = hit
            return value, True, stale
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            hit = self.get(key)
            if hit:
                value, stale = hit
                return value, True, stale
            try:
                value = await loader()
                self.set(key, value, ttl)
                return value, False, False
            except Exception:
                stale_hit = self.get(key, allow_stale=True)
                if stale_hit:
                    value, _ = stale_hit
                    return value, True, True
                raise

    def clear(self) -> int:
        count = 0
        self._memory.clear()
        for path in self.directory.glob("*.json"):
            try:
                path.unlink()
                count += 1
            except OSError:
                continue
        return count


cache = CacheStore(settings.cache_dir)
