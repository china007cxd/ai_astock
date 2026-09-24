"""截图解读：视觉模型(deepseek-v4-flash-vision-exp) → 结构化 JSON

【这个文件是干什么的】
学习管线的第一步：把用户上传的选股案例截图交给视觉模型"看图说话"，
输出结构化的形态描述（K线形态/均线状态/指标状态/量价关系/标注文字等），
供下一步规则提炼（extract.py）使用。

只在学习案例阶段使用（离线一次），运行时不做图形判断
——所以视觉模型慢一点/贵一点都无所谓。

【给小白的关键概念】
- 视觉模型：能看懂图片的大模型。这里用 DeepSeek 的实验视觉模型，
  把图片转成 base64 文本后随提示词一起发过去（见 llm.analyze_image）。
- 提示词工程：VISION_PROMPT 精心规定了输出 JSON 的字段，并强调
  "只描述图中可见内容，不要推测图外信息"——防止模型脑补。
- 降级策略：模型偶尔输出不合格 JSON，parse 失败时降级为
  {"raw": 原文}，学习流程不中断，只是这单张图的解读质量差点。
- asyncio.to_thread：视觉模型调用是同步阻塞的（openai SDK），
  放到线程池里跑，避免阻塞整个事件循环。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from .. import llm
from ..llm import parse_json_text

# 视觉模型提示词：规定输出 JSON 的结构和每个字段的取值口径
VISION_PROMPT = """你是一名专业A股复盘助手，请仔细分析这张股票软件截图，输出一个 JSON 对象（不要输出JSON以外的内容），字段如下：
{
  "kline_pattern": "K线形态描述（如箱体突破/头肩底/连板拉升/缩量回踩，无则写无）",
  "ma_status": "均线状态（如多头排列/空头排列/粘合/回踩某均线，无则写无）",
  "indicator_status": "MACD/KDJ/成交量等技术指标状态（如MACD金叉/红柱放大，无则写无）",
  "volume_price": "量价关系（如放量突破/缩量回调/量价齐升，无则写无）",
  "annotations": "图中所有标注文字原文（箭头/圆圈旁的手写或输入文字，逐条列出；无则写无）",
  "panels": "图中面板信息（如筹码分布/主力资金/板块等副图或面板内容摘要，无则写无）",
  "judgment": "你对这张图整体形态的一句话判断"
}
只描述图中可见内容，不要推测图外信息。"""

# 文件扩展名 → 图片 MIME 类型（发给模型时声明图片格式）
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp"}


def _mime_of(path: Path) -> str:
    """根据扩展名推断 MIME 类型；不认识的一律按 png 声明（容错）"""
    return _MIME.get(path.suffix.lower(), "image/png")


def analyze_image_file(path: Path) -> dict:
    """单张截图 → 结构化解读 dict（失败时降级为 {"raw": 原文}）"""
    data = path.read_bytes()                       # 读图片字节
    text = llm.analyze_image(data, _mime_of(path), VISION_PROMPT)  # 视觉模型看图
    try:
        j = parse_json_text(text)                  # 解析模型输出的 JSON
        return j if isinstance(j, dict) else {"raw": text}
    except ValueError:
        return {"raw": text}                       # 解析失败：保留原文，不中断流程


async def analyze_case_images(paths: list[Path],
                              progress: Callable[[str], None] | None = None) -> list[dict]:
    """并发解读一个案例的全部截图（并发3，IO 放线程池避免阻塞事件循环）

    参数：
        paths: 截图文件路径列表（一个案例的所有截图）
        progress: 进度回调（写学习任务的日志）
    """
    sem = asyncio.Semaphore(3)  # 最多同时解读 3 张图（视觉模型限流友好）

    async def one(p: Path) -> dict:
        async with sem:
            if progress:
                progress("解读截图 %s" % p.name)
            # analyze_image_file 是同步阻塞函数，用 to_thread 扔到线程池执行
            return await asyncio.to_thread(analyze_image_file, p)

    # gather：并发解读所有截图，按输入顺序返回结果
    return list(await asyncio.gather(*[one(p) for p in paths]))
