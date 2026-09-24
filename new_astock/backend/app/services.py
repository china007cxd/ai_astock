# -*- coding: utf-8 -*-
"""业务聚合、数据源降级与复盘口径。"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, Awaitable, Callable

from .adapters.base import SourceError, http_client
from .adapters.eastmoney import EastMoneyAdapter
from .adapters.market_sources import (
    ClsAdapter,
    LonghuVipAdapter,
    SupplementAdapter,
    TencentAdapter,
    ThsAdapter,
    XgbAdapter,
)
from .database import save_snapshot
from .indicators import apply_filters, enrich_klines, market_sentiment

Loader = Callable[[], Awaitable[tuple[Any, dict[str, Any]]]]


class MarketService:
    def __init__(self) -> None:
        self.eastmoney = EastMoneyAdapter(http_client)
        self.ths = ThsAdapter(http_client)
        self.xgb = XgbAdapter(http_client)
        self.cls = ClsAdapter(http_client)
        self.tencent = TencentAdapter(http_client)
        self.supplement = SupplementAdapter(http_client)
        self.longhu = LonghuVipAdapter(http_client)

    @staticmethod
    def result(data: Any, meta: dict[str, Any], fallback_reason: str | None = None) -> dict[str, Any]:
        return {
            "data": data,
            "meta": {
                "source": meta.get("source", "未知"),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "cached": bool(meta.get("cached")),
                "stale": bool(meta.get("stale")),
                "fallback_reason": fallback_reason,
            },
        }

    async def fallback(self, loaders: list[Loader]) -> tuple[Any, dict[str, Any], str | None]:
        errors: list[str] = []
        for loader in loaders:
            try:
                data, meta = await loader()
                if data not in (None, [], {}):
                    reason = "；".join(errors) if errors else None
                    return data, meta, reason
                errors.append(f"{meta.get('source', '数据源')}返回空数据")
            except SourceError as exc:
                errors.append(str(exc))
            except Exception as exc:  # 数据源错误必须被隔离
                errors.append(str(exc))
        raise SourceError("全部数据源", "；".join(errors) or "没有可用数据")

    async def market_list(self, page: int = 1, size: int = 200, sort: str = "f3") -> dict[str, Any]:
        data, meta = await self.eastmoney.market(page, size, sort)
        return self.result(data, meta)

    async def indices(self) -> dict[str, Any]:
        data, meta = await self.eastmoney.indices()
        return self.result(data, meta)

    async def limit_pool(self, status: str = "limit_up", trade_date: str | None = None) -> dict[str, Any]:
        loaders: list[Loader]
        if status == "broken":
            loaders = [lambda: self.xgb.pool("limit_up_broken", trade_date)]
        else:
            loaders = [lambda: self.ths.limit_up(trade_date), lambda: self.xgb.pool("limit_up", trade_date)]
        data, meta, reason = await self.fallback(loaders)
        return self.result(data, meta, reason)

    async def ladder(self, trade_date: str | None = None) -> dict[str, Any]:
        pool = await self.limit_pool("limit_up", trade_date)
        groups: dict[int, list[dict[str, Any]]] = {}
        for row in pool["data"]:
            groups.setdefault(int(row.get("board_height") or 1), []).append(row)
        ladder = [
            {"height": height, "count": len(rows), "stocks": rows}
            for height, rows in sorted(groups.items(), reverse=True)
        ]
        return self.result(ladder, pool["meta"])

    async def dashboard(self) -> dict[str, Any]:
        indices_task = asyncio.create_task(self.indices())
        market_task = asyncio.create_task(self.market_list(1, 1000))
        limit_task = asyncio.create_task(self.limit_pool())
        indices, market, limit_rows = await asyncio.gather(indices_task, market_task, limit_task)
        sentiment = market_sentiment(limit_rows["data"], market["data"])
        amount = sum(float(row.get("amount") or 0) for row in market["data"])
        data = {
            "indices": indices["data"],
            "sentiment": sentiment,
            "market_amount": amount,
            "top_gainers": market["data"][:20],
            "limit_preview": limit_rows["data"][:20],
        }
        sources = ", ".join(dict.fromkeys([indices["meta"]["source"], market["meta"]["source"], limit_rows["meta"]["source"]]))
        return self.result(data, {"source": sources, "cached": market["meta"]["cached"]})

    async def auction(self) -> dict[str, Any]:
        results = await asyncio.gather(
            self.supplement.auction(), self.supplement.seal_orders(), self.cls.plate_analysis(),
            return_exceptions=True,
        )
        data: dict[str, Any] = {"live": [], "seal_orders": {}, "plate_analysis": {}}
        sources: list[str] = []
        errors: list[str] = []
        for key, result in zip(data, results, strict=False):
            if isinstance(result, Exception):
                errors.append(str(result))
                continue
            value, meta = result
            data[key] = value.get("live", value) if key == "live" and isinstance(value, dict) else value
            sources.append(meta.get("source", ""))
        return self.result(data, {"source": ", ".join(filter(None, sources)) or "无可用源"}, "；".join(errors) or None)

    async def sectors(self) -> dict[str, Any]:
        results = await asyncio.gather(
            self.eastmoney.sectors(), self.ths.hot_plates(), self.xgb.plates(), return_exceptions=True
        )
        data = {"ranking": [], "hot": [], "limit_up": []}
        sources, errors = [], []
        for key, result in zip(data, results, strict=False):
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                data[key], meta = result
                sources.append(meta.get("source", ""))
        return self.result(data, {"source": ", ".join(filter(None, sources))}, "；".join(errors) or None)

    async def sector_stocks(self, code: str) -> dict[str, Any]:
        data, meta = await self.eastmoney.sector_stocks(code)
        return self.result(data, meta)

    async def intelligence(self, trade_date: str) -> dict[str, Any]:
        lhb, news, events = await asyncio.gather(
            self.eastmoney.lhb(trade_date), self.eastmoney.news(), self.xgb.events(), return_exceptions=True
        )
        data: dict[str, Any] = {"lhb": [], "news": [], "events": []}
        sources, errors = [], []
        for key, result in zip(data, (lhb, news, events), strict=False):
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                data[key], meta = result
                sources.append(meta.get("source", ""))
        return self.result(data, {"source": ", ".join(dict.fromkeys(sources))}, "；".join(errors) or None)

    async def stock_detail(self, code: str) -> dict[str, Any]:
        quote_data, quote_meta, reason = await self.fallback(
            [lambda: self.eastmoney.quote(code), lambda: self.tencent.quote(code)]
        )
        kline_result, minute_result = await asyncio.gather(
            self.eastmoney.kline(code), self.eastmoney.minute(code), return_exceptions=True
        )
        errors = [reason] if reason else []
        kline, minute = [], []
        if isinstance(kline_result, Exception):
            errors.append(str(kline_result))
        else:
            kline_raw, _ = kline_result
            kline = enrich_klines(kline_raw)
        if isinstance(minute_result, Exception):
            errors.append(str(minute_result))
        else:
            minute, _ = minute_result
        return self.result(
            {"quote": quote_data, "kline": kline, "minute": minute},
            quote_meta,
            "；".join(filter(None, errors)) or None,
        )

    async def search(self, keyword: str) -> dict[str, Any]:
        rows, meta = await self.eastmoney.market(1, 5000, "f3")
        term = keyword.strip().lower()
        matched = [row for row in rows if term in row.get("code", "").lower() or term in row.get("name", "").lower()]
        return self.result(matched[:30], meta)

    async def screener(
        self, query: str, filters: list[dict[str, Any]], page: int, page_size: int
    ) -> dict[str, Any]:
        if query.strip():
            rows, meta = await self.eastmoney.smart_search(query, page, page_size)
            return self.result(rows, meta)
        rows, meta = await self.eastmoney.market(1, 5000, "f3")
        filtered = apply_filters(rows, filters)
        begin = (page - 1) * page_size
        return self.result(
            {"total": len(filtered), "rows": filtered[begin : begin + page_size]}, meta
        )

    async def themes(self) -> dict[str, Any]:
        industry, plates, events = await asyncio.gather(
            self.supplement.industry(), self.xgb.plates(), self.xgb.events(50), return_exceptions=True
        )
        data = {"industry": [], "plates": [], "timeline": []}
        sources, errors = [], []
        for key, result in zip(data, (industry, plates, events), strict=False):
            if isinstance(result, Exception):
                errors.append(str(result))
            else:
                data[key], meta = result
                sources.append(meta.get("source", ""))
        return self.result(data, {"source": ", ".join(dict.fromkeys(sources))}, "；".join(errors) or None)

    async def save_daily_snapshot(self) -> None:
        today = date.today().isoformat()
        for category, loader in (
            ("dashboard", self.dashboard), ("limit_up", self.limit_pool), ("sectors", self.sectors)
        ):
            try:
                result = await loader()
                save_snapshot(today, category, result["data"], result["meta"]["source"])
            except Exception:
                continue


service = MarketService()
