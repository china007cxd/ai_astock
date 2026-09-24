# -*- coding: utf-8 -*-
"""临时脚本：完整反汇编旧 .pyc，用于精确还原原始源码逻辑。"""
import dis
import marshal
import pathlib
import sys

SRC = pathlib.Path(__file__).parent / "src" / "astock_agent"


def main():
    name = sys.argv[1]
    mod = name[:-3] if name.endswith(".py") else name
    cache_dir = SRC / "__pycache__"
    cands = sorted(cache_dir.glob(f"{mod}*.pyc"), key=lambda p: p.stat().st_mtime)
    pyc = cands[-1]
    print("== file:", pyc.name)
    with open(pyc, "rb") as f:
        f.read(16)
        code = marshal.load(f)
    # 顶层：列出所有嵌套 code 对象（函数/类体）
    for c in code.co_consts:
        if hasattr(c, "co_consts"):
            print("\n===== CODE %s (argcount=%d) =====" % (c.co_name, c.co_argcount))
            dis.dis(c)
    print("\n===== MODULE top-level =====")
    dis.dis(code)


if __name__ == "__main__":
    main()
