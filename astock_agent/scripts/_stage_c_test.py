# 阶段C自检：存储层 + diff + 案例结构（不调用 LLM）
import base64

from astock_agent import storage
from astock_agent.models import Rule, QueryCondition, VerifyCondition, RunResult
from astock_agent.learn.diff import diff_rules

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

# 1) 创建示例模式 + 案例
mid = "_测试模式_删除我"
storage.create_mode(mid)
storage.add_case(mid, "案例01_某票", "日线MACD金叉，且主力净流入为正", [("a.png", PNG_1PX), ("b.jpg", PNG_1PX)])
storage.add_case(mid, "案例02_某票", "同上，且属于当日热点板块", [("a.png", PNG_1PX)])
cases = storage.list_cases(mid)
assert len(cases) == 2 and cases[0]["image_count"] == 2, cases
print("PASS: 案例库读写 ->", [(c["case_id"], c["image_count"]) for c in cases])
c0 = storage.read_case(mid, "案例01_某票")
assert len(c0["image_paths"]) == 2 and "MACD" in c0["description"]
print("PASS: read_case 图片路径/说明.md")

# 2) 草案保存/加载/确认
draft = {
    "rule": {"mode_id": mid, "name": "测试模式", "combine": "intersection",
             "conditions": [
                 {"id": "c1", "text": "MACD金叉", "type": "query", "query": "MACD金叉"},
                 {"id": "c2", "text": "筹码集中", "type": "verify",
                  "compute": "chips_concentration_lt", "params": {"threshold": 15}},
             ]},
    "evidence": {"c1": ["案例01_某票"], "c2": ["案例02_某票"]},
}
storage.save_draft(mid, draft)
assert storage.load_draft(mid)["evidence"]["c1"]
print("PASS: 草案保存/加载")
rule = storage.confirm_draft(mid)
assert rule.verified_at and storage.load_draft(mid) is None
print("PASS: 确认草案 -> rules/%s.yaml (verified_at=%s)" % (mid, rule.verified_at))

# 3) 增量 diff
new_rule = Rule(mode_id=mid, name="测试模式", conditions=[
    QueryCondition(id="c1", text="MACD金叉", query="MACD金叉"),          # 不变
    QueryCondition(id="c3", text="主力净流入大于0", query="主力净流入大于0"),  # 新增
])
d = diff_rules(rule, new_rule)
assert len(d["unchanged"]) == 1 and len(d["added"]) == 1 and len(d["removed"]) == 1
print("PASS: diff -> 不变%d 新增%d 删除%d" % (len(d["unchanged"]), len(d["added"]), len(d["removed"])))

# 4) 运行记录
run = RunResult(run_id="test_run_1", mode_id=mid, mode_name="测试模式",
                time="2026-08-24 12:00:00", rule=rule)
storage.save_run(run)
runs = storage.list_runs()
assert any(r["run_id"] == "test_run_1" for r in runs)
assert storage.load_run("test_run_1").mode_id == mid
print("PASS: 运行记录保存/列表/加载")

# 5) 清理测试数据
storage.delete_mode(mid)
assert mid not in [m["mode_id"] for m in storage.list_modes()]
import os
for p in (storage.config.RUNS_DIR / "test_run_1.json",):
    if p.exists():
        p.unlink()
print("PASS: 清理完成，全部阶段C存储/diff自检通过")
