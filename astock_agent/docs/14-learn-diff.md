# 14-learn-diff：学习管线③差异对比（`learn/diff.py`）

## 职责

增量学习场景：模式已有正式规则，用户新增案例重新学习后，
把新草案与旧规则逐条件对比，供人审页高亮"新增/删除/修改/未变"。

## 对外的接口

`diff_rules(old: Rule | None, new: Rule) -> dict`

返回：
```
{added: [条件...], removed: [条件...],
 modified: [{before: 条件, after: 条件}, ...],
 unchanged: [条件...], is_new: bool}
```

## 匹配策略（关键设计）

1. **优先按条件 id**（c1/c2...）对应；
2. **id 对不上就按文本**（规范化：去首尾空白+去空格）对应；
3. 都对应不上 → 新侧记 added、旧侧记 removed；
4. 对应上但内容不同 → modified；
5. `old is None`（首次学习）→ 全部 added，`is_new=True`。

这样 LLM 重新编号条件时不会把整条规则误判成"全删全加"。

## 谁依赖它

- `main.py`：`_learn_job`（学习完成时算一次）和
  `save_draft`（前端编辑保存时重算一次）

## 修改注意点

1. **文本规范化是核心**：`_norm` 去空格防止"MACD 金叉"和"MACD金叉"
   被当成两条条件。改它要慎重（去空格也可能把有意的差异抹平）。
2. 前端 app.js 的 `renderDraftEditor` 依赖 added/removed/modified/
   unchanged 这四个字段名高亮，改名要同步前端。
3. 两轮循环的顺序有讲究：先扫新条件（判 added/modified/unchanged），
   再扫旧条件（判 removed），改逻辑时保持这个框架。
