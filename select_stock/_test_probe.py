# -*- coding: utf-8 -*-
"""探测腾讯K线可用域名/变体"""
import json
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

variants = [
    ("web.ifzq.gtimg.cn 原URL", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,,,320,qfq", {}),
    ("proxy.finance.qq.com", "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/fqkline/get?param=sz000001,day,,,320,qfq", {}),
    ("web+Referer gu.qq.com", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,,,320,qfq", {"Referer": "https://gu.qq.com/"}),
    ("ifzq.gtimg.cn host", "https://ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,,,320,qfq", {}),
    ("web+day非复权", "https://web.ifzq.gtimg.cn/appstock/app/kline/kline?param=sz000001,day,,,320", {"Referer": "https://gu.qq.com/"}),
]

for name, url, extra in variants:
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        req.add_header("Accept", "*/*")
        for k, v in extra.items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                j = json.loads(raw)
                node = ((j.get("data") or {}).get("sz000001") or {})
                n = len(node.get("qfqday") or node.get("day") or [])
                print("[OK ]", name, "->", n, "根")
            except Exception:
                print("[RAW]", name, "->", raw[:120].replace("\n", " "))
    except Exception as e:
        print("[ERR]", name, "->", repr(e)[:100])
    time.sleep(1)
print("done")
