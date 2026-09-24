"""LangChain 工具层：把 astock HTTP 接口 + 东财直连封装为 agent 工具

【这个文件是干什么的】
工具的"统一入口目录"。把底层数据能力（astock 接口、东财直连）包装成
一个个标准化的 agent 工具（带功能说明 + 参数说明），运行引擎按工具名
调用，未来接入 LangGraph ReAct 式自主决策时也能直接复用。

【给小白的关键概念】
- @tool 装饰器：LangChain 提供的装饰器，把一个函数标记为"工具"。
  LLM 能读懂函数的 docstring（功能说明）来决定什么时候调用它。
- 所有工具均为 async（异步）：运行引擎直接 await 调用。
- docstring 按 LLM 可读格式书写（含 Args 说明）：LLM 是靠读
  docstring 理解工具用途的，所以这里的文档写得规范很重要。
- ALL_TOOLS：工具清单。新增工具记得加进这个列表，否则引擎发现不了。
"""
from __future__ import annotations

from langchain_core.tools import tool

from . import eastmoney as em
from .astock_client import client as astock


@tool
async def em_xuangu(query: str, size: int = 100) -> dict:
    """东财智能选股：输入自然语言选股条件，返回符合条件股票列表（服务端智能解析）。

    Args:
        query: 自然语言选股条件，保持简洁，如 "MACD金叉"、"主力净流入大于0"、"市盈率低于20"
        size: 返回数量上限（10-100）
    """
    return await astock.get("em_xuangu", q=query, size=size)


@tool
async def wencai(query: str, size: int = 100) -> dict:
    """问财选股（本地关键词匹配版）：按涨停原因/题材/板块/名称/拼音匹配股票。

    Args:
        query: 关键词（空格或逗号分隔），如 "涨停 半导体"
        size: 返回数量上限
    """
    return await astock.get("wencai", q=query, size=size)


@tool
async def get_kline(code: str, count: int = 320) -> dict:
    """获取个股前复权日K线（含开收高低量/振幅/换手率），供技术指标计算。

    Args:
        code: 股票代码，如 "000001"
        count: K线根数（60-800）
    """
    return await astock.get("kline", code=code, period="day", count=count)


@tool
async def get_chips(code: str) -> dict:
    """获取个股筹码分布（通达信式三角分布）：平均成本/90%与70%成本区间/90%成本集中度/获利盘比例。

    Args:
        code: 股票代码，如 "000001"
    """
    return await astock.get("chips", code=code, date="")


@tool
async def get_hot_plates() -> dict:
    """获取当日热门概念板块热度榜（同花顺最强风口）：板块名+热度排名。"""
    return await astock.get("fengkou")


@tool
async def get_plate_flow() -> dict:
    """获取行业板块主力资金流排行（东财）：板块名+主力净流入额。"""
    return await astock.get("plate_flow")


@tool
async def get_quotes(codes: str) -> dict:
    """批量获取个股实时行情（最多60只）：现价/涨跌幅。

    Args:
        codes: 逗号分隔的股票代码，如 "000001,600519"
    """
    return await astock.get("quotes", codes=codes)


@tool
async def get_stock_boards(code: str) -> list[dict]:
    """获取个股所属板块列表（东财直连）：[{"code","name","pct"}]，用于判断是否属于热点板块。

    Args:
        code: 股票代码，如 "600519"
    """
    return await em.stock_boards(code)


@tool
async def get_stock_flow(codes: list[str]) -> list[dict]:
    """获取个股资金流（东财直连，最多60只）：主力/超大单/大单/中单/小单净流入。

    Args:
        codes: 股票代码列表，如 ["600519", "000001"]
    """
    return await em.stock_flow(codes)


# 工具总清单：运行引擎从这里取工具。新增工具后记得追加进列表。
ALL_TOOLS = [
    em_xuangu, wencai, get_kline, get_chips, get_hot_plates,
    get_plate_flow, get_quotes, get_stock_boards, get_stock_flow,
]
