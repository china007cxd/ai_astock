# 10-jobs：后台任务进度管理（`src/astock_agent/jobs.py`）

## 职责

学习、运行等耗时操作的"进度登记处"。API 收到请求后立刻返回
`job_id`，任务在后台跑，前端轮询进度（百分比/阶段/日志流）。

## 任务对象结构

```
{job_id, kind(learn/run), label, status(running/done/failed),
 progress(0-100), stage(阶段名), logs(日志列表),
 result(完成结果), error(失败原因), created, finished}
```

## 函数清单

| 函数 | 用途 |
|---|---|
| `create_job(kind, label) -> job_id` | 登记新任务（job_id=时分秒+6位随机串） |
| `log(job_id, msg, stage=None, bump=0)` | 追加日志；可同时更新阶段/累加进度 |
| `set_progress(job_id, pct, stage=None)` | 直接设定进度（自动夹取0~100） |
| `finish(job_id, result, stage)` | 成功收尾：done + 100% + 结果 |
| `fail(job_id, error)` | 失败收尾：failed + 错误信息 |
| `get(job_id)` / `list_jobs()` | 查询单个/全部任务 |

## 关键约定

- **内存态**：任务存在进程内存，**服务重启即清空**。有意为之——
  任务是"过程"，产物（规则/结果）已由 storage 落盘。
- **进度封顶 95%**：只有 `finish()` 才置 100%。前端约定：
  看到 100% 说明结果一定已写好（可安全拉取）。
- **日志上限 300 条**：防内存膨胀，只留最新。

## 谁依赖它

- `main.py`：`_learn_job` / `_run_job` 全程写进度；
  `/api/jobs/{id}` 端点供前端轮询。

## 修改注意点

1. **保持内存态**：不要把任务落盘——历史任务记录没有任何价值，
   反而增加复杂度。
2. **进度语义**：bump 是"累加"、set_progress 是"设定"，混用会让
   进度条乱跳。学习任务用 set_progress（按图片数精确分档），
   运行任务用 bump（每步+3）。
3. 前端 app.js 的 `pollJob()` 依赖 status/error/result 字段名，
   改名要同步前端。
