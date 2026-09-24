"""增量学习 diff：新草案 vs 已保存规则的差异对比

【这个文件是干什么的】
学习管线的第三步（增量场景）：模式已经有正式规则，用户又新增了案例
重新学习。此时把新草案和旧规则逐条件对比，得出"新增了什么条件、
删除了什么条件、修改了什么条件"，前端确认页按差异高亮展示，
用户一眼看出这次学习改动了哪里。

【给小白的关键概念】
- diff（差异对比）：像 git diff 一样对比两个版本。这里对比的是
  规则的条件列表，而不是文本行。
- 匹配策略：优先按条件 id（c1/c2...）对应；id 对不上（模型重新
  编号了）就按条件文本（去掉空格后）对应——这样重学一次不会把
  所有条件都误判成"删除+新增"。
"""
from __future__ import annotations

from ..models import Condition, Rule


def _norm(t: str) -> str:
    """文本规范化：去首尾空白 + 去所有空格（"MACD 金叉" 和 "MACD金叉" 视为相同）"""
    return (t or "").strip().replace(" ", "")


def diff_rules(old: Rule | None, new: Rule) -> dict:
    """对比新旧规则，返回 {added, removed, modified, unchanged, is_new}

    匹配策略：优先按条件 id，其次按文本（学习重新编号时仍能对应上）。
    - added：新规则有、旧规则没有的条件
    - removed：旧规则有、新规则没有的条件
    - modified：两边都有但内容变了（{before, after}）
    - unchanged：完全没变
    - is_new：旧规则不存在（首次学习）
    """
    if old is None:
        # 首次学习：所有条件都算"新增"
        return {"added": [c.model_dump() for c in new.conditions],
                "removed": [], "modified": [], "unchanged": [],
                "is_new": True}

    # 旧规则建两个索引：按 id 和按规范化文本
    old_by_id = {c.id: c for c in old.conditions}
    old_by_text = {_norm(c.text): c for c in old.conditions if c.text.strip()}
    added, removed, modified, unchanged = [], [], [], []

    # 第一轮：遍历新条件，在旧规则里找对应
    for c in new.conditions:
        oc: Condition | None = old_by_id.get(c.id)
        if oc is None:
            oc = old_by_text.get(_norm(c.text))  # id 没对上，退而求其次按文本
        if oc is None:
            added.append(c.model_dump())
        elif oc.model_dump() == c.model_dump():
            unchanged.append(c.model_dump())
        else:
            modified.append({"before": oc.model_dump(), "after": c.model_dump()})

    # 第二轮：找出旧规则里"没被任何新条件对应上"的条件 = 被删除
    new_ids = {c.id for c in new.conditions}
    new_texts = {_norm(c.text) for c in new.conditions if c.text.strip()}
    for c in old.conditions:
        if c.id not in new_ids and _norm(c.text) not in new_texts:
            removed.append(c.model_dump())

    return {"added": added, "removed": removed, "modified": modified,
            "unchanged": unchanged, "is_new": False}
