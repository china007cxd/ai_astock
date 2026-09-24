# -*- coding: utf-8 -*-
"""对外稳定数据模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceMeta(BaseModel):
    source: str
    updated_at: datetime = Field(default_factory=datetime.now)
    cached: bool = False
    stale: bool = False
    fallback_reason: str | None = None


class ApiResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: Any
    meta: SourceMeta


class StockQuote(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    name: str = ""
    price: float | None = None
    change: float | None = None
    change_amount: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    amplitude: float | None = None
    volume_ratio: float | None = None
    pe: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    main_net_inflow: float | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class KlinePoint(BaseModel):
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float = 0
    amount: float = 0
    amplitude: float | None = None
    change: float | None = None
    turnover: float | None = None


class LimitUpStock(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    name: str = ""
    price: float | None = None
    change: float | None = None
    board_height: int = 1
    reason: str = ""
    first_time: str = ""
    last_time: str = ""
    order_amount: float | None = None
    turnover_rate: float | None = None
    status: str = "涨停"
    plates: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ScreenerRequest(BaseModel):
    query: str = ""
    filters: list[dict[str, Any]] = Field(default_factory=list)
    page: int = 1
    page_size: int = Field(default=50, ge=1, le=500)


class ExportRequest(BaseModel):
    title: str = "A股数据导出"
    format: str = Field(pattern="^(csv|xlsx)$")
    columns: list[dict[str, str]]
    rows: list[dict[str, Any]]


class SettingPatch(BaseModel):
    values: dict[str, Any]
