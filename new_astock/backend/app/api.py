# -*- coding: utf-8 -*-
"""REST、兼容接口与实时行情通道。"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from .adapters.base import SourceError, http_client
from .cache import cache
from .database import (
    get_settings,
    get_snapshots,
    list_screeners,
    list_watchlist,
    patch_settings,
    remove_watch,
    save_screener,
    upsert_watch,
)
from .exporter import export_data
from .schemas import ExportRequest, ScreenerRequest, SettingPatch
from .services import service

router = APIRouter(prefix="/api/v1")
compat_router = APIRouter()


def _raise_source_error(exc: SourceError) -> None:
    raise HTTPException(status_code=503, detail={"source": exc.source, "message": exc.message}) from exc


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "date": date.today().isoformat(), "sources": http_client.health()}


@router.get("/market/overview")
async def market_overview() -> dict[str, Any]:
    try:
        return await service.dashboard()
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/market/indices")
async def market_indices() -> dict[str, Any]:
    try:
        return await service.indices()
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/market/stocks")
async def market_stocks(page: int = 1, size: int = Query(200, ge=1, le=5000), sort: str = "f3") -> dict[str, Any]:
    try:
        return await service.market_list(page, size, sort)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/limit-up")
async def limit_up(status: str = "limit_up", trade_date: str | None = None) -> dict[str, Any]:
    try:
        return await service.limit_pool(status, trade_date)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/limit-up/ladder")
async def limit_ladder(trade_date: str | None = None) -> dict[str, Any]:
    try:
        return await service.ladder(trade_date)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/auction")
async def auction() -> dict[str, Any]:
    return await service.auction()


@router.get("/sectors")
async def sectors() -> dict[str, Any]:
    return await service.sectors()


@router.get("/sectors/{sector_code}/stocks")
async def sector_stocks(sector_code: str) -> dict[str, Any]:
    try:
        return await service.sector_stocks(sector_code)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/intelligence")
async def intelligence(trade_date: str | None = None) -> dict[str, Any]:
    return await service.intelligence(trade_date or date.today().isoformat())


@router.get("/themes")
async def themes() -> dict[str, Any]:
    return await service.themes()


@router.get("/review")
async def review() -> dict[str, Any]:
    return await market_overview()


@router.get("/anomaly")
async def anomaly() -> dict[str, Any]:
    return await service.auction()


@router.get("/lhb")
async def lhb(trade_date: str | None = None) -> dict[str, Any]:
    result = await service.intelligence(trade_date or date.today().isoformat())
    return service.result(result["data"].get("lhb", []), result["meta"])


@router.get("/news")
async def news() -> dict[str, Any]:
    result = await service.intelligence(date.today().isoformat())
    return service.result(result["data"].get("news", []), result["meta"])


@router.get("/stocks/search")
async def stock_search(q: str = Query(min_length=1, max_length=30)) -> dict[str, Any]:
    try:
        return await service.search(q)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/stocks/{code}/kline")
async def stock_kline(
    code: str,
    period: str = "101",
    count: int = Query(240, ge=10, le=1000),
) -> dict[str, Any]:
    try:
        rows, meta = await service.eastmoney.kline(code[-6:], period, count)
        from .indicators import enrich_klines

        return service.result(enrich_klines(rows), meta)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/stocks/{code}/minute")
async def stock_minute(code: str, days: int = Query(1, ge=1, le=5)) -> dict[str, Any]:
    try:
        rows, meta = await service.eastmoney.minute(code[-6:], days)
        return service.result(rows, meta)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/stocks/{code}")
async def stock_detail(code: str) -> dict[str, Any]:
    if not code[-6:].isdigit():
        raise HTTPException(status_code=400, detail="股票代码格式错误")
    try:
        return await service.stock_detail(code[-6:])
    except SourceError as exc:
        _raise_source_error(exc)


@router.post("/screeners/run")
async def run_screener(request: ScreenerRequest) -> dict[str, Any]:
    try:
        return await service.screener(request.query, request.filters, request.page, request.page_size)
    except SourceError as exc:
        _raise_source_error(exc)


@router.get("/screeners")
async def saved_screeners() -> dict[str, Any]:
    return {"data": list_screeners()}


@router.post("/screeners/{name}")
async def persist_screener(name: str, request: ScreenerRequest) -> dict[str, Any]:
    save_screener(name, request.model_dump())
    return {"ok": True}


@router.get("/watchlist")
async def watchlist() -> dict[str, Any]:
    items = list_watchlist()
    if not items:
        return {"data": [], "meta": {"source": "本地", "cached": False}}
    try:
        quotes, meta = await service.eastmoney.quotes([item["code"] for item in items])
        notes = {item["code"]: item for item in items}
        return service.result([{**row, **notes.get(row["code"], {})} for row in quotes], meta)
    except SourceError:
        return {"data": items, "meta": {"source": "本地", "cached": True, "stale": True}}


@router.post("/watchlist/{code}")
async def add_watch(code: str, body: dict[str, str] = Body(default={})) -> dict[str, Any]:
    upsert_watch(code[-6:], body.get("name", ""), body.get("group", "默认"), body.get("note", ""))
    return {"ok": True}


@router.delete("/watchlist/{code}")
async def delete_watch(code: str) -> dict[str, Any]:
    remove_watch(code[-6:])
    return {"ok": True}


@router.get("/history")
async def history(trade_date: str | None = None) -> dict[str, Any]:
    return {"data": get_snapshots(trade_date), "meta": {"source": "SQLite", "cached": True}}


@router.post("/history/snapshot")
async def create_snapshot() -> dict[str, Any]:
    await service.save_daily_snapshot()
    return {"ok": True}


@router.post("/exports")
async def create_export(request: ExportRequest) -> FileResponse:
    if len(request.rows) > 10000:
        raise HTTPException(status_code=400, detail="单次最多导出 10000 行")
    path = export_data(request)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.get("/settings")
async def settings_get() -> dict[str, Any]:
    return {"data": get_settings()}


@router.patch("/settings")
async def settings_patch(request: SettingPatch) -> dict[str, Any]:
    forbidden = {key for key in request.values if "token" in key.lower() or "password" in key.lower()}
    if forbidden:
        raise HTTPException(status_code=400, detail="凭证请写入本地 .env 文件")
    return {"data": patch_settings(request.values)}


@router.get("/sources")
async def sources() -> dict[str, Any]:
    known = ["东方财富", "同花顺", "选股宝", "财联社", "腾讯行情", "短线侠", "九阳公社", "龙虎VIP"]
    health_map = {item["source"]: item for item in http_client.health()}
    return {
        "data": [
            health_map.get(source, {"source": source, "ok": None, "checked_at": None, "error": "尚未请求"})
            for source in known
        ]
    }


@router.post("/cache/clear")
async def clear_cache() -> dict[str, Any]:
    return {"ok": True, "removed": cache.clear()}


@router.websocket("/ws/market")
async def market_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            try:
                await websocket.send_json(await service.dashboard())
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        return


def _legacy(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    items = data if isinstance(data, list) else []
    return {
        "State": 0,
        "Data": data,
        "List": items,
        "Count": len(items),
        "Page": 0,
        "Meta": result.get("meta", {}),
    }


@compat_router.get("/compat/w1/api/index.php")
@compat_router.get("/w1/api/index.php")
async def compatibility_api(
    a: str,
    c: str = "",
    Day: str | None = None,
    Date: str | None = None,
    StockID: str | None = None,
    PlateID: str | None = None,
    Type: str | None = None,
    Index: int = 0,
    st: int = 200,
) -> dict[str, Any]:
    trade_date = Day or Date
    try:
        if a in {"DailyLimitPerformance", "DailyLimitPerformance2", "HisDaBanList"}:
            return _legacy(await service.limit_pool("limit_up", trade_date))
        if a in {"DiskReview", "ChangeStatistics", "RiseFallAnalysis"}:
            return _legacy(await service.dashboard())
        if a in {"RealRankingInfo", "GetPlateInfo", "GetPlateInfo_w38", "GetBKJJ_w36", "GetBKJJBL"}:
            return _legacy(await service.sectors())
        if a in {"ZhiShuStockList_W8", "GetGroupStock_ByGroup_W28"} and PlateID:
            return _legacy(await service.sector_stocks(PlateID))
        if a in {"MorningBiddingList", "Radar", "GetFengKListBest", "GetWPQC"}:
            return _legacy(await service.auction())
        if a in {"GetStockList", "GetYTFP_LHBDX"}:
            result = await service.intelligence(trade_date or date.today().isoformat())
            result["data"] = result["data"].get("lhb", [])
            return _legacy(result)
        if a in {"InfoList", "ZhiBoContent", "GetPoint"}:
            return _legacy(await service.themes())
        if StockID:
            return _legacy(await service.stock_detail(StockID[-6:]))
        result = await service.market_list(max(1, Index + 1), min(st, 5000))
        return _legacy(result)
    except SourceError as exc:
        return {"State": -1, "Data": [], "List": [], "Count": 0, "Page": Index, "Error": str(exc), "Controller": c, "Type": Type}
