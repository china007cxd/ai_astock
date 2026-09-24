# -*- coding: utf-8 -*-
"""东方财富公开接口适配。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from .base import HTTPDataClient

_FIELDS = (
    "f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f15,f16,f17,f18,"
    "f20,f21,f22,f23,f24,f25,f62,f66,f69,f72,f75,f78,f81,f104,f105,f106,f184"
)


def _number(value: Any, divisor: float = 1) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return round(float(value) / divisor, 4)
    except (TypeError, ValueError):
        return None


def _secid(code: str) -> str:
    code = re.sub(r"\D", "", code)[-6:]
    return f"1.{code}" if code.startswith(("5", "6", "9")) else f"0.{code}"


def _quote(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": str(row.get("f12") or ""),
        "name": row.get("f14") or "",
        "price": _number(row.get("f2")),
        "change": _number(row.get("f3")),
        "change_amount": _number(row.get("f4")),
        "volume": _number(row.get("f5")),
        "amount": _number(row.get("f6")),
        "amplitude": _number(row.get("f7")),
        "turnover_rate": _number(row.get("f8")),
        "pe": _number(row.get("f9")),
        "volume_ratio": _number(row.get("f10")),
        "high": _number(row.get("f15")),
        "low": _number(row.get("f16")),
        "open": _number(row.get("f17")),
        "previous_close": _number(row.get("f18")),
        "market_cap": _number(row.get("f20")),
        "float_market_cap": _number(row.get("f21")),
        "pb": _number(row.get("f23")),
        "main_net_inflow": _number(row.get("f62")),
        "rise_count": row.get("f104"),
        "fall_count": row.get("f105"),
        "flat_count": row.get("f106"),
        "raw": row,
    }


class EastMoneyAdapter:
    name = "东方财富"

    def __init__(self, client: HTTPDataClient) -> None:
        self.client = client

    async def market(self, page: int = 1, size: int = 200, sort: str = "f3") -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://82.push2.eastmoney.com/api/qt/clist/get",
            {
                "pn": page,
                "pz": min(size, 5000),
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": sort,
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                "fields": _FIELDS,
            },
            ttl=10,
        )
        rows = ((body or {}).get("data") or {}).get("diff") or []
        return [_quote(row) for row in rows if isinstance(row, dict)], meta

    async def indices(self) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            {
                "fltt": 2,
                "invt": 2,
                "fields": _FIELDS,
                "secids": "1.000001,0.399001,0.399006,1.000688,1.000300,1.000016",
            },
            ttl=8,
        )
        rows = ((body or {}).get("data") or {}).get("diff") or []
        return [_quote(row) for row in rows if isinstance(row, dict)], meta

    async def quote(self, code: str) -> tuple[dict, dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://push2.eastmoney.com/api/qt/stock/get",
            {"secid": _secid(code), "fltt": 2, "invt": 2, "fields": _FIELDS},
            ttl=5,
        )
        return _quote((body or {}).get("data") or {}), meta

    async def quotes(self, codes: list[str]) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            {"fltt": 2, "invt": 2, "fields": _FIELDS, "secids": ",".join(_secid(code) for code in codes)},
            ttl=5,
        )
        rows = ((body or {}).get("data") or {}).get("diff") or []
        return [_quote(row) for row in rows], meta

    async def kline(self, code: str, period: str = "101", count: int = 240) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            {
                "secid": _secid(code),
                "klt": period,
                "fqt": 1,
                "lmt": min(count, 1000),
                "end": "20500101",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            },
            ttl=120,
        )
        lines = ((body or {}).get("data") or {}).get("klines") or []
        result = []
        for line in lines:
            fields = str(line).split(",")
            if len(fields) < 11:
                continue
            result.append(
                {
                    "date": fields[0], "open": _number(fields[1]) or 0, "close": _number(fields[2]) or 0,
                    "high": _number(fields[3]) or 0, "low": _number(fields[4]) or 0,
                    "volume": _number(fields[5]) or 0, "amount": _number(fields[6]) or 0,
                    "amplitude": _number(fields[7]), "change": _number(fields[8]),
                    "change_amount": _number(fields[9]), "turnover": _number(fields[10]),
                }
            )
        return result, meta

    async def minute(self, code: str, days: int = 1) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://push2his.eastmoney.com/api/qt/stock/trends2/get",
            {
                "secid": _secid(code), "ndays": min(days, 5), "iscr": 0, "iscca": 0,
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            },
            ttl=8,
        )
        lines = ((body or {}).get("data") or {}).get("trends") or []
        result = []
        for line in lines:
            fields = str(line).split(",")
            if len(fields) >= 8:
                result.append({"time": fields[0], "price": _number(fields[2]), "average": _number(fields[7]), "volume": _number(fields[5]), "amount": _number(fields[6])})
        return result, meta

    async def sectors(self, size: int = 100) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://push2.eastmoney.com/api/qt/clist/get",
            {"pn": 1, "pz": size, "po": 1, "np": 1, "fid": "f3", "fs": "m:90+t:2+f:!50", "fields": _FIELDS},
            ttl=30,
        )
        rows = ((body or {}).get("data") or {}).get("diff") or []
        return [_quote(row) for row in rows], meta

    async def sector_stocks(self, sector: str) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://push2.eastmoney.com/api/qt/clist/get",
            {"pn": 1, "pz": 500, "po": 1, "np": 1, "fid": "f3", "fs": f"b:{sector}", "fields": _FIELDS},
            ttl=20,
        )
        rows = ((body or {}).get("data") or {}).get("diff") or []
        return [_quote(row) for row in rows], meta

    async def lhb(self, trade_date: str) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            {
                "reportName": "RPT_DAILYBILLBOARD_DETAILS", "columns": "ALL", "pageNumber": 1,
                "pageSize": 500, "sortColumns": "SECURITY_CODE", "sortTypes": "1",
                "filter": f"(TRADE_DATE='{trade_date}')",
            },
            ttl=300,
        )
        return ((body or {}).get("result") or {}).get("data") or [], meta

    async def news(self, size: int = 50) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
            {"client": "web", "biz": "web_news_col", "fastColumn": "102", "sortEnd": "", "pageSize": size},
            ttl=30,
        )
        data = (body or {}).get("data") or {}
        return data.get("fastNewsList") or data.get("list") or [], meta

    async def smart_search(self, query: str, page: int, size: int) -> tuple[list[dict], dict]:
        token = uuid.uuid4().hex
        body, meta = await self.client.post_json(
            self.name,
            "https://np-tjxg-b.eastmoney.com/api/smart-tag/stock/v3/pw/search-code",
            {
                "keywordNew": query, "pageSize": size, "pageNo": page, "fingerprint": token,
                "timestamp": int(datetime.now().timestamp() * 1000), "requestId": uuid.uuid4().hex,
                "gids": [], "shareToGuba": False, "needShowStockNum": False, "client": "WEB",
            },
            ttl=60,
        )
        result = (((body or {}).get("data") or {}).get("result") or {})
        return result.get("dataList") or [], meta
