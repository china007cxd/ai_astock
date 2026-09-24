# 13-learn-extract：学习管线②规则提炼（`learn/extract.py`）

## 职责

学习管线第二步：把某模式全部案例材料（说明.md + 截图解读）拼成
提示词，让文本模型归纳出规则草案（query/verify 条件组合），
供人审页审改。

## 对外的接口

| 接口 | 说明 |
|---|---|
| `build_prompt(mode_name, case_materials) -> str` | 拼装提示词（案例材料+格式要求+校验函数清单） |
| `extract_draft(mode_name, case_materials) -> dict` | 调模型出草案；返回 `{"rule": {...}, "evidence": {cond_id: [案例名]}}` |
| `VERIFY_CATALOG`（常量） | 校验函数清单文本，由 `VERIFIER_INFO` 自动生成 |

## 输出草案结构

```yaml
rule:
  mode_id / name / description / combine(intersection)
  conditions:            # 2-6 条
    - id: c1
      text: 条件一句话描述
      type: query         # 或 verify
      query: MACD金叉     # query 条件给东财查询语句
      # 或 compute: macd_gold_cross + params: {...}  # verify 条件
  case_count / notes
evidence: {c1: [案例A, 案例B], ...}   # 每条条件的依据案例
```

## 关键概念

- **提示词约束**：5 条要求（query 必须东财查得到 / verify 必须从
  清单选 / 2-6 条 / combine 固定 intersection / 必须带 evidence）。
- **输出清洗**：LLM 输出不规范时的兜底——补 id、按 type 删多余字段、
  type 缺失按字段推断、最后 `Rule.model_validate` 硬校验。
- **单一来源**：`VERIFY_CATALOG` 从 `verifiers.VERIFIER_INFO` 生成，
  新增校验函数自动进入提示词，无需改这里。

## 谁依赖它

- `main.py` 的 `_learn_job`（`asyncio.to_thread(extract_draft, ...)`）

## 修改注意点

1. **改提示词=改产品质量**：提示词里的"要求"直接决定规则质量，
   每次修改建议用 `scripts/learn_mode.py` 跑一个模式验证效果。
2. **`chat_json` 失败会抛异常**（llm.py 的设计），本文件不捕获，
   会一路冒泡到学习任务 failed——这是有意让用户看到明确失败原因。
3. 清洗逻辑按"query 条件删 compute/params、verify 条件删 query"
   的对称规则写，加新字段时记得在这里同步清洗。
4. `evidence` 不进规则本体（pop 出去单放），前端人审页靠它展示依据。
