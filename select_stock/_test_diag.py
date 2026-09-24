# -*- coding: utf-8 -*-
"""诊断: 单只股票K线拉取失败原因"""
import sys

sys.path.insert(0, ".")
import main as m

m._KLINE_CACHE.clear()
m._KLINE_INFLIGHT.clear()

for code in ["600478", "000541", "000001"]:
    r = m.get_kline_data(code)
    print(code, "->", len(r), "根" if r else "EMPTY/FAIL")
print("done")
