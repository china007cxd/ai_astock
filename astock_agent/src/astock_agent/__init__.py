"""astock_agent：A股选股 Agent（案例学习 → 规则库 → 工具筛选）

【项目一句话介绍】
从用户的历史选股案例（截图+说明）里用 LLM 学习出一套可执行的选股
规则，再通过东财数据工具按规则自动筛选股票，全程带 Web 界面。

【核心流程】
1. 上传案例（截图 + 说明.md）到某模式
2. 学习：视觉模型解读截图 → 文本模型归纳规则草案 → 人审确认 → 存规则库
3. 运行：按规则分条查询（东财智能选股）→ 取交集 → 数据工具逐只验证
   → LLM 生成命中说明 → 存档

【包结构（src/astock_agent/）】
- main.py          Web 服务入口（FastAPI REST API）
- engine.py        运行引擎（LangGraph 状态机，选股流程编排）
- learn/           学习管线（vision 截图解读 / extract 规则提炼 / diff 差异对比）
- verifiers.py     校验函数注册表（verify 条件的数据工具）
- indicators.py    技术指标计算（纯函数）
- tools.py         LangChain 工具层
- eastmoney.py     东财直连（板块/资金流）
- astock_client.py astock 服务 HTTP 客户端
- storage.py       文件存储层（cases/rules/drafts/runs）
- jobs.py          后台任务进度管理
- llm.py           DeepSeek 客户端
- models.py        Pydantic 数据模型
- config.py        全局配置
"""
__version__ = "0.1.0"
