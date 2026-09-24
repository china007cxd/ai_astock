# 11-engine：运行引擎（`src/astock_agent/engine.py`）

## 职责

选股运行的核心流程编排。用 LangGraph 状态机把五个节点串起来，
前端点"运行"后，后台任务最终调 `Engine.run()`。

## 流程（LangGraph 图）

```
START → load_rule → query_conditions → intersect
      →（有候选？verify_conditions → summarize : END）→ END
```

| 节点 | 做什么 | 产出 |
|---|---|---|
| `load_rule` | 校验规则 | - |
| `query_conditions` | **并行**执行所有 query 条件（东财智能选股分条查询） | condition_results |
| `intersect` | 分条结果取交集 → 候选池；空则提前结束并提示 | candidates / empty_reason |
| `verify_conditions` | **并行**逐只执行 verify 条件 + 补实时行情 | stocks（带标签） |
| `summarize` | LLM 生成命中说明（失败用模板兜底） | stocks（带 note） |

## 关键概念

- **LangGraph**：状态在节点间传递（EngineState），节点返回的 dict
  合并进状态。条件边 `_after_intersect` 决定交集为空时短路结束。
- **确定性执行**：查询语句来自规则（学习产物），运行时不现场生成——
  结果可复现、可调试。LLM 只写结果说明，不影响选股本身。
- **并发控制**：`asyncio.gather` 并行查询/验证；`_VERIFY_SEM(8)`
  限制验证并发，防打爆 astock。
- **三类验证标签**：matched（通过）/ failed（未通过）/
  unverified（数据失败或函数未实现）。

## 失败与降级

- 单个查询条件失败 → 该条件 `ok=False`，不拖累其他条件；
  全部失败才整体结束。
- 单只股票验证数据失败 → 标"未验证"，继续其他股票。
- LLM 说明失败 → 模板说明 `_fallback_note`。
- 整体异常 → 存 `status="failed"` 的 RunResult（历史页可查原因）。

## 谁依赖它

- `main.py` 的 `_run_job`：`Engine(progress=回调).run(mode_id)`

## 修改注意点

1. **加节点**：`_build()` 里 add_node + add_edge；改分支逻辑改
   `_after_intersect`。注意每个节点函数签名必须是
   `async def xxx(self, state: EngineState) -> dict`。
2. **progress 回调**：每个关键步骤都应 `self.progress(...)`，
   否则前端进度条/日志不动。
3. **别把 LLM 加进查询决策**：保持"确定性执行"设计，LLM 只做解读。
4. `intersect` 的 `combine=union` 是预留扩展，前端目前固定
   intersection，改这里要同步前端编辑器。
5. 验证并发上限 8 是平衡速度和 astock 承载的结果，调大前先确认
   astock 不报限流。
