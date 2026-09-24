"""后台任务管理器：学习/选股运行等长任务的进度跟踪（内存态，服务重启即清空）

【这个文件是干什么的】
学习、选股运行都要跑几十秒甚至几分钟，HTTP 请求不能一直干等。
解决方案：API 收到请求后立刻返回一个 job_id，任务在后台跑，
前端拿着 job_id 每隔一两秒轮询一次进度（百分比/阶段/日志流），
跑完了再拿结果。本文件就是这些后台任务的"进度登记处"。

【给小白的关键概念】
- 内存态：任务信息存在进程内存的字典里（_jobs），不落盘。
  服务重启后历史任务记录就没了——这是有意为之：任务只是"过程"，
  真正的产物（规则/运行结果）已由 storage.py 落盘。
- 轮询（polling）：前端定时问"好了没"，比 websocket 简单可靠。
- 进度约定：任务进行中进度封顶 95%，只有 finish() 才置 100%。
  这样前端看到 100% 就知道结果一定已经写好。

任务对象：{job_id, kind, label, status(running/done/failed), progress, stage,
           logs, result, error, created, finished}
"""
from __future__ import annotations

import time
import uuid

_jobs: dict[str, dict] = {}  # 内存任务表：job_id → 任务字典
_MAX_LOGS = 300              # 每个任务最多保留 300 条日志（防内存膨胀）


def create_job(kind: str, label: str) -> str:
    """创建一个新任务并登记，返回 job_id

    job_id = 时分秒 + 6位随机串，可读且不会重复。
    kind = 任务类型（learn/run），label = 显示名称（如"MACD金叉启动"）。
    """
    job_id = "%s_%s" % (time.strftime("%H%M%S"), uuid.uuid4().hex[:6])
    _jobs[job_id] = {
        "job_id": job_id, "kind": kind, "label": label,
        "status": "running", "progress": 0, "stage": "排队中",
        "logs": [], "result": None, "error": None,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"), "finished": None,
    }
    return job_id


def log(job_id: str, msg: str, stage: str | None = None, bump: int = 0) -> None:
    """追加一条日志；可同时更新当前阶段、累加进度百分比（封顶95，完成时才到100）

    参数：
        msg: 日志内容（自动加时间戳前缀 [HH:MM:SS]）
        stage: 同时更新的阶段名（如"截图解读"），可选
        bump: 进度累加值，如 bump=10 表示进度 +10%
    """
    j = _jobs.get(job_id)
    if not j:
        return
    j["logs"].append("[%s] %s" % (time.strftime("%H:%M:%S"), msg))
    # 只保留最后 300 条：del j["logs"][:-300] 把前面的老日志删掉
    if len(j["logs"]) > _MAX_LOGS:
        del j["logs"][:-_MAX_LOGS]
    if stage:
        j["stage"] = stage
    if bump:
        j["progress"] = min(95, j["progress"] + bump)


def set_progress(job_id: str, pct: int, stage: str | None = None) -> None:
    """直接把进度设为某个百分比（0~100 之间自动夹取），可选更新阶段"""
    j = _jobs.get(job_id)
    if not j:
        return
    j["progress"] = max(0, min(100, pct))
    if stage:
        j["stage"] = stage


def finish(job_id: str, result: dict | None = None, stage: str = "完成") -> None:
    """任务成功收尾：状态置 done、进度 100、附上结果"""
    j = _jobs.get(job_id)
    if not j:
        return
    j["status"] = "done"
    j["progress"] = 100
    j["stage"] = stage
    j["result"] = result
    j["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")


def fail(job_id: str, error: str) -> None:
    """任务失败收尾：状态置 failed、记录错误信息（进度保持原样供排查）"""
    j = _jobs.get(job_id)
    if not j:
        return
    j["status"] = "failed"
    j["stage"] = "失败"
    j["error"] = error
    j["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    log(job_id, "任务失败: %s" % error)


def get(job_id: str) -> dict | None:
    """查单个任务（前端轮询 /api/jobs/{id} 就是调它）"""
    return _jobs.get(job_id)


def list_jobs() -> list[dict]:
    """所有任务列表（按创建时间倒序）"""
    return sorted(_jobs.values(), key=lambda j: j["created"], reverse=True)
