# astock_agent 代码说明文档

> 本目录是服务端代码（`src/astock_agent/`）的配套说明文档。
> 每个 `.py` 文件都有一篇对应的说明，供两类读者使用：
> - **人类读者（尤其 Python 新手）**：理解每个文件干什么、关键概念是什么
> - **AI 修改代码时**：快速定位要改的文件、了解模块间约定和易错点
>
> 每个源文件内部也写了详细注释，与本文档互为补充：注释讲"这一行/这一段"，
> 文档讲"这个文件整体"。

## 快速导航

| 文件 | 说明文档 | 一句话职责 |
|---|---|---|
| `src/astock_agent/__init__.py` | [00-项目总览](00-项目总览.md) | 包入口 + 项目导览 |
| `config.py` | [01-config.md](01-config.md) | 全局配置（路径/Key/地址） |
| `models.py` | [02-models.md](02-models.md) | 数据模型（规则/条件/结果） |
| `llm.py` | [03-llm.md](03-llm.md) | DeepSeek 客户端（文本+视觉） |
| `astock_client.py` | [04-astock-client.md](04-astock-client.md) | astock 数据服务 HTTP 客户端 |
| `eastmoney.py` | [05-eastmoney.md](05-eastmoney.md) | 东财直连（板块/资金流） |
| `indicators.py` | [06-indicators.md](06-indicators.md) | 技术指标计算（纯函数） |
| `tools.py` | [07-tools.md](07-tools.md) | LangChain 工具层 |
| `verifiers.py` | [08-verifiers.md](08-verifiers.md) | 校验函数注册表 |
| `storage.py` | [09-storage.md](09-storage.md) | 文件存储层（4个数据目录） |
| `jobs.py` | [10-jobs.md](10-jobs.md) | 后台任务进度管理 |
| `engine.py` | [11-engine.md](11-engine.md) | 运行引擎（LangGraph 状态机） |
| `learn/vision.py` | [12-learn-vision.md](12-learn-vision.md) | 学习管线①截图解读 |
| `learn/extract.py` | [13-learn-extract.md](13-learn-extract.md) | 学习管线②规则提炼 |
| `learn/diff.py` | [14-learn-diff.md](14-learn-diff.md) | 学习管线③差异对比 |
| `main.py` | [15-main.md](15-main.md) | Web 服务入口（REST API） |

## 整体架构

```
┌──────────────────── 浏览器（web/ 原生JS单页应用） ────────────────────┐
│  模式管理 │ 学习确认 │ 选股运行 │ 历史记录        （四标签页）          │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTP (REST API)
┌──────────────────────────────▼───────────────────────────────────────┐
│                        main.py（FastAPI，端口8766）                    │
│   模式/案例 CRUD │ 学习任务 │ 草案人审 │ 运行任务 │ 任务进度 │ 历史记录 │
└───────┬──────────────────┬─────────────────────┬─────────────────────┘
        │                  │                     │
        ▼                  ▼                     ▼
   ┌─────────┐      ┌────────────┐        ┌────────────┐
   │ jobs.py │      │ 学习管线    │        │ engine.py  │
   │ 任务进度 │      │ learn/     │        │ 运行引擎    │
   └─────────┘      │ ①vision    │        │ (LangGraph) │
                    │ ②extract   │        └─────┬──────┘
                    │ ③diff      │              │
                    └─────┬──────┘              │
                          │                     │
                          ▼                     ▼
                  ┌──────────────┐     ┌───────────────┐
                  │  storage.py  │     │  verifiers.py │  校验函数注册表
                  │ 文件存储层    │     └──┬───────┬────┘
                  │ cases/rules/ │        │       │
                  │ drafts/runs/ │        ▼       ▼
                  └──────────────┘  ┌──────────┐ ┌──────────────┐
                          ▲         │indicators│ │eastmoney/    │
                          │         │技术指标  │ │astock_client │
                     LLM 调用走 llm.py│(纯计算) │ │(HTTP取数)    │
                          │         └──────────┘ └──────────────┘
                          │                        │        │
                  ┌───────▼────────┐        ┌──────▼─┐ ┌────▼─────┐
                  │ DeepSeek API   │        │ astock │ │ 东财接口  │
                  │ (chat+vision)  │        │ :8765  │ │ push2... │
                  └────────────────┘        └────────┘ └──────────┘
```

## 两条核心数据流

### 学习流（案例 → 规则）
```
案例文件夹(cases/模式/案例/截图*.png+说明.md)
  → learn/vision.py 视觉模型逐张解读截图 → 结构化形态描述
  → learn/extract.py 文本模型归纳 → 规则草案 dict
  → learn/diff.py 与已存规则对比（增量学习高亮差异）
  → storage.save_draft 存 drafts/模式.yaml
  → 人在"学习确认"页审改 → storage.confirm_draft 转正 rules/模式.yaml
```

### 运行流（规则 → 选股结果）
```
rules/模式.yaml → engine.Engine.run()
  → 节点1 load_rule      校验规则
  → 节点2 query_conditions  并行调东财智能选股（tools.em_xuangu）分条查询
  → 节点3 intersect         取交集 → 候选池（空则提前结束并提示）
  → 节点4 verify_conditions 并行逐只调 verifiers 验证 + 补实时行情
  → 节点5 summarize         LLM 生成命中说明（失败用模板兜底）
  → storage.save_run 存 runs/时间戳.json → 历史记录页可查
```

## 关键约定（改代码前必读）

1. **数据来源分工**：行情数据一律走 `astock_client`（astock 服务）；只有
   "个股所属板块"和"个股资金流"两个数据点直连东财（`eastmoney.py`）。
   不要在某模块里私自新开一种取数方式。
2. **校验函数三处注册**：在 `verifiers.py` 新增校验函数时，必须同时改
   `v_xxx 函数`、`VERIFIER_INFO`（说明+默认参数）、`VERIFIERS`（注册表）
   三处，否则前端看不到或引擎调不到。
3. **规则条件两种类型**：`query`（自然语言，交东财查）和 `verify`
   （数据工具逐只验证），由 `models.py` 的判别联合校验字段合法性。
4. **存储就是文件夹**：不要引入数据库；所有持久化都落在
   `cases/ rules/ drafts/ runs/` 四个目录，文件格式为 YAML/JSON/图片。
5. **后台任务模式**：耗时操作（学习/运行）一律 POST 接口立即返回
   `job_id`，后台 `asyncio.create_task` 执行，进度写 `jobs.py`，
   前端轮询 `/api/jobs/{id}`。不要写同步阻塞的长接口。
6. **容错原则**：单只股票数据失败 = 标记"未验证"而不是整体失败；
   LLM 失败 = 用模板兜底；单个存储文件损坏 = 返回 None 跳过。
7. **代码风格**：所有模块 docstring 用中文；对外 API 说明放函数
   docstring；`from __future__ import annotations` 允许直接用
   `list[dict]`、`str | None` 等新式类型注解。
8. **测试**：`scripts/selftest.py`（工具层自检）、
   `scripts/_stage_a~e_test.py`（各阶段验收）、
   `scripts/learn_mode.py`（命令行学一个模式）。

## 环境与启动

```bat
:: 一键启动（推荐）：先拉起 astock 数据服务，再启动 agent 并打开浏览器
astock_agent\启动.bat

:: 手动启动 agent（需先启动 astock\启动.bat）
cd astock_agent
uv run uvicorn astock_agent.main:app --host 127.0.0.1 --port 8766
```

- Web 界面：http://127.0.0.1:8766
- API 文档（FastAPI 自动生成）：http://127.0.0.1:8766/docs
- 配置：`astock_agent/.env`（DeepSeek Key 等）
