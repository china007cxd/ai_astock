# 15-main：Web 服务入口（`src/astock_agent/main.py`）

## 职责

整个 agent 的"门面"。提供 REST API + Web 页面，前端（web/ 原生 JS
单页应用）只通过这里的接口与 agent 交互；耗时操作转后台任务。

## REST API 一览

| 分组 | 端点 | 说明 |
|---|---|---|
| 页面 | `GET /` | 返回 index.html（前端入口） |
| 健康 | `GET /api/health` | astock 连通性 + LLM 配置状态 |
| 校验目录 | `GET /api/verifiers` | 16 个校验函数目录（前端编辑器用） |
| 模式 | `GET/POST /api/modes` | 列表/新建 |
| | `GET/DELETE /api/modes/{mode_id}` | 详情/删除 |
| 案例 | `POST /api/modes/{mode_id}/cases` | 上传案例（multipart：名称+说明+截图） |
| | `DELETE /api/modes/{mode_id}/cases/{case_id}` | 删案例 |
| | `GET .../cases/{case_id}/images/{name}` | 截图预览 |
| 学习 | `POST /api/modes/{mode_id}/learn` | 发起学习（后台任务，返回 job_id） |
| 草案 | `GET/PUT/DELETE /api/modes/{mode_id}/draft` | 读/存/弃草案 |
| | `POST /api/modes/{mode_id}/confirm` | 确认草案 → 正式规则 |
| 运行 | `POST /api/modes/{mode_id}/run` | 发起选股（后台任务，返回 job_id） |
| 任务 | `GET /api/jobs/{job_id}` | 轮询进度 |
| 历史 | `GET /api/runs` / `GET /api/runs/{run_id}` | 记录列表/详情 |

## 两个后台任务（本文件的核心）

### `_learn_job(job_id, mode_id)`
```
0-5% 准备 → 5%-55% 逐案例截图解读(按图片数均分)
→ 60% 规则提炼(extract_draft, 扔线程池)
→ 85% diff 对比 → 存草案 → finish("待确认")
```

### `_run_job(job_id, mode_id)`
```
Engine(progress=回调接jobs.log) → run() → finish(结果摘要)
```

## 关键约定

- **前置校验在接口层做**：start_learn 校验模式存在/有案例/有 Key；
  start_run 校验有规则/astock 在线。后台任务内部只 try/except 兜底。
- **HTTP 错误码语义**：400 参数错 / 404 不存在 / 503 astock 未启动。
- **静态资源**：`/static` 挂载 web/static/；截图接口直接 FileResponse。

## 谁依赖它

- 前端 `web/static/app.js`（消费全部 API）
- `启动.bat`（等 8766 端口就绪 + 打开浏览器）
- 测试脚本 `scripts/_stage_e_test.py`（全端点验收）

## 修改注意点

1. **加端点**：命名遵守 `/api/资源[/{id}][/子资源]` 的 REST 风格；
   加完同步更新本文件顶部 docstring 的 API 清单、docs 本文档、
   `scripts/_stage_e_test.py`（全端点自检）。
2. **长操作必须走后台任务模式**（create_task + job_id + 轮询），
   不要写同步阻塞端点——会卡死整个事件循环。
3. **表单字段名**（case_name/description/files）与前端 FormData
   严格对应，改名要同步 app.js 的 `uploadCase()`。
4. `save_draft` 里会重算 diff——前端保存草案后 diff 高亮要刷新，
   这是有意行为。
5. 上传图片校验（扩展名/非空/20MB）在接口层做，storage 层不重复校验。
