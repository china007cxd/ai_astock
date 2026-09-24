# -*- coding: utf-8 -*-
"""同花顺、选股宝、财联社、腾讯及补充数据源。"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from ..config import settings
from .base import HTTPDataClient, SourceError


def _number(value: Any, divisor: float = 1) -> float | None:
    try:
        return round(float(value) / divisor, 4) if value not in (None, "", "-") else None
    except (TypeError, ValueError):
        return None


def _time(value: Any) -> str:
    text = str(value or "")
    if text.isdigit() and len(text) >= 6:
        text = text[-6:]
        return f"{text[:2]}:{text[2:4]}:{text[4:]}"
    return text


class ThsAdapter:
    name = "同花顺"

    def __init__(self, client: HTTPDataClient) -> None:
        self.client = client

    async def limit_up(self, trade_date: str | None = None) -> tuple[list[dict], dict]:
        params = {
            "page": 1, "limit": 200,
            "field": "199112,10,9001,330323,330324,330325,9002,330329,133971,133970,1968584,3475914,9003,9004",
            "filter": "HS,GEM2STAR", "order_field": 133970, "order_type": 0,
        }
        if trade_date:
            params["date"] = trade_date.replace("-", "")
        body, meta = await self.client.get_json(
            self.name,
            "https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool",
            params,
            ttl=20 if not trade_date else 300,
            headers={"Referer": "https://data.10jqka.com.cn/limit_up/"},
        )
        rows = ((body or {}).get("data") or {}).get("info") or []
        result = []
        for row in rows:
            days = str(row.get("high_days") or "1天1板")
            match = re.search(r"(\d+)板", days)
            result.append(
                {
                    "code": str(row.get("code") or ""), "name": row.get("name") or "",
                    "price": _number(row.get("latest")), "change": _number(row.get("change_rate")),
                    "board_height": int(match.group(1)) if match else 1,
                    "reason": row.get("reason_type") or "", "first_time": _time(row.get("first_limit_up_time")),
                    "last_time": _time(row.get("last_limit_up_time")),
                    "order_amount": _number(row.get("order_amount")), "turnover_rate": _number(row.get("turnover_rate")),
                    "status": "涨停", "plates": [], "raw": row,
                }
            )
        return result, meta

    async def hot_stocks(self) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt",
            ttl=60,
        )
        data = (body or {}).get("data") or body or {}
        return data.get("stock_list") or data.get("list") or [], meta

    async def hot_plates(self) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_plate/concept/data.txt",
            ttl=60,
        )
        return ((body or {}).get("data") or {}).get("plate_list") or [], meta


class XgbAdapter:
    name = "选股宝"

    def __init__(self, client: HTTPDataClient) -> None:
        self.client = client

    async def pool(self, pool: str = "limit_up", trade_date: str | None = None) -> tuple[list[dict], dict]:
        params: dict[str, Any] = {"pool_name": pool}
        if trade_date:
            params["date"] = trade_date
        body, meta = await self.client.get_json(
            self.name,
            "https://flash-api.xuangubao.com.cn/api/pool/detail",
            params,
            ttl=20 if not trade_date else 300,
        )
        rows = (body or {}).get("data") or []
        output = []
        for row in rows:
            reason = row.get("surge_reason") or {}
            plates = [p.get("plate_name", "") for p in reason.get("related_plates", []) if p.get("plate_name")]
            output.append(
                {
                    "code": str(row.get("symbol") or "")[-6:], "name": row.get("stock_chi_name") or "",
                    "price": _number(row.get("price")), "change": _number(row.get("change_percent"), 0.01),
                    "board_height": int(row.get("limit_up_days") or 1),
                    "reason": reason.get("stock_reason") or "", "first_time": row.get("first_limit_up") or "",
                    "last_time": row.get("last_limit_up") or "", "turnover_rate": _number(row.get("turnover_ratio"), 0.01),
                    "status": "炸板" if pool == "limit_up_broken" else "涨停", "plates": plates, "raw": row,
                }
            )
        return output, meta

    async def events(self, count: int = 100) -> tuple[list[dict], dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://flash-api.xuangubao.com.cn/api/event/history",
            {"count": count, "types": "9,10,11,12"},
            ttl=30,
        )
        return (body or {}).get("data") or [], meta

    async def plates(self, trade_date: str | None = None) -> tuple[list[dict], dict]:
        params = {"date": trade_date} if trade_date else {}
        body, meta = await self.client.get_json(
            self.name,
            "https://flash-api.xuangubao.com.cn/api/surge_stock/plates",
            params,
            ttl=60,
        )
        return (body or {}).get("data") or [], meta


class ClsAdapter:
    name = "财联社"

    def __init__(self, client: HTTPDataClient) -> None:
        self.client = client

    async def plate_analysis(self) -> tuple[dict, dict]:
        body, meta = await self.client.get_json(
            self.name,
            "https://x-quote.cls.cn/v2/quote/a/plate/up_down_analysis",
            ttl=30,
        )
        return (body or {}).get("data") or {}, meta


class TencentAdapter:
    name = "腾讯行情"

    def __init__(self, client: HTTPDataClient) -> None:
        self.client = client

    async def quote(self, code: str) -> tuple[dict, dict]:
        prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
        text, meta = await self.client.get_text(
            self.name,
            "https://qt.gtimg.cn/q=" + prefix + code[-6:],
            ttl=5,
            encoding="gbk",
        )
        match = re.search(r'="(.*)"', text)
        fields = match.group(1).split("~") if match else []
        if len(fields) < 50:
            raise SourceError(self.name, "行情字段不完整")
        return {
            "code": fields[2], "name": fields[1], "price": _number(fields[3]),
            "previous_close": _number(fields[4]), "open": _number(fields[5]), "volume": _number(fields[6]),
            "change_amount": _number(fields[31]), "change": _number(fields[32]), "high": _number(fields[33]),
            "low": _number(fields[34]), "amount": _number(fields[37], 0.0001), "turnover_rate": _number(fields[38]),
            "pe": _number(fields[39]), "amplitude": _number(fields[43]), "float_market_cap": _number(fields[44], 0.0001),
            "market_cap": _number(fields[45], 0.0001), "pb": _number(fields[46]), "volume_ratio": _number(fields[49]),
            "raw": fields,
        }, meta


class SupplementAdapter:
    name = "公开补充源"

    def __init__(self, client: HTTPDataClient) -> None:
        self.client = client

    async def auction(self) -> tuple[dict, dict]:
        live, meta = await self.client.get_json(
            "短线侠", "https://duanxianxia.com/vendor/stockdata/jjlive.json", ttl=15
        )
        return {"live": live}, meta

    async def seal_orders(self) -> tuple[dict, dict]:
        body, meta = await self.client.get_json(
            "短线侠", "https://duanxianxia.com/api/getFengdanLast", ttl=20
        )
        current = body.get(date.today().isoformat()) if isinstance(body, dict) else None
        return current or body or {}, meta

    async def industry(self) -> tuple[Any, dict]:
        body, meta = await self.client.get_json(
            "九阳公社", "https://app.jiuyangongshe.com/jystock-app/api/v1/action/industry/list", ttl=600
        )
        return (body or {}).get("data") or body or [], meta


class LonghuVipAdapter:
    name = "龙虎VIP"
    hosts = {
        "history": "https://apphis.longhuvip.com/w1/api/index.php",
        "realtime": "https://apphq.longhuvip.com/w1/api/index.php",
        "after": "https://apphwhq.longhuvip.com/w1/api/index.php",
        "lhb": "https://applhb.longhuvip.com/w1/api/index.php",
        "article": "https://apparticle.longhuvip.com/w1/api/index.php",
    }

    def __init__(self, client: HTTPDataClient) -> None:
        self.client = client

    @property
    def enabled(self) -> bool:
        return bool(settings.longhuvip_token and settings.longhuvip_user_id)

    async def action(self, host: str, controller: str, action: str, params: dict[str, Any]) -> tuple[Any, dict]:
        if not self.enabled:
            raise SourceError(self.name, "未配置 Token/UserID")
        query = {
            "c": controller, "a": action, "Token": settings.longhuvip_token,
            "UserID": settings.longhuvip_user_id, "PhoneOSNew": 1, **params,
        }
        return await self.client.get_json(
            self.name,
            self.hosts.get(host, self.hosts["realtime"]),
            query,
            ttl=20,
            headers={"Referer": "https://www.longhuvip.com/"},
        )
