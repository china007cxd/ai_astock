# -*- coding: utf-8 -*-
"""诊断: 直接请求腾讯 fqkline 看原始返回"""
import sys

sys.path.insert(0, ".")
import main as m

sc = m._secid("000001")
url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,320,qfq" % sc)
print("URL:", url)
try:
    d = m.fetch_json(url)
    node = (d.get("data") or {}).get(sc) or {}
    print("code:", d.get("code"), "| msg:", d.get("msg"))
    print("keys:", list((d.get("data") or {}).keys()))
    for k, v in node.items():
        print("  node[%s]: %s条" % (k, len(v) if isinstance(v, list) else v))
except Exception as e:
    print("EXC:", repr(e))
print("done")
