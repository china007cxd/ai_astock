"""学习管线 CLI：对指定模式执行「截图解读 → 规则提炼 → 草案落盘 → 展示 diff」

用法：uv run python scripts/learn_mode.py 模式名
依赖：.env 中已配置 DEEPSEEK_API_KEY
"""
import asyncio
import sys

from astock_agent import storage
from astock_agent.learn.extract import extract_draft
from astock_agent.learn.vision import analyze_case_images
from astock_agent.learn.diff import diff_rules
from astock_agent.models import Rule


def log(msg: str) -> None:
    print("[learn] " + msg)


async def learn(mode_id: str) -> int:
    cases = storage.list_cases(mode_id)
    if not cases:
        log("模式《%s》下没有案例（每个案例需一个文件夹，含截图+说明.md）" % mode_id)
        return 1

    materials = []
    for c in cases:
        log("读取案例 %s（%d 张截图）" % (c["case_id"], c["image_count"]))
        full = storage.read_case(mode_id, c["case_id"])
        vision = await analyze_case_images(full["image_paths"], progress=log)
        materials.append({"case_id": c["case_id"],
                          "description": c["description"],
                          "vision": vision})

    log("规则提炼中（文本模型归纳 %d 个案例）..." % len(materials))
    draft = extract_draft(mode_id, materials)
    draft["learned_at"] = __import__("time").strftime("%Y-%m-%d %H:%M:%S")
    storage.save_draft(mode_id, draft)
    log("草案已保存到 drafts/%s.yaml" % mode_id)

    # 展示草案 + 与已存规则对比
    rule = Rule.model_validate(draft["rule"])
    print("\n=== 草案：%s ===" % rule.name)
    print(rule.description or "(无概述)")
    for c in rule.conditions:
        if c.type == "query":
            print("  [%s] query   %s  → 查询: %s" % (c.id, c.text, c.query))
        else:
            print("  [%s] verify  %s  → 函数: %s %s" % (c.id, c.text, c.compute, c.params))
    print("证据:", draft.get("evidence"))

    old = storage.load_rule(mode_id)
    d = diff_rules(old, rule)
    print("\n=== 与已保存规则的差异 ===")
    if d["is_new"]:
        print("  首次学习（此前无规则）")
    else:
        print("  新增 %d 条 / 修改 %d 条 / 删除 %d 条 / 不变 %d 条"
              % (len(d["added"]), len(d["modified"]), len(d["removed"]), len(d["unchanged"])))
        for c in d["added"]:
            print("  + 新增:", c["text"])
        for m in d["modified"]:
            print("  ~ 修改:", m["before"]["text"], "→", m["after"]["text"])
        for c in d["removed"]:
            print("  - 删除:", c["text"])
    print("\n请在 Web 界面「学习确认」页审查并确认，或直接检查 drafts/%s.yaml" % mode_id)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(asyncio.run(learn(sys.argv[1])))

