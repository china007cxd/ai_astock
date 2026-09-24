# -*- coding: utf-8 -*-
"""对比不同拉取策略耗时: pz=200串行 / pz=100串行 / 并发2路pz=100"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36"
FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
HOSTS = ["https://push2delay.eastmoney.com", "http://90.push2.eastmoney.com",
         "https://push2.eastmoney.com"]


def grab(host, pn, pz):
    url = (host + "/api/qt/clist/get?pn=%d&pz=%d&po=1&np=1"
           "&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12&fs="
           + FS + "&fields=f12,f14") % (pn, pz)
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            j = json.loads(urllib.request.urlopen(req, timeout=10).read())
            d = j.get("data") or {}
            diff = d.get("diff") or []
            if isinstance(diff, dict):
                diff = diff.get("diff") or []
            if isinstance(diff, list) and diff:
                return [x["f12"] for x in diff]
        except Exception:
            time.sleep(0.5)
    return None


# 策略1: pz=200 串行 (30 页)
def s1():
    t0 = time.time()
    host = HOSTS[0]
    rows = []
    for pn in range(1, 31):
        r = grab(host, pn, 200)
        if r is None:
            print("s1 fail at pn", pn)
            return None
        rows.extend(r)
        time.sleep(0.1)
    return time.time() - t0, len(rows)


# 策略2: pz=100 串行 (60 页)
def s2():
    t0 = time.time()
    host = HOSTS[0]
    rows = []
    for pn in range(1, 61):
        r = grab(host, pn, 100)
        if r is None:
            print("s2 fail at pn", pn)
            return None
        rows.extend(r)
    return time.time() - t0, len(rows)


# 策略3: pz=200 并发2路 (30 页)
def s3():
    t0 = time.time()
    host = HOSTS[0]
    with ThreadPoolExecutor(max_workers=2) as ex:
        rs = list(ex.map(lambda pn: grab(host, pn, 200), range(1, 31)))
    if any(r is None for r in rs):
        print("s3 fail")
        return None
    rows = [c for r in rs for c in r]
    return time.time() - t0, len(rows)


for name, fn in [("pz200串行", s1), ("pz100串行", s2), ("pz200并发2", s3)]:
    try:
        r = fn()
        print("%s -> %.1fs rows=%d" % (name, r[0], r[1]) if r else "%s FAIL" % name)
    except Exception as e:
        print(name, "EXC", e)
    time.sleep(2)
