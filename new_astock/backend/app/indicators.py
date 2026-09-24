# -*- coding: utf-8 -*-
"""不依赖第三方科学计算库的常用技术指标。"""
from __future__ import annotations

from typing import Any


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def _sma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = []
    rolling = 0.0
    for index, value in enumerate(values):
        rolling += value
        if index >= period:
            rolling -= values[index - period]
        result.append(round(rolling / period, 4) if index >= period - 1 else None)
    return result


def enrich_klines(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    closes = [float(row.get("close") or 0) for row in rows]
    highs = [float(row.get("high") or 0) for row in rows]
    lows = [float(row.get("low") or 0) for row in rows]
    ema12, ema26 = _ema(closes, 12), _ema(closes, 26)
    dif = [a - b for a, b in zip(ema12, ema26, strict=False)]
    dea = _ema(dif, 9)
    mas = {period: _sma(closes, period) for period in (5, 10, 20, 60)}
    k_value = d_value = 50.0
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        begin = max(0, index - 8)
        low_n, high_n = min(lows[begin : index + 1]), max(highs[begin : index + 1])
        rsv = 50.0 if high_n == low_n else (closes[index] - low_n) / (high_n - low_n) * 100
        k_value = k_value * 2 / 3 + rsv / 3
        d_value = d_value * 2 / 3 + k_value / 3
        result.append(
            {
                **row,
                "ma5": mas[5][index],
                "ma10": mas[10][index],
                "ma20": mas[20][index],
                "ma60": mas[60][index],
                "dif": round(dif[index], 4),
                "dea": round(dea[index], 4),
                "macd": round((dif[index] - dea[index]) * 2, 4),
                "k": round(k_value, 4),
                "d": round(d_value, 4),
                "j": round(3 * k_value - 2 * d_value, 4),
            }
        )
    return result


def apply_filters(rows: list[dict[str, Any]], filters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    operators = {
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
        "contains": lambda a, b: str(b).lower() in str(a).lower(),
    }
    output = rows
    for rule in filters:
        field, operator, expected = rule.get("field"), rule.get("operator", "gte"), rule.get("value")
        compare = operators.get(operator)
        if not field or compare is None:
            continue
        filtered = []
        for row in output:
            actual = row.get(field)
            if actual is None:
                continue
            try:
                if compare(float(actual), float(expected)) if operator != "contains" else compare(actual, expected):
                    filtered.append(row)
            except (TypeError, ValueError):
                continue
        output = filtered
    return output


def market_sentiment(limit_rows: list[dict[str, Any]], market_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rises = sum(1 for row in market_rows if float(row.get("change") or 0) > 0)
    falls = sum(1 for row in market_rows if float(row.get("change") or 0) < 0)
    flats = max(0, len(market_rows) - rises - falls)
    high_boards = sum(1 for row in limit_rows if int(row.get("board_height") or 1) >= 3)
    broken = sum(1 for row in limit_rows if row.get("status") == "炸板")
    denominator = max(1, rises + falls)
    score = min(100, max(0, round(50 + (rises - falls) / denominator * 30 + high_boards * 2 - broken)))
    return {
        "score": score,
        "label": "亢奋" if score >= 80 else "活跃" if score >= 60 else "平衡" if score >= 40 else "低迷",
        "rises": rises,
        "falls": falls,
        "flats": flats,
        "limit_up": len([row for row in limit_rows if row.get("status") != "炸板"]),
        "broken": broken,
        "high_boards": high_boards,
    }
