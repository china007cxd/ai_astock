"""Pydantic 数据模型：规则(Rule)/条件(Condition)/运行结果(RunResult) 等

【这个文件是干什么的】
定义整个项目里"数据长什么样"。比如一条选股规则 Rule 包含哪些字段、
一个条件 Condition 有两种类型（查询/验证）等。所有模块读写规则、
结果时都使用这里的类，保证数据格式统一、不会写错字段名。

【给小白的关键概念】
- Pydantic：数据校验库。定义类时声明字段类型，存入数据时会自动校验
  （比如 age: int 存 "abc" 会直接报错），还能自动补默认值。
- 判别联合（discriminator）：Condition 是一个"二选一"的类型——
  看 type 字段是 "query" 还是 "verify"，自动解析成 QueryCondition 或
  VerifyCondition。相当于"同一个字段，装两种不同形状的数据"。
- model_dump()：把对象转成普通 dict（方便存 YAML/JSON 或给前端）；
  model_validate()：反过来，把 dict 转回对象（并做校验）。

【数据流】
学习管线：LLM 输出 dict → Rule.model_validate() 校验 → 存 rules/*.yaml
运行引擎：读 rules/*.yaml → Rule.model_validate() 还原 → 执行条件
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class QueryCondition(BaseModel):
    """查询型条件：交给东财智能选股做自然语言查询

    例如：type="query"、query="MACD金叉" → 运行引擎会调 em_xuangu 工具
    查出一批满足"MACD金叉"的股票。
    """

    id: str              # 条件编号，如 "c1"（规则内唯一，diff 对比时靠它对应）
    text: str            # 条件的一句话描述，如 "日线MACD金叉"（展示给用户看）
    type: Literal["query"] = "query"   # 固定为 "query"，用于判别联合
    query: str           # 给东财的自然语言查询语句，如 "MACD金叉"


class VerifyCondition(BaseModel):
    """验证型条件：用数据工具逐只验证

    例如：type="verify"、compute="chips_concentration_lt"、params={threshold: 15}
    → 运行引擎对候选池每只股票调 verifiers.py 里的对应函数，
    判断 "90%筹码集中度 < 15%" 是否成立。
    """

    id: str              # 条件编号
    text: str            # 条件描述
    type: Literal["verify"] = "verify"  # 固定为 "verify"
    compute: str         # 验证函数名，对应 verifiers.VERIFIERS 注册表里的 key
    params: dict = Field(default_factory=dict)  # 函数参数，如 {"n": 20}


# 判别联合：type=="query" → QueryCondition；type=="verify" → VerifyCondition
Condition = Annotated[Union[QueryCondition, VerifyCondition], Field(discriminator="type")]


class Rule(BaseModel):
    """一套选股模式的完整规则（学习产物，人审后保存）

    对应 rules/模式名.yaml 文件的内容。学习管线生成它，
    运行引擎执行它。
    """

    mode_id: str                     # 模式标识，与 cases/ 下的文件夹名一致
    name: str                        # 模式名称，如 "MACD金叉启动"
    description: str = ""            # 模式一句话概述
    combine: Literal["intersection", "union"] = "intersection"
    # combine 表示多个 query 条件的组合方式：
    #   intersection = 取交集（股票要同时满足所有查询条件）——默认，方案确认的用法
    #   union = 取并集（满足任意一条即可）——预留扩展位
    conditions: list[Condition] = Field(default_factory=list)  # 条件清单
    verified_at: str = ""            # 人审确认时间（confirm_draft 时写入）
    case_count: int = 0              # 参与学习的案例数量
    notes: str = ""                  # 归纳说明（LLM 生成的备注，可选）


class StockHit(BaseModel):
    """某条件查出的单只股票（一条查询的原始命中记录）"""

    code: str                        # 股票代码，如 "000001"
    name: str = ""                   # 股票名称
    extra: dict = Field(default_factory=dict)  # 额外字段（现价/涨跌/命中原因等）


class ConditionResult(BaseModel):
    """单个条件的查询/验证汇总（运行引擎每个条件的执行结果）"""

    condition_id: str                # 对应规则里条件的 id
    text: str                        # 条件描述
    hits: list[StockHit] = Field(default_factory=list)  # 命中的股票列表
    total: int = 0                   # 命中总数
    ok: bool = True                  # 该条件是否执行成功（查询失败为 False）
    error: str = ""                  # 失败原因


class StockResult(BaseModel):
    """最终输出的单只股票：命中/未命中/未验证的条件清单 + 说明

    对应结果页表格的一行。
    """

    code: str                        # 股票代码
    name: str = ""                   # 股票名称
    price: str = "-"                 # 现价（字符串，保留 "-" 表示无数据）
    pct: str = "-"                   # 涨跌幅
    matched: list[str] = Field(default_factory=list)    # 命中的条件（绿色标签）
    failed: list[str] = Field(default_factory=list)     # 未通过的条件（红色标签）
    unverified: list[str] = Field(default_factory=list) # 验证失败/未验证（灰色标签）
    note: str = ""                   # LLM 生成的一句话命中说明


class RunResult(BaseModel):
    """一次运行结果（存档 runs/*.json）

    选股运行的完整产物，历史记录页读取的就是这个。
    """

    run_id: str                      # 运行编号，如 "20260824_213600_ab12cd"
    mode_id: str                     # 运行的模式
    mode_name: str = ""              # 模式名称
    time: str = ""                   # 运行时间（字符串形式，便于直接展示）
    status: str = "done"             # done / failed
    rule: Rule | None = None         # 本次运行使用的规则快照（结果自包含）
    condition_results: list[ConditionResult] = Field(default_factory=list)  # 各查询条件结果
    stocks: list[StockResult] = Field(default_factory=list)                 # 最终候选股票
    empty_reason: str = ""           # 交集为空时的提示（提示用户放宽哪条条件）
    error: str = ""                  # 运行失败原因
