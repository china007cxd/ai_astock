# 08-verifiers：校验函数注册表（`src/astock_agent/verifiers.py`）

## 职责

"逐只验证"环节的执行器。规则里 `type=verify` 的条件在这里找到对应的
校验函数，对候选池每只股票逐一判断。

## 三层结构

1. **`v_xxx` 函数**：`async fn(code, params) -> (是否满足, 说明)`。
   数据拉取失败抛异常（引擎捕获后标"未验证"）。
2. **`VERIFIER_INFO`**：校验函数说明目录（compute名 → 功能说明+默认参数）。
   学习管线提示词（extract.VERIFY_CATALOG）和前端编辑器
   （/api/verifiers）都从它生成——**单一数据源，改一处三处同步**。
3. **`VERIFIERS`**：真正的注册表（compute名 → 函数），引擎按名调用。

## 现有 16 个校验函数

| compute 名 | 功能 | 默认参数 | 数据来源 |
|---|---|---|---|
| `macd_gold_cross` | 近N日MACD金叉 | lookback=3 | K线 |
| `macd_dead_cross` | 近N日MACD死叉 | lookback=3 | K线 |
| `ma_bull_alignment` | 均线多头排列 | - | K线 |
| `ma_bear_alignment` | 均线空头排列 | - | K线 |
| `price_above_ma` | 收盘站上MA(n) | n=20 | K线 |
| `pct_gain_range` | 近days日涨幅∈[lo,hi] | days=5 | K线 |
| `new_high_n_days` | 收盘创n日新高 | n=60 | K线 |
| `vol_shrink_break` | 放量突破前高 | shrink_n=5, break_n=20, vol_mult=1.5 | K线 |
| `chips_concentration_lt` | 90%筹码集中度<threshold | threshold=15 | 筹码 |
| `profit_ratio_lt` | 获利盘<threshold | threshold=30 | 筹码 |
| `profit_ratio_gt` | 获利盘>threshold | threshold=70 | 筹码 |
| `avg_cost_near_price` | 现价距平均成本≤pct% | pct=5 | 筹码 |
| `in_hot_plate` | 板块在热门概念榜前top_n | top_n=20 | 板块+榜 |
| `in_plate_flow_top` | 板块在主力资金榜前n | n=20 | 板块+榜 |
| `main_net_gt` | 主力净流入>value | value=0 | 资金流 |
| `main_net_lt` | 主力净流入<value | value=0 | 资金流 |

## 谁依赖它

- `engine.py`：`V.VERIFIERS.get(c.compute)` 按名取函数执行
- `learn/extract.py`：`VERIFIER_INFO` 生成提示词里的函数清单
- `main.py`：`/api/verifiers` 直接返回 `VERIFIER_INFO`

## 新增校验函数的标准步骤（改这个文件的常见场景）

1. 写 `v_xxx` 函数：参数从 `params.get(...)` 取并带默认值；
   数据异常抛 RuntimeError（不是返回 False）。
2. `VERIFIER_INFO` 加一行 `"xxx": ("功能说明", {"参数": 默认值})`。
3. `VERIFIERS` 加一行 `"xxx": v_xxx`。
4. 若需要新数据源，参考 `_kline_df`/`_chips`/`_flow_row` 写内部
   工具函数。
5. 跑 `scripts/selftest.py` 验证。

## 修改注意点

1. **三处必须同步**，缺一处表现为：前端看不到（缺 INFO）、
   引擎调不到（缺 VERIFIERS）、或压根没函数体。
2. **返回说明的格式串用 `%%` 转义**（`"%.2f%%"` 在 % 格式化下
   输出 `%`），改说明文字时别弄错转义。
3. 判定失败返回 `(False, 说明)`，**数据失败抛异常**——这是约定：
   引擎靠异常区分"不满足"和"没法判断（未验证）"。
4. `params` 是 dict，直接 `.get` 取值；引擎传进来的是 LLM 提炼
   或用户编辑的参数，可能缺字段，默认值要齐全。
