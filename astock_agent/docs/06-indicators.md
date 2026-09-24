# 06-indicators：技术指标计算（`src/astock_agent/indicators.py`）

## 职责

技术指标的"数学计算层"。纯函数、无 IO（不碰网络/文件），
测试方便、执行快。verifiers 的指标类校验全部基于这里的函数。

## 函数清单

### 指标计算（给 DataFrame 加列）

| 函数 | 产出列 |
|---|---|
| `kline_df(klines)` | 干净的 DataFrame（数字列转数值、丢坏行） |
| `sma(s, n)` / `ema(s, n)` | 简单/指数移动平均 Series |
| `add_ma(df)` | `ma5/ma10/ma20/ma60` |
| `add_macd(df)` | `dif/dea/macd`（柱为2倍，国内软件惯例） |
| `add_kdj(df)` | `k/d/j`（alpha=1/3 国标平滑） |
| `enrich(df)` | 上面全部 + `pct`（涨跌幅）/`vol_ratio_5`（量比）/`high20`/`low20` |

### 形态判定（统一返回 `(是否满足, 人话说明)`）

| 函数 | 判定内容 | 关键参数 |
|---|---|---|
| `macd_gold_cross` | 近N日 MACD 金叉 | lookback=3 |
| `macd_dead_cross` | 近N日 MACD 死叉 | lookback=3 |
| `ma_bull_alignment` | 多头排列 5>10>20>60 | - |
| `ma_bear_alignment` | 空头排列 | - |
| `price_above_ma` | 收盘价站上 MA(n) | n=20 |
| `pct_gain_range` | 近days日涨幅∈[lo,hi] | days=5, lo=-100, hi=100 |
| `new_high_n_days` | 收盘创n日新高 | n=60 |
| `vol_shrink_break` | 放量突破前高（量价配合） | shrink_n=5, break_n=20, vol_mult=1.5 |

## 关键约定

1. **判定函数不抛异常**：数据不足返回 `(False, "数据不足...")`。
   批量验证时一只股票失败不拖累其他。
2. **返回说明带数值**：如 `"收盘价在MA20上方(5.32>5.10)"`，
   前端直接展示，用户可核对。
3. **`enrich` 是标准预处理入口**：原始K线 → `kline_df` → `enrich`
   → 判定函数。verifiers._kline_df 就按这个顺序。

## 谁依赖它

- `verifiers.py`：所有 K线/指标类校验
- `scripts/` 的测试脚本

## 修改注意点

1. **新增判定函数**后要同步在 `verifiers.py` 加 `v_xxx` 包装 + 注册
   （三处注册约定见 08-verifiers）。
2. **MACD 柱乘 2**、**KDJ 用 alpha=1/3** 是刻意对齐国内行情软件显示，
   改成标准公式会导致和用户屏幕上的软件读数不一致。
3. 判定只看"最近N根K线"（`df.tail()`），性能考虑：320 根K线
   足够算 MA60，别把 count 改小。
