# -*- coding: utf-8 -*-
"""冷启动过滤(不等预热) + K线弹窗接口回归"""
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


# 1. 换一个条件(第3页), 查询后立即过滤(不等预热)
r = post(BASE + "/api/xuangu", {"q": "连续放量 非ST", "size": 20, "page": 3})
codes = [x["code"] for x in r["rows"]]
print("查询第3页: %d 只" % len(codes))

t0 = time.time()
url = (BASE + "/api/filter?codes=%s&months=3&drop_pct=-30&mode=%s"
       % (",".join(codes), urllib.request.quote("至今")))
done = None
with urllib.request.urlopen(url, timeout=120) as resp:
    for raw in resp:
        line = raw.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        item = json.loads(line[5:].strip())
        if item.get("type") == "done":
            done = item
            break
print("冷启动过滤(并发拉取): %.2fs" % (time.time() - t0))

# 2. K线弹窗接口回归(回退域名)
k = get(BASE + "/api/kline?code=000001&period=day")
print("api/kline: %d 根" % len(k.get("klines", [])))
c = get(BASE + "/api/chips?code=000001")
print("api/chips: %s, avg %s" % (c.get("date"), c.get("avg_cost")))
m = get(BASE + "/api/minute?code=000001")
print("api/minute: %d 点" % len(m.get("points", [])))
print("done")
