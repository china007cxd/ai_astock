# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from app.cache import CacheStore


@pytest.mark.asyncio
async def test_cache_remembers_and_reports_hits(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    calls = 0

    async def loader() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"value": 42}

    first = await store.remember("key", 60, loader)
    second = await store.remember("key", 60, loader)
    assert first == ({"value": 42}, False, False)
    assert second == ({"value": 42}, True, False)
    assert calls == 1
