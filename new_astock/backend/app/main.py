"""FastAPI 入口与后台任务。"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .adapters.base import http_client
from .api import compat_router, router
from .config import ROOT_DIR, settings
from .database import cleanup_snapshots, init_database
from .services import service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("new_astock")
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.ensure_directories()
    init_database()
    cleanup_snapshots()
    scheduler.add_job(service.save_daily_snapshot, "cron", day_of_week="mon-fri", hour=15, minute=10, id="daily-review", replace_existing=True)
    scheduler.add_job(cleanup_snapshots, "cron", hour=3, minute=10, id="cleanup", replace_existing=True)
    scheduler.start()
    logger.info("new_astock 服务已启动")
    yield
    scheduler.shutdown(wait=False)
    await http_client.close()


app = FastAPI(
    title="new_astock API",
    version="1.0.0",
    description="独立 A 股复盘、选股与导出服务",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("请求失败 request_id=%s path=%s", request_id, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "服务器内部错误", "request_id": request_id})
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(router)
app.include_router(compat_router)

frontend_dist = ROOT_DIR / "frontend" / "dist"
assets_dir = frontend_dist / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str):
    if path.startswith(("api/", "compat/", "w1/")):
        return JSONResponse(status_code=404, content={"detail": "接口不存在"})
    index = frontend_dist / "index.html"
    requested = frontend_dist / path
    if path and requested.is_file() and frontend_dist in requested.resolve().parents:
        return FileResponse(requested)
    if index.is_file():
        return FileResponse(index)
    return JSONResponse(
        status_code=200,
        content={"message": "后端已就绪；请先在 frontend 目录执行 npm run build", "docs": "/docs"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
