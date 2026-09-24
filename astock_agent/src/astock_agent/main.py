"""astock_agent Web 服务入口（FastAPI，端口 8766）

【这个文件是干什么的】
整个 agent 的"门面"：对外提供 REST API + Web 页面。前端（web/ 目录
的原生 JS 单页应用）只通过这里的接口和 agent 交互；学习、运行等
耗时操作在这里转成后台任务异步执行。

REST API：
  健康检查   GET  /api/health
  模式管理   GET/POST /api/modes、DELETE /api/modes/{mode_id}、GET /api/modes/{mode_id}
  案例管理   POST /api/modes/{mode_id}/cases、DELETE /api/modes/{mode_id}/cases/{case_id}
             GET  /api/modes/{mode_id}/cases/{case_id}/images/{name}（截图预览）
  学习管线   POST /api/modes/{mode_id}/learn（后台任务）
  草案人审   GET/PUT/DELETE /api/modes/{mode_id}/draft、POST /api/modes/{mode_id}/confirm
  选股运行   POST /api/modes/{mode_id}/run（后台任务）
  任务进度   GET  /api/jobs/{job_id}
  历史记录   GET  /api/runs、GET /api/runs/{run_id}
  校验目录   GET  /api/verifiers

启动：uv run uvicorn astock_agent.main:app --host 127.0.0.1 --port 8766

【给小白的关键概念】
- FastAPI：Python 最流行的 Web 框架。@app.get("/路径") 装饰一个函数
  就注册了一个接口；参数和返回值自动做 JSON 转换和文档生成
  （运行后可访问 /docs 看自动生成的接口文档）。
- 后台任务模式：POST /learn 和 /run 不直接干重活，而是立刻返回
  job_id，用 asyncio.create_task 让 _learn_job/_run_job 在后台跑，
  前端轮询 /api/jobs/{id} 看进度。HTTP 请求不能长时间挂着。
- HTTPException：抛这个异常 = 返回对应的 HTTP 错误码给前端
  （400 参数错 / 404 不存在 / 503 服务未就绪）。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, jobs, storage
from .astock_client import client
from .engine import Engine
from .learn.diff import diff_rules
from .learn.extract import extract_draft
from .learn.vision import analyze_case_images
from .llm import has_llm
from .models import Rule
from .verifiers import VERIFIER_INFO

config.ensure_dirs()  # 启动即确保所有数据目录存在

app = FastAPI(title="A股选股 Agent", version="0.1.0")

# 截图单张上限 20MB
_MAX_IMAGE_BYTES = 20 * 1024 * 1024


# ---- 请求体模型：FastAPI 会自动把请求 JSON 解析成这些对象 ----

class ModeBody(BaseModel):
    """新建模式请求体：{"name": "模式名"}"""
    name: str


class DraftBody(BaseModel):
    """保存草案请求体：{"rule": {...}}（前端编辑后的规则）"""
    rule: dict


# ---------------- 静态页面 ----------------
# 把 web/static/ 目录挂载为 /static 路径（app.css / app.js 从此访问）

app.mount("/static", StaticFiles(directory=config.WEB_DIR / "static"), name="static")


@app.get("/")
async def index():
    """首页：直接返回 web/index.html（前端单页应用）"""
    return FileResponse(config.WEB_DIR / "index.html")


# ---------------- 健康检查 / 校验目录 ----------------

@app.get("/api/health")
async def health() -> dict:
    """健康检查：astock 连通性 + LLM Key 配置状态（启动脚本和前端状态栏使用）"""
    return {
        "ok": True,
        "astock": await client.health(),   # astock 服务是否可用
        "astock_base": config.ASTOCK_BASE,
        "llm": has_llm(),                  # DeepSeek Key 是否已配置
        "models": {"text": config.TEXT_MODEL, "vision": config.VISION_MODEL},
    }


@app.get("/api/verifiers")
async def verifiers() -> dict:
    """校验函数目录（学习确认页编辑 verify 条件时使用）

    返回格式：{compute名: {"desc": 功能说明, "params": 默认参数}}
    前端据此渲染"函数选择下拉框 + 参数编辑表单"。
    """
    return {k: {"desc": v[0], "params": v[1]} for k, v in VERIFIER_INFO.items()}


# ---------------- 模式管理 ----------------

@app.get("/api/modes")
async def list_modes() -> list[dict]:
    """模式列表（模式管理页首页数据）"""
    return storage.list_modes()


@app.post("/api/modes")
async def create_mode(body: ModeBody) -> dict:
    """新建模式：在 cases/ 下建文件夹"""
    try:
        mid = storage.create_mode(body.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"mode_id": mid}


@app.delete("/api/modes/{mode_id}")
async def remove_mode(mode_id: str) -> dict:
    """删除模式：案例 + 规则 + 草案一起删"""
    if not (config.CASES_DIR / mode_id).is_dir():
        raise HTTPException(404, "模式不存在")
    storage.delete_mode(mode_id)
    return {"ok": True}


@app.get("/api/modes/{mode_id}")
async def mode_detail(mode_id: str) -> dict:
    """模式详情：案例列表 + 正式规则 + 待审草案（进入模式后的页面数据）"""
    if not (config.CASES_DIR / mode_id).is_dir():
        raise HTTPException(404, "模式不存在")
    rule = storage.load_rule(mode_id)
    return {
        "mode_id": mode_id,
        "cases": storage.list_cases(mode_id),
        "rule": rule.model_dump() if rule else None,
        "draft": storage.load_draft(mode_id),
    }


# ---------------- 案例管理 ----------------

@app.post("/api/modes/{mode_id}/cases")
async def add_case(mode_id: str, case_name: str = Form(""),
                   description: str = Form(""),
                   files: list[UploadFile] = File([])) -> dict:
    """新增案例（multipart 表单上传：案例名 + 说明 + 截图文件）

    注意参数用 Form/File 而不是 JSON body，因为要传文件。
    校验：模式存在、扩展名是图片、非空、单张不超过 20MB。
    """
    if not (config.CASES_DIR / mode_id).is_dir():
        raise HTTPException(404, "模式不存在")
    image_files = []
    for f in files:
        if not f.filename:
            continue  # 前端可能传空文件框，跳过
        ext = Path(f.filename).suffix.lower()
        if ext not in config.IMAGE_EXTS:
            raise HTTPException(400, "仅支持图片文件(png/jpg/gif/webp): %s" % f.filename)
        data = await f.read()
        if not data:
            raise HTTPException(400, "图片内容为空: %s" % f.filename)
        if len(data) > _MAX_IMAGE_BYTES:
            raise HTTPException(400, "图片超过20MB: %s" % f.filename)
        image_files.append((f.filename, data))
    try:
        case_id = storage.add_case(mode_id, case_name, description, image_files)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"case_id": case_id}


@app.delete("/api/modes/{mode_id}/cases/{case_id}")
async def remove_case(mode_id: str, case_id: str) -> dict:
    """删除单个案例"""
    storage.delete_case(mode_id, case_id)
    return {"ok": True}


@app.get("/api/modes/{mode_id}/cases/{case_id}/images/{image_name}")
async def case_image(mode_id: str, case_id: str, image_name: str):
    """返回案例截图文件（前端 <img> 直接引用此地址预览）"""
    p = config.CASES_DIR / mode_id / case_id / image_name
    if not p.is_file():
        raise HTTPException(404, "图片不存在")
    return FileResponse(p)


# ---------------- 学习管线（后台任务） ----------------

@app.post("/api/modes/{mode_id}/learn")
async def start_learn(mode_id: str) -> dict:
    """发起学习：立即返回 job_id，真正的工作在后台 _learn_job 里跑

    前置校验：模式存在、有案例、配了 LLM Key。
    """
    if not (config.CASES_DIR / mode_id).is_dir():
        raise HTTPException(404, "模式不存在")
    if not storage.list_cases(mode_id):
        raise HTTPException(400, "该模式下还没有案例，请先在「模式管理」页上传案例（截图+说明.md）")
    if not has_llm():
        raise HTTPException(
            400, "未配置 DEEPSEEK_API_KEY，请在 astock_agent/.env 中填写后重启服务")
    job_id = jobs.create_job("learn", "学习模式《%s》" % mode_id)
    asyncio.create_task(_learn_job(job_id, mode_id))  # 不 await：放后台跑
    return {"job_id": job_id}


async def _learn_job(job_id: str, mode_id: str) -> None:
    """学习任务：截图解读(视觉模型) → 规则提炼(文本模型) → diff → 存草案

    进度设计：0-5% 准备，5%-55% 截图解读（按图片数均分），
    60% 规则提炼，85% diff 对比，完成时 100%。
    """
    try:
        cases = storage.list_cases(mode_id)
        total_imgs = sum(c["image_count"] for c in cases) or 1  # 防除0
        materials, done = [], 0
        # 阶段1：逐个案例解读截图（视觉模型）
        for c in cases:
            rd = storage.read_case(mode_id, c["case_id"])
            jobs.log(job_id, "解读案例「%s」的 %d 张截图" % (c["case_id"], len(rd["image_paths"])))
            vision = await analyze_case_images(
                rd["image_paths"], progress=lambda s: jobs.log(job_id, s))
            done += len(rd["image_paths"])
            jobs.set_progress(job_id, 5 + int(done / total_imgs * 50),
                              "截图解读 %d/%d 张" % (done, total_imgs))
            materials.append({"case_id": c["case_id"], "description": rd["description"],
                              "vision": vision})
        # 阶段2：文本模型归纳规则草案
        jobs.set_progress(job_id, 60, "规则提炼")
        jobs.log(job_id, "文本模型归纳规则草案（可能耗时1-3分钟）...")
        # extract_draft 是同步函数（阻塞），扔线程池跑防卡事件循环
        draft = await asyncio.to_thread(extract_draft, mode_id, materials)
        # 阶段3：与已存规则对比（增量学习时前端高亮差异）
        jobs.set_progress(job_id, 85, "对比已存规则")
        old = storage.load_rule(mode_id)
        draft["diff"] = diff_rules(old, Rule.model_validate(draft["rule"]))
        storage.save_draft(mode_id, draft)
        jobs.log(job_id, "草案已生成（%d 条条件），请到「学习确认」页审查" %
                 len(draft["rule"]["conditions"]))
        jobs.finish(job_id, {"mode_id": mode_id}, "待确认")
    except Exception as e:  # noqa —— 任何失败都记录到任务，前端能看到原因
        jobs.fail(job_id, str(e))


# ---------------- 草案人审 ----------------

@app.get("/api/modes/{mode_id}/draft")
async def get_draft(mode_id: str) -> dict:
    """读草案（学习确认页初始数据）"""
    d = storage.load_draft(mode_id)
    if d is None:
        raise HTTPException(404, "该模式暂无草案，请先在「模式管理」页点学习")
    return d


@app.put("/api/modes/{mode_id}/draft")
async def save_draft(mode_id: str, body: DraftBody) -> dict:
    """保存人审修改后的草案（重新计算与已存规则的 diff）

    前端编辑条件后点"保存"，整个规则体传过来；
    这里做 Pydantic 校验 + 重算 diff + 落盘。
    """
    try:
        rule = Rule.model_validate(body.rule)
    except Exception as e:  # noqa
        raise HTTPException(400, "规则校验失败: %s" % e)
    prev = storage.load_draft(mode_id) or {}
    draft = {"rule": rule.model_dump(),
             "evidence": prev.get("evidence") or {},   # 证据映射保留
             "diff": diff_rules(storage.load_rule(mode_id), rule)}
    storage.save_draft(mode_id, draft)
    return draft


@app.delete("/api/modes/{mode_id}/draft")
async def discard_draft(mode_id: str) -> dict:
    """放弃草案（重新学习前清掉旧的）"""
    storage.delete_draft(mode_id)
    return {"ok": True}


@app.post("/api/modes/{mode_id}/confirm")
async def confirm_draft(mode_id: str) -> dict:
    """确认草案 → 保存为正式规则（草案删除、规则落盘 rules/）"""
    try:
        rule = storage.confirm_draft(mode_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return rule.model_dump()


@app.post("/api/modes/{mode_id}/rule")
async def import_rule(mode_id: str, body: DraftBody) -> dict:
    """直接导入正式规则（跳过学习管线，用于手动创建/测试规则）

    接受完整的 Rule JSON，校验后直接落盘为正式规则。
    如果已有草案，会先丢弃旧草案再写入。
    前端没有直接入口，推荐用 curl 或 Python requests 调用：
      curl -X POST http://127.0.0.1:8766/api/modes/{mode_id}/rule
           -H "Content-Type: application/json"
           -d @rule.json
    """
    if not (config.CASES_DIR / mode_id).is_dir():
        raise HTTPException(404, "模式不存在，请先在模式管理页创建")
    try:
        rule = Rule.model_validate(body.rule)
    except Exception as e:
        raise HTTPException(400, "规则校验失败: %s" % e)
    # 确保 rule 的 mode_id 与路径一致
    rule.mode_id = mode_id
    # 删除旧草案（如果有），再保存新草案 + 确认
    storage.delete_draft(mode_id)
    draft = {"rule": rule.model_dump(),
             "evidence": {},
             "diff": diff_rules(storage.load_rule(mode_id), rule)}
    storage.save_draft(mode_id, draft)
    try:
        confirmed = storage.confirm_draft(mode_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return confirmed.model_dump()


# ---------------- 选股运行（后台任务） ----------------

@app.post("/api/modes/{mode_id}/run")
async def start_run(mode_id: str) -> dict:
    """发起选股运行：立即返回 job_id，后台 _run_job 执行引擎

    前置校验：有正式规则（已学习+已确认）、astock 服务在线。
    """
    if storage.load_rule(mode_id) is None:
        raise HTTPException(400, "该模式尚未确认规则：请先学习，再到「学习确认」页确认保存")
    if not await client.health():
        raise HTTPException(503, "astock 数据服务未启动（%s），请先启动 astock" % config.ASTOCK_BASE)
    job_id = jobs.create_job("run", "运行模式《%s》" % mode_id)
    asyncio.create_task(_run_job(job_id, mode_id))
    return {"job_id": job_id}


async def _run_job(job_id: str, mode_id: str) -> None:
    """运行任务：引擎日志实时写入任务进度

    Engine 的 progress 回调接 jobs.log（每条日志进度+3%，封顶95），
    前端轮询即可看到"执行查询条件.../取交集后候选N只/验证..."的实时日志。
    """
    try:
        eng = Engine(progress=lambda s: jobs.log(job_id, s, bump=3))
        run = await eng.run(mode_id)
        jobs.finish(job_id, {"run_id": run.run_id, "status": run.status,
                             "stock_count": len(run.stocks),
                             "empty_reason": run.empty_reason}, "运行完成")
    except Exception as e:  # noqa
        jobs.fail(job_id, str(e))


# ---------------- 任务进度 / 历史记录 ----------------

@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str) -> dict:
    """任务进度轮询端点（前端每 1-2 秒调一次）"""
    j = jobs.get(job_id)
    if j is None:
        raise HTTPException(404, "任务不存在（服务重启后任务记录清空）")
    return j


@app.get("/api/runs")
async def list_runs() -> list[dict]:
    """历史运行记录列表（摘要）"""
    return storage.list_runs()


@app.get("/api/runs/{run_id}")
async def run_detail(run_id: str) -> dict:
    """单次运行完整结果（含条件结果和股票明细）"""
    r = storage.load_run(run_id)
    if r is None:
        raise HTTPException(404, "运行记录不存在")
    return r.model_dump()
