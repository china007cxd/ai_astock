# 02-models：数据模型（`src/astock_agent/models.py`）

## 职责

用 Pydantic 定义全项目共享的数据结构。规则怎么存、条件长什么样、
一次运行结果包含什么字段——都在这里规定。所有模块读写这些数据时
都经过这里的校验，保证"数据形状"全局一致。

## 类清单

| 类 | 用途 | 出现场景 |
|---|---|---|
| `QueryCondition` | 查询型条件：一句话交东财智能选股查 | 规则的 conditions 列表 |
| `VerifyCondition` | 验证型条件：指定校验函数+参数逐只验证 | 规则的 conditions 列表 |
| `Condition` | 判别联合：按 `type` 字段二选一自动解析 | 规则里的通用条件类型 |
| `Rule` | 一套模式的完整规则 | rules/*.yaml 的读写 |
| `StockHit` | 某条件命中的单只股票 | ConditionResult.hits |
| `ConditionResult` | 单个条件的执行汇总 | RunResult.condition_results |
| `StockResult` | 最终候选的股票（含命中/未通过/未验证标签） | RunResult.stocks |
| `RunResult` | 一次运行的完整结果 | runs/*.json 的读写 |

## 关键概念

- **判别联合（discriminator）**：`Condition` 用 `Field(discriminator="type")`
  实现"同一个字段装两种不同形状的数据"。序列化时看 `type=="query"` 就按
  `QueryCondition` 校验（必须有 `query` 字段），`type=="verify"` 就按
  `VerifyCondition` 校验（必须有 `compute` 字段）。这是本项目最核心的
  类型设计，理解它就能理解规则结构。
- **model_dump / model_validate**：对象 → dict / dict → 对象（带校验）。
  存 YAML/JSON 前 dump，读回后 validate。

## 字段速查

**Rule**：`mode_id`（模式标识）、`name`、`description`、
`combine`（intersection/union，固定用 intersection）、
`conditions`（条件列表）、`verified_at`（人审时间）、
`case_count`（案例数）、`notes`（归纳说明）

**StockResult**：`code`、`name`、`price`、`pct`、
`matched`（绿色标签）、`failed`（红色标签）、
`unverified`（灰色标签）、`note`（LLM 说明）

## 谁依赖它

- `storage.py`：读写 YAML/JSON 时用 Rule/RunResult 校验
- `engine.py`：全程使用这些类型
- `learn/extract.py`：LLM 输出的 dict 用 Rule 校验
- `main.py`：API 返回的 dict 大多来自 model_dump

## 修改注意点

1. **加字段**：给 `Rule` 等类加字段时给默认值（如 `str = ""`），
   保证旧 YAML 文件能继续校验通过（向后兼容）。
2. **改判别联合**：给 `QueryCondition`/`VerifyCondition` 加字段时，
   注意前端 `web/static/app.js` 的 `collectRule()` 也要同步加字段，
   否则前端编辑后保存会丢字段。
3. **不要删字段**：删字段会让已存文件校验失败（load_rule 返回 None，
   表现为"规则消失"）。若必须改结构，先写迁移逻辑。
