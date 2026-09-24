# -*- coding: utf-8 -*-
"""分页条数功能验证"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:5188"
time.sleep(4)


def post(url, body, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8")


# 1. 默认 size(不传) -> 60条
r = post(BASE + "/api/xuangu", {"q": "MACD金叉 非ST"})
print("默认(不传size): %d 条, total=%d, pages=%d" % (len(r["rows"]), r["total"], r["pages"]))

# 2. size=60 第1/2页无重叠
r1 = post(BASE + "/api/xuangu", {"q": "MACD金叉 非ST", "size": 60, "page": 1})
r2 = post(BASE + "/api/xuangu", {"q": "MACD金叉 非ST", "size": 60, "page": 2})
c1 = {x["code"] for x in r1["rows"]}
c2 = {x["code"] for x in r2["rows"]}
print("60/页: page1=%d只 page2=%d只 重叠=%d" % (len(r1["rows"]), len(r2["rows"]), len(c1 & c2)))

# 3. size=200 -> 全量一页
r = post(BASE + "/api/xuangu", {"q": "MACD金叉 非ST", "size": 200, "page": 1})
print("200/页: %d 只, pages=%d (total=%d)" % (len(r["rows"]), r["pages"], r["total"]))

# 4. size=500 超上限 -> 被限制为200
r = post(BASE + "/api/xuangu", {"q": "MACD金叉 非ST", "size": 500, "page": 1})
print("500越界: 实际 %d 只" % len(r["rows"]))

# 5. 前端页面包含下拉框与默认60
html = get(BASE + "/")
print("页面: xgPageSize=%d处 xgPageSizeChange=%d处 value=60选中=%d"
      % (html.count("xgPageSize"), html.count("xgPageSizeChange"),
         html.count('<option value="60" selected>')))
print("done")
