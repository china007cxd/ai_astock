# -*- coding: utf-8 -*-
"""临时脚本：用旧 .pyc 字节码核对重写后的 .py 文件逻辑是否被改动。

原理：.pyc 里保存了模块的字节码，其中 co_consts 包含所有字符串常量
（提示词、格式串、默认值等）。把旧 pyc 的字符串常量集合与新源码的
字符串常量集合对比，新源码若缺少旧常量，说明逻辑被改动/删除了。

用法：python _t_verify.py <模块名>  例如 python _t_verify.py llm.py
"""
import importlib.util
import marshal
import pathlib
import sys

SRC = pathlib.Path(__file__).parent / "src" / "astock_agent"


def pyc_strings(pyc_path: pathlib.Path) -> set[str]:
    """从 pyc 文件提取所有字符串常量（递归遍历 code 对象）"""
    with open(pyc_path, "rb") as f:
        f.read(16)  # 跳过 pyc 文件头（magic + 时间戳 + 大小）
        code = marshal.load(f)
    out: set[str] = set()

    def walk(co):
        for c in co.co_consts:
            if isinstance(c, str):
                out.add(c)
            elif hasattr(c, "co_consts"):  # 嵌套的 code 对象（函数体）
                walk(c)
    walk(code)
    return out


def src_strings(py_path: pathlib.Path) -> set[str]:
    """编译新源码并提取字符串常量（与 pyc_strings 同口径）"""
    code = compile(py_path.read_text(encoding="utf-8"), str(py_path), "exec")
    out: set[str] = set()

    def walk(co):
        for c in co.co_consts:
            if isinstance(c, str):
                out.add(c)
            elif hasattr(c, "co_consts"):
                walk(c)
    walk(code)
    return out


def main():
    name = sys.argv[1]
    mod = name[:-3] if name.endswith(".py") else name
    # 找到旧 pyc（__pycache__ 里时间戳最新的那个，即上一轮运行产生的）
    cache_dir = SRC / "__pycache__"
    cands = sorted(cache_dir.glob(f"{mod}*.pyc"), key=lambda p: p.stat().st_mtime)
    if not cands:
        print("NO PYC for", mod)
        return
    old = pyc_strings(cands[-1])
    new = src_strings(SRC / f"{mod}.py")
    missing = {s for s in old if s not in new}
    # 过滤掉无意义差异：源码里我加的长注释字符串不在 pyc 常量中，反之旧 docstring 可能被扩充
    if missing:
        print(f"[{mod}] 旧 pyc 有 {len(old)} 个字符串常量，新源码缺 {len(missing)} 个：")
        for s in sorted(missing, key=len):
            print("   -", s[:160])
    else:
        print(f"[{mod}] OK: 旧 {len(old)} 个字符串常量全部保留于新源码中")


if __name__ == "__main__":
    main()
