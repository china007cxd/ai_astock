# -*- coding: utf-8 -*-
"""给 index.html 所有静态资源 URL 加版本号, 强制浏览器拉取新文件"""
import re

p = r"D:\SoftwareInstallaction\v62.1\astock\index.html"
c = open(p, encoding="utf-8").read()

def add_v(m):
    return m.group(1) + "?v=3" + m.group(2)

c2 = re.sub(r'(href="static/[^"]+?)(")', lambda m: m.group(1) + "?v=3" + '"', c)
c2 = re.sub(r'(src="static/[^"]+?)(")', lambda m: m.group(1) + "?v=3" + '"', c2)

n = c2.count("?v=3")
print("changed refs:", n)
open(p, "w", encoding="utf-8").write(c2)
