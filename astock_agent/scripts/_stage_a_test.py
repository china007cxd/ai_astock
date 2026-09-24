# 临时验证脚本（阶段A骨架自检）
import asyncio

from astock_agent.llm import get_chat_llm, LLMNotConfiguredError, parse_json_text
from astock_agent.astock_client import client
from astock_agent.models import Rule, QueryCondition, VerifyCondition

# 1) 未配置 key 时的友好报错
try:
    get_chat_llm()
    print("FAIL: 未配置 key 却未报错")
except LLMNotConfiguredError as e:
    print("PASS: key 检查 ->", e)

# 2) JSON 解析
print("PASS: parse_json ->", parse_json_text('```json\n{"a": 1}\n```'))

# 3) 规则模型往返
rule = Rule(
    mode_id="test",
    name="测试模式",
    conditions=[
        QueryCondition(id="c1", text="MACD金叉", query="MACD金叉"),
        VerifyCondition(id="c2", text="筹码集中", compute="chips_concentration_lt",
                        params={"threshold": 15}),
    ],
)
dump = rule.model_dump()
back = Rule.model_validate(dump)
assert back.conditions[0].type == "query" and back.conditions[1].compute == "chips_concentration_lt"
print("PASS: Rule 序列化往返", [c.type for c in back.conditions])

# 4) astock 连通性（未启动时会打印 False）
ok = asyncio.run(client.health())
print("INFO: astock 连通性 =", ok, "(未启动 astock 时为 False)")
