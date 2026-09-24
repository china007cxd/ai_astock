# -*- coding: utf-8 -*-
"""SSE 逐条日志接收时间打点"""
import json
import time
import urllib.request

codes = "600478,000541,600361,600717,600956,601818,601336,600612,600674,600884,600983,301007,600483,301035"
t_start = time.time()
last = t_start
url = ("http://127.0.0.1:5188/api/filter?codes=%s&months=3&drop_pct=-30&mode=%s"
       % (codes, urllib.request.quote("至今")))
with urllib.request.urlopen(url, timeout=120) as resp:
    for raw in resp:
        line = raw.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        now = time.time()
        item = json.loads(line[5:].strip())
        typ = item.get("type")
        print("%.3f (+%.3f) %s" % (now - t_start, now - last, typ))
        last = now
        if typ == "done":
            break
print("done")
