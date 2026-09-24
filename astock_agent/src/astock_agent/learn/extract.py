"""规则提炼：多案例材料（说明.md + 截图解读）→ 文本模型 → 规则草案

【这个文件是干什么的】
学习管线的第二步：把某个模式下所有案例的文字说明和截图解读打包成
提示词，让文本模型归纳出一套可执行的选股规则草案（哪几条查询条件 +
哪几条验证条件），供人在"学习确认"页审核修改。

【给小白的关键概念】
- 提示词拼接：build_prompt 把案例材料一段段拼成超长提示词。
  LLM 的"输入长度"有限（上下文窗口），案例特别多时要注意。
- 规则草案结构：{"rule": {...}, "evidence": {cond_id: [案例名]}}。
  evidence（证据映射）记录每条条件来自哪些案例，前端确认页可以
  展示"这条条件的依据"，人审时更有据可依。
- 输出清洗：LLM 输出的 JSON 不一定规范（漏字段/类型错），
  extract_draft 里做了大量清洗兜底：补默认值、删多余字段、
  类型缺失时按字段推断，最后用 Pydantic 校验兜底。

输出草案结构：{"rule": {...}, "evidence": {cond_id: [案例名]}}
"""
from __future__ import annotations

import json

from .. import llm
from ..models import Rule
from ..verifiers import VERIFIER_INFO

# 可用验证函数清单（写入提示词，供模型选择 compute 字段），从 verifiers.VERIFIER_INFO 生成
# —— 单一来源：以后在 verifiers.py 里新增校验函数，这里自动同步，不用改提示词
VERIFY_CATALOG = "\n".join(
    ["可用验证函数（compute 字段取值）及参数说明："]
    + ["- %s %s %s" % (name, json.dumps(params, ensure_ascii=False), desc)
       for name, (desc, params) in VERIFIER_INFO.items()])

SYSTEM = "你是专业A股选股策略分析师，擅长从多个选股案例中归纳可执行的选股条件。"


def build_prompt(mode_name: str, case_materials: list[dict]) -> str:
    """拼装规则提炼提示词

    参数 case_materials: [{case_id, description, vision: [截图解读dict]}]
    输出：一段超长提示词 = 案例材料 + JSON 输出格式要求 + 规则清单 + 5条要求
    """
    parts = ['以下是用户选股模式《%s》的 %d 个案例材料。' % (mode_name, len(case_materials))]
    for m in case_materials:
        parts.append("\n【案例：%s】" % m["case_id"])
        if m.get("description"):
            parts.append("文字说明：%s" % m["description"])
        # 每张截图的解读都塞进去（视觉模型第一步的产出在这里派上用场）
        for i, v in enumerate(m.get("vision") or [], 1):
            parts.append("截图%d解读：%s" % (i, json.dumps(v, ensure_ascii=False)))
    parts.append("""
请归纳该模式的选股条件，输出一个 JSON 对象（不要输出JSON以外的内容）：
{
  "name": "模式名称",
  "description": "模式一句话概述",
  "combine": "intersection",
  "conditions": [
    {
      "id": "c1",
      "text": "条件一句话描述",
      "type": "query 或 verify",
      "query": "若type=query，给出简洁的东财智能选股自然语言查询语句，如 MACD金叉、主力净流入大于0",
      "params": {"若type=verify，给参数，如 threshold: 15"},
      "compute": "若type=verify，从下面函数清单中选择合适的函数名",
      "evidence": ["体现该条件的案例名列表"]
    }
  ],
  "notes": "归纳说明（可选）"
}

要求：
1. type=query 的条件必须是东财智能选股能用自然语言查出来的（如 MACD金叉/均线多头排列/主力净流入/市盈率等），查询语句保持简洁，一条查询一个核心条件。
2. type=verify 的条件用数据工具逐只验证，compute 必须从下面的函数清单中选取，params 只保留必要参数。
3. 条件数量控制在 2-6 条，不要过度拆分。
4. combine 固定为 intersection（各条件取交集）。
5. 每条条件必须列出 evidence（哪些案例体现了该条件）。

%s""" % VERIFY_CATALOG)  # 把校验函数清单拼到提示词末尾
    return "\n".join(parts)


def extract_draft(mode_name: str, case_materials: list[dict]) -> dict:
    """多案例 → 规则草案（含证据映射），调用文本模型

    返回：{"rule": {...}, "evidence": {cond_id: [案例名, ...]}}
    模型输出不规范时会做清洗兜底；彻底失败抛 ValueError 由上层捕获。
    """
    j = llm.chat_json(build_prompt(mode_name, case_materials), system=SYSTEM)
    if not isinstance(j, dict):
        raise ValueError("规则提炼输出不是 JSON 对象")

    conditions, evidence = [], {}
    for i, c in enumerate(j.get("conditions") or []):
        if not isinstance(c, dict):
            continue  # 非 dict 的脏数据直接跳过
        cid = str(c.get("id") or "c%d" % (i + 1))  # 没写 id 就按序号补
        ev = c.pop("evidence", []) or []           # 证据单独抽出，不进规则
        c["id"] = cid
        # 按 type 清洗字段：query 条件不要 compute/params，verify 条件不要 query
        if c.get("type") == "verify":
            c.pop("query", None)
            c.setdefault("compute", "")
            c.setdefault("params", {})
        elif c.get("type") == "query":
            c.pop("compute", None)
            c.pop("params", None)
            c.setdefault("query", "")
        else:  # 类型缺失：按字段推断（有 query 就按 query，否则按 verify）
            if c.get("query"):
                c["type"] = "query"
                c.pop("compute", None)
                c.pop("params", None)
            else:
                c["type"] = "verify"
                c.setdefault("compute", "")
                c.setdefault("params", {})
        conditions.append(c)
        evidence[cid] = ev

    rule_data = {
        "mode_id": mode_name,
        "name": j.get("name") or mode_name,
        "description": j.get("description") or "",
        "combine": j.get("combine") or "intersection",
        "conditions": conditions,
        "case_count": len(case_materials),
        "notes": j.get("notes") or "",
    }
    # 校验规则合法性（条件字段错误会抛异常）——最后一道防线
    Rule.model_validate(rule_data)
    return {"rule": rule_data, "evidence": evidence}
