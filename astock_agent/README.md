# A股选股 Agent（astock_agent）

从你自己的选股案例（截图 + 文字）中学习选股逻辑，提炼成结构化规则，运行时通过东财智能选股 + 数据工具自动筛选股票。

**核心理念**：案例是数据、规则是产物、运行时只做确定性执行。截图只在离线学习时被视觉模型解读一次，运行时不看图、不做自由 ReAct。

```
案例库(cases/) → 离线学习管线(视觉+文本LLM) → 人审确认 → 规则库(rules/*.yaml)
                                                        ↓
                            Web 界面 ← 运行引擎(LangGraph+工具) ← astock 数据服务(8765)
```

## 架构（两进程）

| 进程 | 端口 | 职责 |
|---|---|---|
| astock（已有项目） | 8765 | 东财智能选股/问财/K线/筹码/板块/资金流等 20+ HTTP 端点 |
| astock_agent（本项目） | 8766 | FastAPI + Web 前端：模式管理 / 学习确认 / 选股运行 / 历史记录 |

astock_agent 仅通过 HTTP 调用 astock，不 import astock 代码。

## 目录结构

```
astock_agent/
├── 启动.bat                  # 一键启动（先 astock 后 agent）
├── pyproject.toml            # uv 管理，包名 astock-agent，src 布局
├── .env                      # DEEPSEEK_API_KEY 等配置（复制 .env.example 填写）
├── cases/                    # 案例库（用户维护）
├── rules/                    # 学习产物（人审确认后保存）
├── drafts/                   # 待确认草案
├── runs/                     # 每次运行结果存档
├── scripts/                  # 自检脚本
├── src/astock_agent/
│   ├── main.py               # FastAPI 入口（端口 8766，完整 REST API）
│   ├── jobs.py               # 后台任务管理器（学习/运行进度跟踪）
│   ├── config.py / models.py / llm.py / astock_client.py
│   ├── eastmoney.py          # 直连东财补缺失数据（个股板块/个股资金流）
│   ├── indicators.py         # pandas 指标计算库
│   ├── tools.py              # LangChain @tool 封装（9 个数据工具）
│   ├── verifiers.py          # 16 个校验函数 + 注册表
│   ├── engine.py             # LangGraph 运行引擎
│   ├── storage.py            # cases/rules/drafts/runs 文件存储
│   └── learn/                # vision(截图解读) / extract(规则提炼) / diff(增量对比)
├── docs/                     # 代码说明文档（每个源文件一篇，含架构总览，见 docs/README.md）
└── web/                      # 前端（浅色单页，原生 JS）
```

## 快速开始

1. 配置密钥：复制 `.env.example` 为 `.env`，填写 `DEEPSEEK_API_KEY`（DeepSeek 官网获取）
2. 双击 `启动.bat`（自动拉起 astock 与 agent，浏览器打开 http://127.0.0.1:8766）
   - 或手动：先启动 `..\astock\启动.bat`，再在本目录执行
     `uv run uvicorn astock_agent.main:app --host 127.0.0.1 --port 8766`
3. 顶部状态栏确认 `astock: 已连接`、`LLM: 已配置Key`

## 使用流程

1. **模式管理**：新建模式（每套选股逻辑一个模式）→ 上传案例（拖拽截图 + 说明.md）→ 点「学习规则」
2. **学习确认**：审查 LLM 提炼的草案（条件增删改、查询语句修改、证据/差异对比）→ 「确认保存为正式规则」
3. **选股运行**：选模式 → 开始选股 → 实时进度 → 结果表格（代码/名称/现价/涨幅/命中条件/说明）；交集为空时会提示各条件命中数与放宽方向
4. **历史记录**：查看历次运行结果

## 案例库约定

- 每套模式一个文件夹（文件夹名即模式名，如 `模式1_MACD金叉`）
- 每个案例一个子文件夹：截图任意命名多张（PNG/JPG/GIF/WebP），文字放 `说明.md`
- 说明.md 风格不限（条件清单 / 叙事复盘 / 截图有标注均可）
- 新增案例：把新案例文件夹丢进对应模式文件夹 → Web 点「学习规则」（增量学习：新草案与旧规则 diff → 确认合并）

## 规则 Schema（学习产物）

```yaml
mode_id: 模式1_MACD金叉
name: MACD金叉启动
description: 日线MACD金叉 + 主力净流入为正 + 筹码低位密集
combine: intersection            # 各条件取交集（union 为备选）
conditions:
  - id: c1
    text: 日线MACD金叉
    type: query                  # query = 东财智能选股自然语言查询
    query: "MACD金叉"
  - id: c2
    text: 筹码低位密集(90%成本集中度<15%)
    type: verify                 # verify = 数据工具逐只验证
    compute: chips_concentration_lt
    params: {threshold: 15}
verified_at: "2026-08-24 21:00:00"
case_count: 8
```

## 校验函数（verify 条件可用，学习时模型自动选择）

| compute | 功能 | 默认参数 |
|---|---|---|
| macd_gold_cross / macd_dead_cross | 近N日MACD金叉/死叉 | {lookback: 3} |
| ma_bull_alignment / ma_bear_alignment | 均线多头/空头排列 | {} |
| price_above_ma | 收盘价站上MA(n) | {n: 20} |
| pct_gain_range | 近days日累计涨幅区间 | {days: 5, lo: -100, hi: 100} |
| new_high_n_days | 收盘价创n日新高 | {n: 60} |
| vol_shrink_break | 放量突破前高 | {shrink_n: 5, break_n: 20, vol_mult: 1.5} |
| chips_concentration_lt | 90%筹码集中度低于threshold | {threshold: 15} |
| profit_ratio_lt / profit_ratio_gt | 获利盘低于/高于threshold | {threshold: 30 / 70} |
| avg_cost_near_price | 现价与平均成本差距在pct%内 | {pct: 5} |
| in_hot_plate | 所属板块在热门概念榜前top_n | {top_n: 20} |
| in_plate_flow_top | 所属板块在主力资金榜前n | {n: 20} |
| main_net_gt / main_net_lt | 主力净流入大于/小于value | {value: 0} |

## 运行引擎流程（LangGraph）

```
load_rule → query_conditions(并行查询) → intersect(取交集)
         → verify_conditions(并发8逐只验证) → summarize(LLM生成命中说明) → 存档
```

- 查询语句来自规则而非现场生成：可复现、低成本；LLM 只在结果解读阶段使用
- 交集为空：提前终止，返回各条件命中数，提示放宽方向
- 单工具失败：重试后仍失败则标注「该条件未验证」，不中断整体流程

## 自检

```bash
uv run python scripts/selftest.py        # 工具层自检（astock 端点 + 东财直连，需 astock 运行）
uv run python scripts/_stage_e_test.py   # Web API 全端点自检（需 agent 服务运行在 8766）
uv run python scripts/learn_mode.py 模式名   # 学习管线 CLI（需配置 DEEPSEEK_API_KEY）
```

## 代码说明文档

想学习代码或让 AI 帮你改代码？先读 [`docs/README.md`](docs/README.md)：
架构图、两条核心数据流（学习流/运行流）、关键约定，以及每个源文件
一篇的模块说明（职责/接口/依赖/修改注意点）。源文件内也写了面向
初学者的详细中文注释。

## 常见问题

- **「未配置 DEEPSEEK_API_KEY」**：在 `.env` 填写 key 后重启 agent 服务
- **「astock 数据服务未启动」**：先运行 `..\astock\启动.bat`，或直接用一键启动.bat
- **学习无反应/任务失败**：查看任务日志（页面进度区）；确认案例文件夹里有截图或说明.md
- **交集为空**：结果页展示各条件命中数，回到「学习确认」放宽/调整某条条件后重新运行
- **东财智能选股解析不了复杂语句**：规则里的查询语句保持简洁（一条查询一个核心条件），失败自动回退 wencai 并标注
