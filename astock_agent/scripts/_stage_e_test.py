# 阶段E自检：Web REST API 全端点验证（不依赖 LLM Key）
import asyncio
import time

import httpx

BASE = "http://127.0.0.1:8766"
mid = "_WEB测试_删除我"
PASS = []
FAIL = []


def check(name: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(name)
    print(("  [OK] " if ok else "  [XX] ") + name + ((" - " + detail) if detail else ""))


async def main():
    async with httpx.AsyncClient(timeout=60) as c:
        # 静态页面
        r = await c.get(BASE + "/")
        check("GET / 首页", r.status_code == 200 and "选股" in r.text)
        r = await c.get(BASE + "/static/app.js")
        check("GET /static/app.js", r.status_code == 200 and "pollJob" in r.text)
        r = await c.get(BASE + "/static/app.css")
        check("GET /static/app.css", r.status_code == 200)

        # 健康/校验目录
        r = await c.get(BASE + "/api/health")
        h = r.json()
        check("GET /api/health", r.status_code == 200 and "astock" in h,
              "astock=%s llm=%s" % (h.get("astock"), h.get("llm")))
        r = await c.get(BASE + "/api/verifiers")
        v = r.json()
        check("GET /api/verifiers", r.status_code == 200 and "macd_gold_cross" in v,
              "%d 个校验函数" % len(v))

        # 模式 CRUD
        r = await c.post(BASE + "/api/modes", json={"name": mid})
        check("POST /api/modes", r.status_code == 200 and r.json()["mode_id"] == mid)
        r = await c.post(BASE + "/api/modes", json={"name": mid})
        check("POST /api/modes 重名幂等", r.status_code == 200)
        r = await c.get(BASE + "/api/modes")
        check("GET /api/modes", r.status_code == 200
              and any(m["mode_id"] == mid for m in r.json()))
        r = await c.get(BASE + "/api/modes/%s" % mid)
        check("GET /api/modes/{id}", r.status_code == 200
              and r.json()["rule"] is None and r.json()["draft"] is None)

        # 案例上传（无图片的空案例 + 非法扩展名拒绝）
        r = await c.post(BASE + "/api/modes/%s/cases" % mid,
                         data={"case_name": "空案例", "description": "测试说明"})
        check("POST cases 空案例", r.status_code == 200 and "case_id" in r.json())
        r = await c.post(BASE + "/api/modes/%s/cases" % mid,
                         files={"files": ("a.txt", b"xx", "text/plain")})
        check("POST cases 非图片拒绝", r.status_code == 400)
        r = await c.get(BASE + "/api/modes/%s" % mid)
        check("GET 案例列表", r.status_code == 200 and len(r.json()["cases"]) == 1)
        r = await c.delete(BASE + "/api/modes/%s/cases/%s" % (mid, "空案例"))
        check("DELETE case", r.status_code == 200)
        r = await c.get(BASE + "/api/modes/%s/cases/x/images/a.png" % mid)
        check("GET 不存在的图片 404", r.status_code == 404)

        # 学习无案例 → 400
        r = await c.post(BASE + "/api/modes/%s/learn" % mid)
        check("POST learn 无案例被拒", r.status_code == 400)

        # 草案：GET 404 → PUT → GET → confirm
        r = await c.get(BASE + "/api/modes/%s/draft" % mid)
        check("GET draft 404", r.status_code == 404)
        rule = {
            "mode_id": mid, "name": "WEB测试模式",
            "description": "MACD金叉 + 获利盘过半",
            "combine": "intersection",
            "conditions": [
                {"id": "c1", "text": "日线MACD金叉", "type": "query", "query": "MACD金叉"},
                {"id": "c2", "text": "获利盘过半", "type": "verify",
                 "compute": "profit_ratio_gt", "params": {"threshold": 50}},
            ],
        }
        r = await c.put(BASE + "/api/modes/%s/draft" % mid, json={"rule": rule})
        check("PUT draft", r.status_code == 200 and r.json()["diff"]["is_new"])
        r = await c.put(BASE + "/api/modes/%s/draft" % mid, json={"rule": {"bad": 1}})
        check("PUT draft 非法规则被拒", r.status_code == 400)
        r = await c.get(BASE + "/api/modes/%s/draft" % mid)
        check("GET draft", r.status_code == 200 and "rule" in r.json())
        r = await c.post(BASE + "/api/modes/%s/confirm" % mid)
        check("POST confirm", r.status_code == 200)
        r = await c.get(BASE + "/api/modes/%s" % mid)
        check("规则已落盘", r.json()["rule"] is not None and r.json()["draft"] is None)

        # 运行（依赖 astock 8765 服务）
        r = await c.post(BASE + "/api/modes/%s/run" % mid)
        if r.status_code == 503:
            check("POST run astock未启动被拒(503)", True)
        else:
            check("POST run 启动任务", r.status_code == 200)
            job_id = r.json()["job_id"]
            for _ in range(120):
                j = (await c.get(BASE + "/api/jobs/%s" % job_id)).json()
                if j["status"] != "running":
                    break
                await asyncio.sleep(1)
            check("GET /api/jobs/%s" % job_id, j["status"] in ("done", "failed"),
                  "status=%s progress=%d%%" % (j["status"], j["progress"]))
            if j["status"] == "done":
                rid = j["result"]["run_id"]
                r = await c.get(BASE + "/api/runs")
                check("GET /api/runs", any(x["run_id"] == rid for x in r.json()))
                r = await c.get(BASE + "/api/runs/%s" % rid)
                d = r.json()
                check("GET /api/runs/{id}", r.status_code == 200
                      and "stocks" in d and "condition_results" in d,
                      "%d 只候选" % len(d["stocks"]))
                r = await c.get(BASE + "/api/runs/不存在")
                check("GET 不存在的运行记录 404", r.status_code == 404)

        # 无规则模式 run 被拒
        r = await c.post(BASE + "/api/modes", json={"name": "_无规则模式"})
        mid2 = r.json()["mode_id"]
        r = await c.post(BASE + "/api/modes/%s/run" % mid2)
        check("POST run 无规则被拒", r.status_code == 400)

        # 清理
        await c.delete(BASE + "/api/modes/%s" % mid)
        await c.delete(BASE + "/api/modes/%s" % mid2)
        r = await c.get(BASE + "/api/modes")
        check("DELETE mode 清理", not any(m["mode_id"] in (mid, mid2) for m in r.json()))

    print("\n=== 结果：%d 通过 / %d 失败 ===" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：", FAIL)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
