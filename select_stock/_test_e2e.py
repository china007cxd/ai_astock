# -*- coding: utf-8 -*-
"""端到端: 查询第10页 -> warmup预热 -> SSE过滤 计时"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:5188"


def get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post(url, body, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# 1. 查询第10页(20只/页)
t0 = time.time()
r = post(BASE + "/api/xuangu", {"q": "MACD金叉 非ST", "size": 20, "page": 10})
t1 = time.time() - t0
codes = [x["code"] for x in r["rows"]]
print("查询第10页: %.2fs, 本页 %d 只" % (t1, len(codes)))

# 2. 触发预热
get(BASE + "/api/warmup?codes=" + ",".join(codes))
print("预热已触发")

# 3. 等3秒(模拟用户浏览时间)后过滤
time.sleep(3)
t0 = time.time()
url = (BASE + "/api/filter?codes=%s&months=3&drop_pct=-30&mode=%s"
       % (",".join(codes), urllib.request.quote("至今")))
total_logs = 0
done = None
with urllib.request.urlopen(url, timeout=120) as resp:
    for raw in resp:
        line = raw.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        item = json.loads(payload)
        if item.get("type") == "done":
            done = item
            break
        total_logs += 1
elapsed = time.time() - t0
passed = sum(1 for x in done["results"] if x["pass"])
print("过滤(预热后): %.2fs, %d 只, 通过 %d, 日志 %d 条" % (elapsed, len(done["results"]), passed, total_logs))
print("done")
