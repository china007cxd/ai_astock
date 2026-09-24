"""运行引擎（LangGraph 状态机）

【这个文件是干什么的】
选股运行的核心流程编排。把"读规则 → 分条查询 → 取交集 → 逐只验证
→ 生成说明 → 存档"串成一个自动流程。前端点"运行"后，后台任务最终
就是调这里。

流程：load_rule → query_conditions（并行执行所有 query 条件）
     → intersect（分条查询取交集）→ verify_conditions（逐只验证）
     → summarize（LLM 生成命中说明，失败用模板）→ 存档

设计原则：确定性执行（查询语句来自规则，不现场生成），LLM 只用于结果解读。
—— 这意味着选股结果可复现、可调试；LLM 不会"自由发挥"影响选股本身，
只是给结果写一句人话说明，失败了也有模板兜底。

【给小白的关键概念】
- LangGraph 状态机：把流程画成一张"图"，每个节点是一个步骤
  （load_rule/query_conditions/...），边定义执行顺序。ainvoke 时
  按图自动执行。本流程是直线型的，只有 intersect 之后有个分支：
  交集为空 → 直接结束；非空 → 继续验证。
- TypedDict 状态：EngineState 定义状态里有哪些字段（rule/candidates/
  stocks...），节点返回的 dict 会合并进状态，下一步就能读到上一步的产出。
- asyncio.gather：并行执行多个 async 任务（分条查询并行、逐只验证并行），
  选股要查几十上百只股票，并行能快一个数量级。
- Semaphore（信号量）：并发"限流闸门"。_VERIFY_SEM(8) 表示同时最多
  8 个验证请求，避免把 astock 打爆。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from . import storage
from . import verifiers as V
from .astock_client import client as astock
from .llm import has_llm, chat_json
from .models import (ConditionResult, Rule, RunResult, StockHit, StockResult)
from .tools import em_xuangu

# 验证并发上限（避免打爆 astock）
_VERIFY_SEM = asyncio.Semaphore(8)


class EngineState(TypedDict, total=False):
    """引擎状态（在图的各节点之间传递数据）

    total=False 表示字段都是可选的：节点没填的字段就当不存在。
    各字段会在对应节点产生、被后续节点消费：
      rule → load_rule 校验
      condition_results → query_conditions 产出、intersect/verify 消费
      candidates → intersect 产出（交集后的候选股）
      stocks → verify_conditions 产出（带验证标签）、summarize 消费
    """
    mode_id: str
    rule: dict
    condition_results: list[dict]
    candidates: list[dict]
    empty_reason: str
    stocks: list[dict]
    error: str


def _fallback_note(s: dict) -> str:
    """LLM 不可用/失败时的兜底说明模板（保证结果页每只股票都有说明）"""
    if s["matched"]:
        return "命中%d项条件：%s" % (len(s["matched"]), "；".join(s["matched"][:3]))
    return "未命中关键条件"


class Engine:
    """运行引擎：一次实例化一个图，可反复 run

    用法：
        engine = Engine(progress=回调)   # 回调接进度日志（写进 jobs）
        result = await engine.run(mode_id)
    """

    def __init__(self, progress: Callable[[str], None] | None = None):
        # progress 回调：每走一步就报告一句进度，由调用方（main._run_job）
        # 接到 jobs.log 里，前端轮询就能看到实时日志
        self.progress = progress or (lambda s: None)
        self.graph = self._build()

    # ---------- 图构建 ----------

    def _build(self):
        """搭建 LangGraph 流程（编译成可执行的图）

        边（执行顺序）：
          START → load_rule → query_conditions → intersect
                → （有候选？verify_conditions : END）
                → summarize → END
        """
        g = StateGraph(EngineState)
        g.add_node("load_rule", self.load_rule)
        g.add_node("query_conditions", self.query_conditions)
        g.add_node("intersect", self.intersect)
        g.add_node("verify_conditions", self.verify_conditions)
        g.add_node("summarize", self.summarize)
        g.add_edge(START, "load_rule")
        g.add_edge("load_rule", "query_conditions")
        g.add_edge("query_conditions", "intersect")
        # 条件边：intersect 之后看 _after_intersect 的返回值决定走哪条路
        g.add_conditional_edges(
            "intersect", self._after_intersect,
            {"verify": "verify_conditions", "end": END})
        g.add_edge("verify_conditions", "summarize")
        g.add_edge("summarize", END)
        return g.compile()

    def _after_intersect(self, state: EngineState) -> str:
        """intersect 的分支判断：交集为空 → "end" 直接结束；否则 → "verify" 继续验证"""
        return "end" if state.get("empty_reason") else "verify"

    # ---------- 节点 ----------

    async def load_rule(self, state: EngineState) -> dict:
        """节点1：加载并校验规则（数据已在 state["rule"] 里，这里做一次 Pydantic 校验）"""
        rule = Rule.model_validate(state["rule"])
        self.progress("加载规则《%s》" % rule.name)
        return {}

    async def query_conditions(self, state: EngineState) -> dict:
        """节点2：并行执行所有 query 条件（东财智能选股自然语言查询）

        每个条件单独查一次（"分条查询"），结果互不干扰；
        查询失败的条件标记 ok=False，不影响其他条件。
        """
        rule = Rule.model_validate(state["rule"])
        qconds = [c for c in rule.conditions if c.type == "query"]
        if not qconds:
            return {"condition_results": []}
        self.progress("执行 %d 条查询条件（东财智能选股）..." % len(qconds))

        async def one(c):
            """单条查询的执行体（内部函数，交给 gather 并行跑）"""
            try:
                # ainvoke 是 LangChain 工具的异步调用方式，参数是 dict
                j = await em_xuangu.ainvoke({"query": c.query, "size": 100})
            except Exception as e:
                return ConditionResult(condition_id=c.id, text=c.text,
                                       ok=False, error=str(e)).model_dump()
            rows = j.get("rows") or []
            # 每行 → StockHit，extra 只保留有值的字段（price/pct/reason/...）
            hits = [
                StockHit(code=r.get("code") or "", name=r.get("name") or "",
                         extra={k: r.get(k) for k in
                                ("price", "pct", "reason", "days", "turnover")
                                if r.get(k) is not None}).model_dump()
                for r in rows if r.get("code")]
            self.progress("条件「%s」命中 %d 只" % (c.text, len(hits)))
            return ConditionResult(condition_id=c.id, text=c.text, hits=hits,
                                   total=len(hits), ok=True).model_dump()

        # gather：并行执行所有条件的 one()，全部完成后一起返回
        results = list(await asyncio.gather(*[one(c) for c in qconds]))
        return {"condition_results": results}

    async def intersect(self, state: EngineState) -> dict:
        """节点3：对分条查询结果取交集（或并集）得到候选池

        交集 = 同时出现在所有查询条件结果里的股票（方案确认的用法）；
        union 是预留扩展位。
        """
        rule = Rule.model_validate(state["rule"])
        results = state.get("condition_results") or []
        # 只统计执行成功的条件；失败的既不算也不拦（至少一条成功才能继续）
        ok_results = [r for r in results if r.get("ok")]
        if not ok_results:
            return {"empty_reason": "所有查询条件均执行失败，请检查 astock 服务是否正常"}
        # 每个条件的命中代码集合，做集合运算
        sets = [{h["code"] for h in r["hits"]} for r in ok_results]
        if rule.combine == "union":
            common = set.union(*sets)
        else:
            common = set.intersection(*sets)
        # hit_map：代码 → 命中记录（取交集后还能找回股票的名称/价格等信息）
        hit_map: dict[str, dict] = {}
        for r in ok_results:
            for h in r["hits"]:
                hit_map.setdefault(h["code"], h)
        candidates = [hit_map[c] for c in sorted(common)]
        if not candidates:
            # 交集为空：给用户一个可操作的提示（附各条件命中数，便于判断放宽哪条）
            counts = "，".join("「%s」命中%d只" % (r["text"], len(r["hits"]))
                               for r in ok_results)
            msg = ("各条件交集为空（%s）。说明当前市场没有同时满足所有条件的股票，"
                   "可考虑在学习确认页放宽或调整某条条件。" % counts)
            self.progress(msg)
            return {"candidates": [], "empty_reason": msg}
        self.progress("取交集后候选 %d 只" % len(candidates))
        return {"candidates": candidates}

    async def verify_conditions(self, state: EngineState) -> dict:
        """节点4：对候选池逐只执行 verify 条件（数据工具验证）

        每只股票、每个验证条件调用一次 verifiers 里的函数，结果分三类：
        matched（通过）/ failed（未通过）/ unverified（数据拉取失败）。
        最后补充实时行情（现价/涨跌幅）。
        """
        rule = Rule.model_validate(state["rule"])
        vconds = [c for c in rule.conditions if c.type == "verify"]
        candidates = state.get("candidates") or []
        # 先把候选池转成 {代码: StockResult} 字典，方便后续按代码打标签
        stocks = {c["code"]: StockResult(code=c["code"],
                                         name=c["name"]).model_dump()
                  for c in candidates}
        # 查询条件命中说明：在交集里的股票，给每个命中它的查询条件打上标签
        for r in state.get("condition_results") or []:
            for h in r["hits"]:
                if h["code"] in stocks:
                    stocks[h["code"]]["matched"].append("%s（查询命中）" % r["text"])

        for c in vconds:
            fn = V.VERIFIERS.get(c.compute)
            if fn is None:
                # 规则里写了个不存在的函数名（可能手改过）：跳过并打"未验证"标签
                self.progress("验证函数 %s 未实现，条件「%s」跳过" % (c.compute, c.text))
                for s in stocks.values():
                    s["unverified"].append("%s（函数未实现:%s）" % (c.text, c.compute))
                continue
            self.progress("验证「%s」(%d 只)..." % (c.text, len(candidates)))

            async def one(code):
                """单只股票的验证体：信号量限流 + 异常转「未验证」"""
                async with _VERIFY_SEM:  # 同时最多8个并发
                    try:
                        passed, detail = await fn(code, c.params)
                        return code, passed, detail
                    except Exception as e:  # noqa —— 数据失败=未验证，不中断整体
                        return code, None, str(e)

            results = await asyncio.gather(*[one(cd["code"]) for cd in candidates])
            # 按结果给每只股票打标签（True→命中 / False→未通过 / None→未验证）
            for code, passed, detail in results:
                s = stocks[code]
                if passed is True:
                    s["matched"].append("%s：%s" % (c.text, detail))
                elif passed is False:
                    s["failed"].append("%s：%s" % (c.text, detail))
                else:
                    s["unverified"].append("%s（验证失败：%s）" % (c.text, detail))

        # 补充实时行情（最多60只，quotes 接口的批次上限）
        codes = list(stocks.keys())[:60]
        if codes:
            try:
                qj = await astock.get("quotes", codes=",".join(codes))
                for r in qj.get("rows") or []:
                    if r.get("code") in stocks:
                        stocks[r["code"]]["price"] = str(r.get("price") or "-")
                        stocks[r["code"]]["pct"] = str(r.get("pct") or "-")
            except Exception:
                pass  # 行情拿不到不致命：结果照常，价格显示 "-"
        return {"stocks": list(stocks.values())}

    async def summarize(self, state: EngineState) -> dict:
        """节点5：为每只股票生成一句话命中说明

        优先用 LLM 生成；LLM 没配/失败时降级为模板说明（_fallback_note）。
        保证结果页始终有说明可看。
        """
        stocks = state.get("stocks") or []
        if not stocks:
            return {"stocks": stocks}
        if has_llm():
            try:
                notes = self._llm_notes(stocks)
                for s in stocks:
                    # LLM 没给这只股票写说明时，用模板兜底
                    s["note"] = notes.get(s["code"], "") or _fallback_note(s)
            except Exception as e:  # noqa
                self.progress("LLM 说明生成失败，改用模板说明: %s" % e)
                for s in stocks:
                    s["note"] = _fallback_note(s)
        else:
            for s in stocks:
                s["note"] = _fallback_note(s)
        return {"stocks": stocks}

    @staticmethod
    def _llm_notes(stocks: list[dict]) -> dict:
        """让 LLM 为所有股票批量写说明（一次调用，省 token）

        输入每只股票的命中/未通过情况，要求输出
        {"notes": {"股票代码": "说明"}} 格式的 JSON。
        """
        lines = []
        for s in stocks:
            lines.append("- %s %s（现价%s，涨跌%s%%）：命中条件[%s]；未通过[%s]"
                         % (s["code"], s["name"], s["price"], s["pct"],
                            "；".join(s["matched"]) or "无",
                            "；".join(s["failed"]) or "无"))
        prompt = ("以下是某选股模式下命中的股票及其条件命中情况。请为每只股票写一句"
                  "20字内的命中说明（突出关键条件），输出 JSON："
                  '{"notes": {"股票代码": "说明"}}\n\n%s' % "\n".join(lines))
        j = chat_json(prompt)
        return j.get("notes") if isinstance(j, dict) else {}

    # ---------- 入口 ----------

    async def run(self, mode_id: str) -> RunResult:
        """对外入口：运行一次完整选股

        流程：读规则 → 跑图 → 组装 RunResult → 存档 runs/{run_id}.json。
        任何异常都转为 status="failed" 的结果存档（历史页可查失败原因），
        而不是抛给上层。
        """
        rule = storage.load_rule(mode_id)
        if rule is None:
            raise ValueError(
                "模式《%s》尚未学习出规则：请先在「模式管理」点学习，再到「学习确认」确认保存" % mode_id)
        # run_id = 日期_时分秒_随机串，唯一且可排序
        run_id = "%s_%s" % (time.strftime("%Y%m%d_%H%M%S"), uuid.uuid4().hex[:6])
        self.progress("开始运行模式《%s》" % rule.name)
        try:
            # ainvoke：异步执行整张图，输入初始状态，输出最终状态
            state = await self.graph.ainvoke(
                {"mode_id": mode_id, "rule": rule.model_dump()})
        except Exception as e:  # noqa
            run = RunResult(run_id=run_id, mode_id=mode_id, mode_name=rule.name,
                            time=time.strftime("%Y-%m-%d %H:%M:%S"),
                            status="failed", rule=rule, error=str(e))
            storage.save_run(run)
            self.progress("运行失败: %s" % e)
            return run

        # 图输出的是 dict 列表，转回 Pydantic 对象（带校验）
        stocks = [StockResult.model_validate(s) for s in state.get("stocks", [])]
        crs = [ConditionResult.model_validate(r)
               for r in state.get("condition_results", [])]
        run = RunResult(run_id=run_id, mode_id=mode_id, mode_name=rule.name,
                        time=time.strftime("%Y-%m-%d %H:%M:%S"),
                        status="done", rule=rule, condition_results=crs,
                        stocks=stocks, empty_reason=state.get("empty_reason", ""))
        storage.save_run(run)
        self.progress("运行完成：命中 %d 只，已存档 runs/%s.json" % (len(stocks), run_id))
        return run
