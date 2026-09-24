"""校验函数注册表：规则中 verify 条件的 compute 名 → 异步校验函数

【这个文件是干什么的】
"逐只验证"环节的执行器。学习产出的规则里除了自然语言查询条件
（交给东财），还有 verify 条件——需要拿每只股票的真实数据逐一判断
是否满足（如"90%筹码集中度<15%"）。每个校验函数就是一个可执行
的判断逻辑。

【组织方式（三层结构）】
1. 每个 v_xxx 函数：async fn(code: str, params: dict) -> tuple[bool, str]
   对单只股票做判断，返回 (是否满足, 人话说明)。
   数据拉取失败时抛异常（引擎捕获后标记为「未验证」）。
2. VERIFIER_INFO：校验函数说明目录（compute 名 → 功能说明+默认参数），
   学习管线提示词（extract.VERIFY_CATALOG）与 Web 编辑器
   （/api/verifiers 接口）都从它生成——改一处，三处同步。
3. VERIFIERS：真正的注册表（compute 名 → 函数），引擎按名调用。

【怎么新增一个校验函数（改这个文件的常见场景）】
1. 写 v_xxx 函数（参考现有写法，参数都从 params.get 取并带默认值）
2. 在 VERIFIER_INFO 里加一行说明（供学习/前端展示）
3. 在 VERIFIERS 里注册（供引擎调用）
三个地方缺一不可，否则前端看不到或引擎调不到。
"""
from __future__ import annotations

import pandas as pd

from . import eastmoney as em
from . import indicators as ind
from .astock_client import client as astock


async def _kline_df(code: str) -> pd.DataFrame:
    """取一只股票的K线并算好指标（内部工具函数，各指标类校验共用）

    拿到原始K线后，先用 indicators.kline_df 清洗成 DataFrame，
    再用 indicators.enrich 补齐 MA/MACD/KDJ/涨跌幅等指标列。
    数据异常（接口报错/K线为空）直接抛异常，由引擎统一处理。
    """
    j = await astock.get("kline", code=code, period="day", count=320)
    if j.get("error") or not j.get("klines"):
        raise RuntimeError(j.get("error") or "K线为空")
    return ind.enrich(ind.kline_df(j["klines"]))


async def _chips(code: str) -> dict:
    """取一只股票的筹码分布数据（内部工具函数，筹码类校验共用）"""
    j = await astock.get("chips", code=code, date="")
    if j.get("error"):
        raise RuntimeError(j["error"])
    return j


# ---------------- K线/指标类 ----------------
# 这一类都基于K线计算的技术指标：先拉K线（_kline_df），再调 indicators
# 里的纯函数判定。params 里的参数都带默认值，规则里可以不写。

async def v_macd_gold_cross(code, params):
    """MACD 金叉：近 lookback 根K线内 DIF 上穿 DEA"""
    df = await _kline_df(code)
    return ind.macd_gold_cross(df, int(params.get("lookback", 3)))


async def v_macd_dead_cross(code, params):
    """MACD 死叉：近 lookback 根K线内 DIF 下穿 DEA"""
    df = await _kline_df(code)
    return ind.macd_dead_cross(df, int(params.get("lookback", 3)))


async def v_ma_bull_alignment(code, params):
    """均线多头排列：MA5 > MA10 > MA20 > MA60"""
    df = await _kline_df(code)
    return ind.ma_bull_alignment(df)


async def v_ma_bear_alignment(code, params):
    """均线空头排列：MA5 < MA10 < MA20 < MA60"""
    df = await _kline_df(code)
    return ind.ma_bear_alignment(df)


async def v_price_above_ma(code, params):
    """收盘价站上 MA(n)（默认 n=20）"""
    df = await _kline_df(code)
    return ind.price_above_ma(df, int(params.get("n", 20)))


async def v_pct_gain_range(code, params):
    """近 days 日累计涨幅落在 [lo, hi] 区间（默认近5日、-100~100）"""
    df = await _kline_df(code)
    return ind.pct_gain_range(df, int(params.get("days", 5)),
                              float(params.get("lo", -100)), float(params.get("hi", 100)))


async def v_new_high_n_days(code, params):
    """收盘价创 n 日新高（默认 60 日）"""
    df = await _kline_df(code)
    return ind.new_high_n_days(df, int(params.get("n", 60)))


async def v_vol_shrink_break(code, params):
    """放量突破：当日量 > 前 shrink_n 日均量 * vol_mult 且收盘突破前 break_n 日高点"""
    df = await _kline_df(code)
    return ind.vol_shrink_break(df, int(params.get("shrink_n", 5)),
                                int(params.get("break_n", 20)),
                                float(params.get("vol_mult", 1.5)))


async def v_drop_from_high(code, params):
    """从高点回落：近 days 日内从最高点回落超过 pct%（默认 90 天回落 30%）"""
    df = await _kline_df(code)
    return ind.drop_from_high(df, int(params.get("days", 90)),
                              float(params.get("pct", 30)))


# ---------------- 筹码类 ----------------
# 筹码数据来自 astock /api/chips（通达信式三角分布）。
# 注意：字符串里的 %% 是转义，% 格式化后输出单个 %。

async def v_chips_concentration_lt(code, params):
    """90% 成本集中度低于 threshold（默认 15，集中度越低筹码越集中）"""
    c = await _chips(code)
    th = float(params.get("threshold", 15))
    val = float(c.get("c90_conc") or 999.0)  # 字段缺失按 999 处理 → 必然不满足
    if val < th:
        return True, "90%%筹码集中度%.2f%%<%.1f%%" % (val, th)
    return False, "90%%筹码集中度%.2f%%≥%.1f%%" % (val, th)


async def v_profit_ratio_lt(code, params):
    """获利盘比例低于 threshold（默认 30，越低套牢盘越多）"""
    c = await _chips(code)
    th = float(params.get("threshold", 30))
    val = float(c.get("profit_ratio") or -1.0)  # 字段缺失按 -1 → 必然"小于"
    if val < th:
        return True, "获利盘%.2f%%<%.1f%%" % (val, th)
    return False, "获利盘%.2f%%≥%.1f%%" % (val, th)


async def v_profit_ratio_gt(code, params):
    """获利盘比例高于 threshold（默认 70，越高抛压越重）"""
    c = await _chips(code)
    th = float(params.get("threshold", 70))
    val = float(c.get("profit_ratio") or -1.0)
    if val > th:
        return True, "获利盘%.2f%%>%.1f%%" % (val, th)
    return False, "获利盘%.2f%%≤%.1f%%" % (val, th)


async def v_avg_cost_near_price(code, params):
    """现价与筹码平均成本的偏差在 pct% 以内（默认 5%，用于判断是否接近主力成本区）"""
    c = await _chips(code)
    pct = float(params.get("pct", 5))
    close = float(c.get("close") or 0)
    avg = float(c.get("avg_cost") or 0)
    if not close or not avg:
        raise RuntimeError("筹码数据缺 close/avg_cost")
    diff = abs(close - avg) / avg * 100  # 偏差百分比
    if diff <= pct:
        return True, "现价距平均成本%.2f%%≤%.1f%%" % (diff, pct)
    return False, "现价距平均成本%.2f%%>%.1f%%" % (diff, pct)


# ---------------- 板块/资金类 ----------------
# 这一类需要东财数据：个股所属板块（eastmoney.stock_boards）+
# 热门榜/资金榜（astock 接口）。

async def v_in_hot_plate(code, params):
    """所属板块在热门概念榜前 top_n（默认前20，同花顺最强风口）"""
    boards = await em.stock_boards(code)               # 个股所属板块
    hot = await astock.get("fengkou")                  # 热门概念榜
    top = int(params.get("top_n", 20))
    # 取榜上前 top 个板块的名字组成集合，集合判断 in 比列表快
    hot_names = {r.get("name") for r in (hot.get("rows") or [])[:top]}
    mine = [b.get("name") for b in boards]
    hits = [n for n in mine if n in hot_names]         # 求个股板块与热门榜的交集
    if hits:
        return True, "所属板块「%s」在热门榜前%d" % ("/".join(hits[:3]), top)
    return False, "所属板块不在热门榜前%d（%s）" % (top, "/".join(mine[:5]) or "无板块信息")


async def v_in_plate_flow_top(code, params):
    """所属板块在板块主力资金榜前 n（默认前20，东财行业板块资金流）"""
    boards = await em.stock_boards(code)
    j = await astock.get("plate_flow")
    n = int(params.get("n", 20))
    top_names = [r.get("name") for r in (j.get("rows") or [])[:n]]
    mine = [b.get("name") for b in boards]
    hits = [x for x in mine if x in top_names]
    if hits:
        return True, "所属板块「%s」在主力资金榜前%d" % ("/".join(hits[:3]), n)
    return False, "所属板块不在主力资金榜前%d" % n


async def _flow_row(code) -> dict:
    """取一只股票的资金流行（内部工具函数，资金类校验共用）

    主力净流入字段缺失时抛异常 → 引擎标记「未验证」而不是误判。
    """
    rows = await em.stock_flow([code])
    if not rows:
        raise RuntimeError("资金流数据为空")
    r = rows[0]
    if r.get("main_net") in (None, "-"):
        raise RuntimeError("主力净流入字段缺失")
    return r


async def v_main_net_gt(code, params):
    """主力净流入大于 value（元，默认 0 = 净流入）"""
    r = await _flow_row(code)
    th = float(params.get("value", 0))
    v = float(r["main_net"])
    if v > th:
        return True, "主力净流入%s>%s" % (_fmt(v), _fmt(th))
    return False, "主力净流入%s≤%s" % (_fmt(v), _fmt(th))


async def v_main_net_lt(code, params):
    """主力净流入小于 value（元，默认 0 = 净流出）"""
    r = await _flow_row(code)
    th = float(params.get("value", 0))
    v = float(r["main_net"])
    if v < th:
        return True, "主力净流入%s<%s" % (_fmt(v), _fmt(th))
    return False, "主力净流入%s≥%s" % (_fmt(v), _fmt(th))


def _fmt(v: float) -> str:
    """把金额格式化成 亿/万/元（资金流数值很大，直接显示元不好读）"""
    a = abs(v)
    if a >= 1e8:                     # 1亿以上：显示"x.xx亿"
        return "%.2f亿" % (v / 1e8)
    if a >= 1e4:                     # 1万以上：显示"x.x万"
        return "%.1f万" % (v / 1e4)
    return "%.0f元" % v


# 校验函数说明目录：compute 名 → (功能说明, 默认参数)
# 学习管线提示词（extract.VERIFY_CATALOG）与 Web 编辑器（/api/verifiers）均从此生成
VERIFIER_INFO = {
    "macd_gold_cross": ("近N日内MACD金叉", {"lookback": 3}),
    "macd_dead_cross": ("近N日内MACD死叉", {"lookback": 3}),
    "ma_bull_alignment": ("均线多头排列(MA5>10>20>60)", {}),
    "ma_bear_alignment": ("均线空头排列", {}),
    "price_above_ma": ("收盘价站上MA(n)", {"n": 20}),
    "pct_gain_range": ("近days日累计涨幅在[lo,hi]区间", {"days": 5, "lo": -100, "hi": 100}),
    "new_high_n_days": ("收盘价创n日新高", {"n": 60}),
    "vol_shrink_break": ("放量突破前高", {"shrink_n": 5, "break_n": 20, "vol_mult": 1.5}),
    "drop_from_high": ("近N日内从最高点回落超过X%", {"days": 90, "pct": 30}),
    "profit_ratio_lt": ("获利盘比例低于threshold", {"threshold": 30}),
    "profit_ratio_gt": ("获利盘比例高于threshold", {"threshold": 70}),
    "avg_cost_near_price": ("现价与平均成本差距在pct%以内", {"pct": 5}),
    "in_hot_plate": ("所属板块在热门概念榜前top_n", {"top_n": 20}),
    "in_plate_flow_top": ("所属板块在板块主力资金榜前n", {"n": 20}),
    "main_net_gt": ("主力净流入大于value(元)", {"value": 0}),
    "main_net_lt": ("主力净流入小于value(元)", {"value": 0}),
}


# 注册表：compute 名 → 函数
VERIFIERS = {
    "macd_gold_cross": v_macd_gold_cross,
    "macd_dead_cross": v_macd_dead_cross,
    "ma_bull_alignment": v_ma_bull_alignment,
    "ma_bear_alignment": v_ma_bear_alignment,
    "price_above_ma": v_price_above_ma,
    "pct_gain_range": v_pct_gain_range,
    "new_high_n_days": v_new_high_n_days,
    "vol_shrink_break": v_vol_shrink_break,
    "drop_from_high": v_drop_from_high,
    "chips_concentration_lt": v_chips_concentration_lt,
    "profit_ratio_lt": v_profit_ratio_lt,
    "profit_ratio_gt": v_profit_ratio_gt,
    "avg_cost_near_price": v_avg_cost_near_price,
    "in_hot_plate": v_in_hot_plate,
    "in_plate_flow_top": v_in_plate_flow_top,
    "main_net_gt": v_main_net_gt,
    "main_net_lt": v_main_net_lt,
}
