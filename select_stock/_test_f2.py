# -*- coding: utf-8 -*-
"""过滤缓存命中耗时测试(连续两次)"""
import json
import time
import urllib.request

codes = "600478,000541,600361,600717,600956,601818,601336,600612,600674,600884,600983,301007,600483,301035"

for i in range(2):
    t0 = time.time()
    url = ("http://127.0.0.1:5188/api/filter?codes=%s&months=3&drop_pct=-30&mode=%s"
           % (codes, urllib.request.quote("至今")))
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
    print("filter 第%d次: %.2fs" % (i + 1, time.time() - t0))
print("done")
