# 07-tools：LangChain 工具层（`src/astock_agent/tools.py`）

## 职责

把底层数据能力包装成标准的 LangChain 工具（`@tool` 装饰器），
运行引擎按工具名调用；未来接 ReAct 式自主决策时可直接复用。

## 工具清单（ALL_TOOLS）

| 工具名 | 数据来源 | 用途 |
|---|---|---|
| `em_xuangu(query, size)` | astock | 东财智能选股（自然语言）——引擎分条查询的主力 |
| `wencai(query, size)` | astock | 问财本地关键词匹配 |
| `get_kline(code, count)` | astock | 个股前复权日K线 |
| `get_chips(code)` | astock | 筹码分布 |
| `get_hot_plates()` | astock | 热门概念榜 |
| `get_plate_flow()` | astock | 板块主力资金榜 |
| `get_quotes(codes)` | astock | 批量实时行情（≤60只） |
| `get_stock_boards(code)` | 东财直连 | 个股所属板块 |
| `get_stock_flow(codes)` | 东财直连 | 个股资金流（≤60只） |

## 关键约定

- **docstring 是给 LLM 看的**：规范地写清功能和 Args，LLM 靠它
  理解工具用途。改功能时必须同步改 docstring。
- **全部 async**：调用方式 `await tool.ainvoke({...})`。
- **新增工具记得进 `ALL_TOOLS`**，否则引擎发现不了。

## 谁依赖它

- `engine.py`：直接 `em_xuangu.ainvoke(...)`（目前只用到这一个）

## 修改注意点

1. 工具只做"转发+说明"，不要在工具函数里写业务逻辑（校验逻辑在
   verifiers，流程在 engine）。
2. `em_xuangu` 的 `size` 默认 100：东财单次返回上限相关，改小会
   导致交集候选池变小。
