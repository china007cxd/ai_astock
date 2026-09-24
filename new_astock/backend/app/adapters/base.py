# -*- coding: utf-8 -*-
"""带缓存、限流与陈旧回退的 HTTP 数据客户端。"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from typing import Any

import httpx

from ..cache import cache
from ..config import settings


class SourceError(RuntimeError):
    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message


class HTTPDataClient:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=12),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
            },
        )
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._health: dict[str, dict[str, Any]] = {}

    async def close(self) -> None:
        await self.client.aclose()

    async def _throttle(self, source: str, calls: int = 8, window: float = 1.0) -> None:
        queue = self._calls[source]
        now = time.monotonic()
        while queue and queue[0] < now - window:
            queue.popleft()
        if len(queue) >= calls:
            await asyncio.sleep(max(0, window - (now - queue[0])))
        queue.append(time.monotonic())

    def health(self) -> list[dict[str, Any]]:
        return [
            {"source": name, **status}
            for name, status in sorted(self._health.items())
        ]

    def _mark(self, source: str, ok: bool, error: str = "") -> None:
        self._health[source] = {
            "ok": ok,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "error": error,
        }

    async def get_json(
        self,
        source: str,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        ttl: int = 30,
        headers: dict[str, str] | None = None,
        encoding: str | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        key = cache.key_for("GET", url, params or {})

        async def loader() -> Any:
            await self._throttle(source)
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    response = await self.client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    if encoding:
                        response.encoding = encoding
                    text = response.text.strip()
                    if text.startswith(("callback(", "jQuery")):
                        text = text[text.find("(") + 1 : text.rfind(")")]
                    if text.startswith("var ") and "=" in text:
                        text = text.split("=", 1)[1].rstrip(";\n ")
                    value = json.loads(text)
                    self._mark(source, True)
                    return value
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt == 0:
                        await asyncio.sleep(0.25)
            self._mark(source, False, str(last_error))
            raise SourceError(source, str(last_error))

        value, cached, stale = await cache.remember(key, ttl, loader)
        return value, {"source": source, "cached": cached, "stale": stale}

    async def post_json(
        self,
        source: str,
        url: str,
        payload: dict[str, Any],
        *,
        ttl: int = 60,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        key = cache.key_for("POST", url, payload)

        async def loader() -> Any:
            await self._throttle(source, calls=3)
            try:
                response = await self.client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                value = response.json()
                self._mark(source, True)
                return value
            except (httpx.HTTPError, ValueError) as exc:
                self._mark(source, False, str(exc))
                raise SourceError(source, str(exc)) from exc

        value, cached, stale = await cache.remember(key, ttl, loader)
        return value, {"source": source, "cached": cached, "stale": stale}

    async def get_text(
        self,
        source: str,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        ttl: int = 15,
        encoding: str = "utf-8",
    ) -> tuple[str, dict[str, Any]]:
        key = cache.key_for("TEXT", url, params or {})

        async def loader() -> str:
            await self._throttle(source)
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                response.encoding = encoding
                self._mark(source, True)
                return response.text
            except httpx.HTTPError as exc:
                self._mark(source, False, str(exc))
                raise SourceError(source, str(exc)) from exc

        value, cached, stale = await cache.remember(key, ttl, loader)
        return str(value), {"source": source, "cached": cached, "stale": stale}


http_client = HTTPDataClient()
