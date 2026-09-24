"""工具层自检：逐一跑通 astock 接口 + 东财直连（需先启动 astock/启动.bat）

用法：uv run python scripts/selftest.py
"""
import asyncio
import sys

from astock_agent.astock_client import client
from astock_agent import tools


def brief(name: str, r) -> str:
    if isinstance(r, dict):
        if r.get("error"):
            return "WARN %s" % r["error"]
        if "rows" in r:
            return "rows=%d" % len(r.get("rows") or [])
        if "klines" in r:
            return "klines=%d" % len(r.get("klines") or [])
        if "avg_cost" in r:
            return "avg_cost=%s c90_conc=%s profit=%s%%" % (
                r["avg_cost"], r.get("c90_conc"), r.get("profit_ratio"))
    if isinstance(r, list):
        return "rows=%d %s" % (len(r), (r[:1] or [{}])[0].get("name", ""))
    return str(r)[:60]


async def main() -> int:
    ok = await client.health()
    print("[ 1/10] astock 连通性      : %s" % ("PASS" if ok else "FAIL（请先启动 astock/启动.bat）"))
    if not ok:
        return 1

    cases = [
        ("东财智能选股", tools.em_xuangu, {"query": "MACD金叉", "size": 10}),
        ("问财本地匹配", tools.wencai, {"query": "涨停 半导体", "size": 10}),
        ("K线(000001)   ", tools.get_kline, {"code": "000001", "count": 100}),
        ("筹码(000001)   ", tools.get_chips, {"code": "000001"}),
        ("热门概念板块   ", tools.get_hot_plates, {}),
        ("板块资金流     ", tools.get_plate_flow, {}),
        ("批量行情       ", tools.get_quotes, {"codes": "000001,600519"}),
        ("个股所属板块   ", tools.get_stock_boards, {"code": "600519"}),
        ("个股资金流     ", tools.get_stock_flow, {"codes": ["600519", "000001"]}),
    ]
    fails = 0
    for i, (name, t, args) in enumerate(cases, 2):
        try:
            r = await t.ainvoke(args)
            print("[%2d/10] %s: %s" % (i, name, brief(name, r)))
        except Exception as e:
            fails += 1
            print("[%2d/10] %s: FAIL %s" % (i, name, e))

    # 指标计算自检
    try:
        import pandas as pd
        from astock_agent import indicators as ind
        df = pd.DataFrame([
            {"date": "2026-08-17", "open": 10, "close": 10.5, "high": 10.6, "low": 9.9, "volume": 1000},
            {"date": "2026-08-18", "open": 10.5, "close": 11.0, "high": 11.2, "low": 10.4, "volume": 1200},
            {"date": "2026-08-19", "open": 11.0, "close": 11.5, "high": 11.6, "low": 10.9, "volume": 1500},
        ] * 30)
        df = ind.enrich(df)
        ok_macd, msg = ind.macd_gold_cross(df, lookback=3)
        print("[10/10] 指标计算        : %s (样本MACD金叉=%s, %s)" % (
            "PASS" if df is not None else "FAIL", ok_macd, msg))
    except Exception as e:
        fails += 1
        print("[10/10] 指标计算        : FAIL %s" % e)

    print("\n结果: %s" % ("全部通过" if fails == 0 else "存在 %d 项失败" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
