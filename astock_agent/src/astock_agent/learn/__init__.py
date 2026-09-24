"""学习管线：案例 → 截图解读(视觉模型) → 规则提炼(文本模型) → 人审确认 → 规则库

【本子包三个模块的分工】
- vision.py  第一步：视觉模型看截图，输出结构化形态描述
- extract.py 第二步：文本模型综合所有案例材料，归纳规则草案
- diff.py    第三步（增量）：新草案与已存规则差异对比，供人审页高亮
三步的产物是人审页看到的"草案"，确认后才进规则库（rules/）。
"""
from .diff import diff_rules  # noqa: F401
from .extract import extract_draft  # noqa: F401
from .vision import analyze_case_images  # noqa: F401
