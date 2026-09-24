# -*- coding: utf-8 -*-
from app.indicators import apply_filters, enrich_klines, market_sentiment


def test_enrich_klines_adds_expected_indicators() -> None:
    rows = [
        {"date": f"2026-01-{day:02d}", "open": day, "close": day + 0.5, "high": day + 1, "low": day - 1, "volume": 1000 + day}
        for day in range(1, 29)
    ]
    enriched = enrich_klines(rows)
    assert len(enriched) == len(rows)
    assert enriched[-1]["ma5"] is not None
    assert all(key in enriched[-1] for key in ("dif", "dea", "macd", "k", "d", "j"))


def test_filters_are_composed() -> None:
    rows = [{"code": "1", "change": 8, "turnover_rate": 12}, {"code": "2", "change": 3, "turnover_rate": 8}]
    assert apply_filters(rows, [{"field": "change", "operator": "gte", "value": 5}]) == [rows[0]]


def test_market_sentiment_has_stable_range() -> None:
    market = [{"change": 2}] * 70 + [{"change": -1}] * 30
    limit_rows = [{"board_height": 3, "status": "涨停"}] * 4
    result = market_sentiment(limit_rows, market)
    assert 0 <= result["score"] <= 100
    assert result["rises"] == 70
