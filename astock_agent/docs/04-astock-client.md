# 04-astock-client：astock 数据服务客户端（`src/astock_agent/astock_client.py`）

## 职责

本项目的"数据源头"。所有行情数据统一通过 HTTP 调用 astock 看盘服务
（`D:\SoftwareInstallaction\v62.1\astock`，先启动它的 `启动.bat`，端口 8765），
本模块不重复实现抓取逻辑，只负责发请求、失败重试。

## 对外接口

| 接口 | 说明 |
|---|---|
| `client`（全局单例） | 整个进程共用一个连接池 |
| `await client.get(name, **params) -> dict` | 请求 `/api/{name}` 接口；None/空串参数自动过滤；失败重试一次，两次失败抛 `AstockError` |
| `await client.health() -> bool` | 连通性检查（用最轻量的 /api/dates 接口） |
| `await client.aclose()` | 关闭连接（停机时释放） |

## 常用接口名（`get` 的 name 参数）

`kline`（日K线）、`chips`（筹码分布）、`fengkou`（热门概念榜）、
`plate_flow`（板块资金流）、`quotes`（批量实时行情）、
`em_xuangu`（东财智能选股）、`wencai`（问财本地匹配）、`dates`（交易日历）

## 谁依赖它

- `tools.py`：把所有 astock 接口包装成 LangChain 工具
- `verifiers.py`：拉 K线/筹码/热门榜/资金榜做验证
- `engine.py`：补实时行情
- `main.py`：健康检查、运行前置校验

## 修改注意点

1. **超时 90 秒是调优结果**：`plate_flow` 在 push2 主站故障时
   多主机轮询可达 57 秒，之前 45 秒超时导致误报失败。
   不要轻易调小。
2. **`get` 已带重试**：调用方不要再包一层重试循环，避免重试风暴。
3. **过滤空参数**：`v not in (None, "")` 是有意行为——空参数会让
   astock 接口走默认值。
4. 新增接口时只需 `await client.get("新接口名", ...)`，无需改本文件，
   但建议同时在 `tools.py` 加一个对应的 LangChain 工具包装。
