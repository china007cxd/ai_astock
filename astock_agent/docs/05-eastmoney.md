# 05-eastmoney：东财直连（`src/astock_agent/eastmoney.py`）

## 职责

补 astock 服务没有的两个数据点，直接请求东方财富公开接口：
- **个股所属板块**（`/api/qt/slist/get?spt=3`）
- **个股资金流**（`/api/qt/ulist.np/get`）

其余数据一律走 astock，只有这两个走这里。

## 对外接口

| 函数 | 返回 | 缓存 |
|---|---|---|
| `await stock_boards(code) -> list[dict]` | `[{code,name,pct,mkt}]` 所属板块 | 5 分钟 |
| `await stock_flow(codes) -> list[dict]` | 资金流明细（主力/超大单/大单/中单/小单净额） | 60 秒 |

## 关键概念

- **secid 转换**（`_esecid`）：6/5/9 开头 → 沪市 `1.xxxxxx`；
  其余 → 深市 `0.xxxxxx`；支持 `sh/sz/bj` 前缀输入。
- **多主机轮询**：`push2` / `90.push2` / `push2delay` 三个镜像挨个试，
  谁通用谁。历史上 push2 主站挂过而 push2delay 正常，所以保留三个。
- **TTL 缓存**：同一批数据短时间内不重复发网络，降低被限流概率。
- **diff 兼容**：东财 `diff` 字段有时是 `{0:行,1:行}` 有时是 `[行,行]`，
  `_rows_of()` 统一转 list。
- **单次上限 60 只**：`stock_flow` 里 `[:60]` 截断是接口硬限制。

## 谁依赖它

- `tools.py`：`get_stock_boards` / `get_stock_flow` 两个工具
- `verifiers.py`：板块类校验（`in_hot_plate`/`in_plate_flow_top`）、
  资金类校验（`main_net_gt/lt` 的 `_flow_row`）

## 修改注意点

1. **东财接口字段是 `f12/f13/f14` 这种代号**，含义对照写在代码注释里，
   改动前先确认字段代号没变（东财偶尔调整）。
2. **缓存空结果也是有意行为**（`_cache_set(key, rows)` 在空时也执行），
   防止接口故障时每次请求都打一轮失败主机。
3. 加第三个数据点直连东财时，遵循"astock 有就用 astock"的原则，
   只有 astock 确实没有才写在这里。
