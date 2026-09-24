"""技术指标计算（pandas/numpy 纯函数，无 IO）

【这个文件是干什么的】
技术指标的"数学计算层"。输入 K 线数据，输出 MA/MACD/KDJ 等指标，
并提供各种形态判定函数（金叉/多头排列/新高/放量突破等）。
本文件不碰网络、不读文件（无 IO），是纯计算，测试方便、执行快。

【给小白的关键概念】
- pandas DataFrame：像 Excel 表格一样的数据结构，一列一个指标。
  df["close"] 是收盘价那一列；df.iloc[-1] 是最后一行（最新一天）。
- Series：DataFrame 的一列。rolling(n).mean() 就是"往前数 n 天求平均"
  ——移动平均线就是这么算的。ewm(span=n) 是指数加权（EMA）。
- 判定函数约定：统一返回 (bool, str) 元组——是否满足 + 人话说明。
  这样引擎和前端展示都能直接用，说明里带上具体数值方便用户核对。
- 数据不足的处理：不够算指标时返回 (False, "数据不足...") 而不是
  报错，保证批量验证时一只股票失败不影响其他股票。

K线输入格式与 astock /api/kline 一致（前复权日K）：
[{"date","open","close","high","low","volume","amplitude","turnover"}]
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def kline_df(klines: list[dict]) -> pd.DataFrame:
    """K线 dict 列表 → 干净的 DataFrame

    做三件事：转 DataFrame、把数字列强制转数值（接口偶尔返回字符串）、
    丢掉收盘价为空的坏行。
    """
    df = pd.DataFrame(klines)
    if df.empty:
        return df
    for col in ("open", "close", "high", "low", "volume"):
        # errors="coerce"：转不动的值变成 NaN（而不是报错），后面统一处理
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"]).reset_index(drop=True)
    return df


def sma(s: pd.Series, n: int) -> pd.Series:
    """简单移动平均（MA）：最近 n 天收盘价的算术平均。不足 n 天为 NaN"""
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """指数移动平均（EMA）：越近的价权重越大，比 SMA 反应更快。adjust=False 是业界惯例"""
    return s.ewm(span=n, adjust=False).mean()


def add_ma(df: pd.DataFrame, windows=(5, 10, 20, 60)) -> pd.DataFrame:
    """给 DataFrame 增加 ma5/ma10/ma20/ma60 四列（常用均线）"""
    for w in windows:
        df["ma%d" % w] = sma(df["close"], w)
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """增加 DIF/DEA/MACD柱 三列（柱为2倍，与中国股市软件显示一致）

    MACD 公式：
      DIF = EMA12 - EMA26（快线-慢线）
      DEA = DIF 的 9 日 EMA（信号线）
      MACD柱 = (DIF - DEA) * 2（国内软件惯例乘2）
    """
    dif = ema(df["close"], 12) - ema(df["close"], 26)
    dea = dif.ewm(span=9, adjust=False).mean()
    df["dif"] = dif
    df["dea"] = dea
    df["macd"] = (dif - dea) * 2
    return df


def add_kdj(df: pd.DataFrame, n: int = 9) -> pd.DataFrame:
    """增加 K/D/J 三列（随机指标，反映超买超卖）

    公式：RSV = (收盘 - 9日最低) / (9日最高 - 9日最低) * 100，
    K/D 是 RSV 的平滑（alpha=1/3 是国标），J = 3K - 2D。
    """
    low_n = df["low"].rolling(n, min_periods=1).min()
    high_n = df["high"].rolling(n, min_periods=1).max()
    # 最高=最低（一字板）时除以0会出 inf，替换成 NaN，后面统一填50
    span = (high_n - low_n).replace(0, np.nan)
    rsv = ((df["close"] - low_n) / span * 100).fillna(50.0)
    df["k"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    df["d"] = df["k"].ewm(alpha=1 / 3, adjust=False).mean()
    df["j"] = 3 * df["k"] - 2 * df["d"]
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """补齐常用指标列：MA/MACD/KDJ/涨跌幅/量比/前N日高低点

    这是验证函数的标准预处理入口：原始K线 → enrich → 各判定函数。
    .pipe(f) 就是 f(df) 的链式写法，读起来顺。
    """
    if df.empty or len(df) < 2:
        return df
    df = add_ma(df).pipe(add_macd).pipe(add_kdj)
    df["pct"] = df["close"].pct_change() * 100          # 当日涨跌幅%
    df["vol_ma5"] = sma(df["volume"], 5)                # 5日均量
    df["vol_ratio_5"] = df["volume"] / df["vol_ma5"].replace(0, np.nan)  # 量比
    df["high20"] = df["high"].rolling(20, min_periods=1).max()   # 前20日最高
    df["low20"] = df["low"].rolling(20, min_periods=1).min()     # 前20日最低
    return df


# ---------- 判定函数：输入 enriched df，返回 (是否满足, 说明) ----------
# 约定：数据不足返回 (False, "数据不足...")，不抛异常。
# 判定只看最近几根K线，用 df.tail(k) 取尾部加速。

def macd_gold_cross(df: pd.DataFrame, lookback: int = 3) -> tuple[bool, str]:
    """近 lookback 根K线内出现 MACD 金叉（DIF 上穿 DEA）

    金叉定义：前一天 DIF <= DEA 且当天 DIF > DEA（上穿瞬间）。
    只检查最近 lookback+1 根，而不是全历史。
    """
    if df.empty or df["dea"].isna().all():
        return False, "数据不足"
    sub = df.tail(lookback + 1)
    dif, dea = sub["dif"].values, sub["dea"].values
    for i in range(1, len(sub)):
        # dea[i] 必须有效（前一日 DIF 允许为 NaN 时照样判断）
        if not np.isnan(dea[i]) and dif[i - 1] <= dea[i - 1] and dif[i] > dea[i]:
            return True, "近%d日内MACD金叉(%s)" % (lookback, sub["date"].iloc[i])
    return False, "近%d日内无MACD金叉" % lookback


def macd_dead_cross(df: pd.DataFrame, lookback: int = 3) -> tuple[bool, str]:
    """近 lookback 根K线内出现 MACD 死叉（DIF 下穿 DEA，金叉的镜像）"""
    if df.empty or df["dea"].isna().all():
        return False, "数据不足"
    sub = df.tail(lookback + 1)
    dif, dea = sub["dif"].values, sub["dea"].values
    for i in range(1, len(sub)):
        if not np.isnan(dea[i]) and dif[i - 1] >= dea[i - 1] and dif[i] < dea[i]:
            return True, "近%d日内MACD死叉(%s)" % (lookback, sub["date"].iloc[i])
    return False, "近%d日内无MACD死叉" % lookback


def ma_bull_alignment(df: pd.DataFrame) -> tuple[bool, str]:
    """均线多头排列 MA5>MA10>MA20>MA60（只看最新一天）"""
    if len(df) < 60:
        return False, "数据不足60根"
    r = df.iloc[-1]
    if pd.isna(r.get("ma60")):
        return False, "MA60 未成形"
    # Python 支持链式比较：a > b > c > d 等价于 a>b 且 b>c 且 c>d
    if r["ma5"] > r["ma10"] > r["ma20"] > r["ma60"]:
        return True, "均线多头排列(5>10>20>60)"
    return False, "均线未多头排列"


def ma_bear_alignment(df: pd.DataFrame) -> tuple[bool, str]:
    """均线空头排列 MA5<MA10<MA20<MA60（多头排列的镜像，弱势形态）"""
    if len(df) < 60:
        return False, "数据不足60根"
    r = df.iloc[-1]
    if pd.isna(r.get("ma60")):
        return False, "MA60 未成形"
    if r["ma5"] < r["ma10"] < r["ma20"] < r["ma60"]:
        return True, "均线空头排列(5<10<20<60)"
    return False, "均线未空头排列"


def price_above_ma(df: pd.DataFrame, n: int = 20) -> tuple[bool, str]:
    """收盘价站上 MA(n)（默认20日线，强势标志）"""
    if df.empty or len(df) < n:
        return False, "数据不足%d根" % n
    r = df.iloc[-1]
    ma = r.get("ma%d" % n)
    if pd.isna(ma):
        return False, "MA%d 未成形" % n
    if r["close"] > ma:
        return True, "收盘价在MA%d上方(%.2f>%.2f)" % (n, r["close"], ma)
    return False, "收盘价在MA%d下方(%.2f<%.2f)" % (n, r["close"], ma)


def pct_gain_range(df: pd.DataFrame, days: int = 5, lo: float = -100, hi: float = 100) -> tuple[bool, str]:
    """近 days 个交易日累计涨幅在 [lo, hi] 区间（闭区间，含端点）"""
    if len(df) < days + 1:
        return False, "数据不足%d日" % (days + 1)
    # 累计涨幅 = 最新收盘 / days 天前收盘 - 1（需要 days+1 根K线）
    gain = (df["close"].iloc[-1] / df["close"].iloc[-1 - days] - 1) * 100
    if lo <= gain <= hi:
        return True, "近%d日涨幅%.2f%%∈[%.1f,%.1f]" % (days, gain, lo, hi)
    return False, "近%d日涨幅%.2f%%超出[%.1f,%.1f]" % (days, gain, lo, hi)


def new_high_n_days(df: pd.DataFrame, n: int = 60) -> tuple[bool, str]:
    """收盘价创 n 日新高（收盘价 > 此前 n 日的最高价）"""
    if len(df) < n:
        return False, "数据不足%d根" % n
    r = df.iloc[-1]
    # iloc[-n:-1]：取最近 n 天里"除今天外"的最高价
    prev_high = df["high"].iloc[-n:-1].max()
    if r["close"] > prev_high:
        return True, "收盘价创%d日新高(%.2f)" % (n, r["close"])
    return False, "未创%d日新高" % n


def vol_shrink_break(df: pd.DataFrame, shrink_n: int = 5, break_n: int = 20,
                     vol_mult: float = 1.5) -> tuple[bool, str]:
    """放量突破：当日量>前 shrink_n 日均量*vol_mult 且收盘价突破前 break_n 日最高价

    两个条件必须同时满足（量价配合的突破才可靠）：
    1. 放量：今天成交量 > 前 shrink_n 天均量 × vol_mult
    2. 突破：今天收盘价 > 前 break_n 天最高价
    """
    if len(df) < max(shrink_n, break_n) + 1:
        return False, "数据不足"
    r = df.iloc[-1]
    vol_ma = df["volume"].iloc[-1 - shrink_n:-1].mean()   # 前 shrink_n 天均量
    prev_high = df["high"].iloc[-1 - break_n:-1].max()    # 前 break_n 天最高价
    vol_ok = r["volume"] > vol_ma * vol_mult
    price_ok = r["close"] > prev_high
    if vol_ok and price_ok:
        return True, "放量突破前%d日高点(量%.0f%%)" % (
            break_n, r["volume"] / vol_ma * 100 if vol_ma else 0)
    if not vol_ok:
        return False, "未放量(量比5日%.1fx)" % (r["volume"] / vol_ma if vol_ma else 0)
    return False, "未突破前%d日高点" % break_n


def drop_from_high(df: pd.DataFrame, days: int = 90, pct: float = 30) -> tuple[bool, str]:
    """近 days 日内从最高点回落超过 pct%（超跌反弹模式的验证条件）

    计算方式：取近 days 日内的最高价，与当前收盘价比较，
    如果 (最高价 - 收盘价) / 最高价 * 100 >= pct，则满足。

    典型用法：days=90, pct=30 表示"3个月内从最高点跌超30%"。
    数据不足时返回 (False, "数据不足")。
    """
    if df.empty or len(df) < 2:
        return False, "数据不足"
    sub = df.tail(days)
    high = sub["high"].max()
    close = df["close"].iloc[-1]
    if pd.isna(high) or pd.isna(close):
        return False, "数据不足"
    drop = (high - close) / high * 100
    if drop >= pct:
        return True, "近%d日内从最高%.2f回落%.2f%%≥%.0f%%" % (days, high, drop, pct)
    return False, "近%d日内从最高%.2f回落%.2f%%<%.0f%%" % (days, high, drop, pct)
