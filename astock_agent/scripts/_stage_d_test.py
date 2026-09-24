# 阶段D自检：真实跑一次完整选股流程（查询→交集→验证→结果）
import asyncio

from astock_agent import storage
from astock_agent.engine import Engine
from astock_agent.models import Rule, QueryCondition, VerifyCondition

mid = "_引擎测试_删除我"
storage.create_mode(mid)
rule = Rule(
    mode_id=mid, name="引擎测试模式",
    description="MACD金叉 + 主力净流入 + 站上20日线 + 获利盘过半",
    conditions=[
        QueryCondition(id="c1", text="日线MACD金叉", query="MACD金叉"),
        QueryCondition(id="c2", text="主力净流入为正", query="主力净流入大于0"),
        VerifyCondition(id="c3", text="收盘价站上MA20", compute="price_above_ma",
                        params={"n": 20}),
        VerifyCondition(id="c4", text="获利盘过半", compute="profit_ratio_gt",
                        params={"threshold": 50}),
    ],
)
storage.save_rule(rule)


async def main():
    eng = Engine(progress=lambda s: print("[eng]", s))
    run = await eng.run(mid)
    print("\n=== 运行结果（%s）===" % run.status)
    for r in run.condition_results:
        print("  条件「%s」: %s 命中%d只" % (r.text, "OK" if r.ok else "FAIL:" + r.error, len(r.hits)))
    print("  最终候选 %d 只：" % len(run.stocks))
    for s in run.stocks[:10]:
        print("   %s %s 现价%s 涨跌%s%%" % (s.code, s.name, s.price, s.pct))
        for m in s.matched:
            print("       + 命中:", m)
        for f in s.failed:
            print("       - 未过:", f)
        for u in s.unverified:
            print("       ? 未验:", u)
        print("       说明:", s.note)


if __name__ == "__main__":
    asyncio.run(main())
