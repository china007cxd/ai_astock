# -*- coding: utf-8 -*-
"""
A股智能选股 Web 应用 - 独立后端服务
=====================================
基于东方财富智能选股 + 历史跌幅二次过滤

功能:
  - 第一轮: 东财智能选股(自然语言条件, 如 "MACD金叉 非ST")
  - 第二轮: N个月内最高价跌幅过滤(至今/最低两种模式)
  - 实时日志流推送

启动:  python main.py  (或双击 启动.bat)
访问:  http://127.0.0.1:5188
"""
import asyncio
import datetime
import json
import os
import queue
import random
import re
import ssl
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

PORT = 5188
BASE_DIR = Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

app = FastAPI(title="A股智能选股", docs_url=None, redoc_url=None)

# ---------------- 静态文件 ----------------
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# ---------------- HTTP 请求工具 ----------------
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_url(url, decode="utf-8", timeout=30, retry=2):
    last_err = None
    ctx = _SSL_CTX if url.startswith("https") else None
    for _ in range(retry + 1):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        req.add_header("Accept", "*/*")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                raw = r.read()
                if decode:
                    return raw.decode(decode, errors="replace")
                return raw
        except Exception as e:
            last_err = e
            time.sleep(0.4)
    raise last_err


def fetch_json(url):
    return json.loads(fetch_url(url))


# ---------------- 腾讯行情请求(多域名回退) ----------------
# web.ifzq.gtimg.cn 的 fqkline 接口偶发 501 风控, 按顺序轮询多个可用域名
_TENCENT_HOSTS = [
    "https://ifzq.gtimg.cn",                     # 直连域名
    "https://proxy.finance.qq.com/ifzqgtimg",    # 官方代理域名
    "https://web.ifzq.gtimg.cn",                 # 原域名(偶发501)
]


def fetch_tencent(path):
    """腾讯行情接口请求, 多域名轮询回退"""
    last_err = None
    for host in _TENCENT_HOSTS:
        try:
            return fetch_json(host + path)
        except Exception as e:
            last_err = e
    raise last_err


# ---------------- 股票代码转换 ----------------
def _secid(code):
    code = (code or "").strip().lower()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code.startswith(("920", "4", "8")):
        return "bj" + code
    if code.startswith(("6", "9", "5")):
        return "sh" + code
    if code.startswith(("0", "1", "2", "3")):
        return "sz" + code
    return "sh" + code





# ---------------- 交易日历(简化版) ----------------
def _seek_trade_date(offset_days):
    d = datetime.date.today() - datetime.timedelta(days=offset_days)
    for _ in range(30):
        if d.weekday() < 5:
            return d.strftime("%Y-%m-%d")
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def latest_trade_date():
    return _seek_trade_date(0)


# ---------------- 东财智能选股 ----------------
def _xg_fp(n=32):
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def _xg_get(r, prefix):
    for k, v in r.items():
        if k == prefix or (isinstance(k, str) and k.startswith(prefix + "{")):
            return v
    return None


def em_xuangu(q, size=60, page=1):
    q = (q or "").strip()
    if not q:
        return {"rows": [], "total": 0, "msg": "请输入选股条件"}
    size = max(10, min(int(size or 60), 200))  # 默认60条/页, 上限200条
    page = max(1, int(page or 1))
    body = {
        "keywordNew": q, "pageSize": size, "pageNo": page,
        "fingerprint": _xg_fp(), "timestamp": int(time.time() * 1000),
        "requestId": _xg_fp(), "gids": [], "shareToGuba": False,
        "needShowStockNum": False, "client": "WEB",
    }
    req = urllib.request.Request(
        "https://np-tjxg-b.eastmoney.com/api/smart-tag/stock/v3/pw/search-code",
        data=json.dumps(body).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json",
                 "Referer": "https://xuangu.eastmoney.com/",
                 "Origin": "https://xuangu.eastmoney.com"},
        method="POST")
    j = json.loads(urllib.request.urlopen(req, timeout=20).read())
    res = ((j.get("data") or {}).get("result")) or {}
    dl = res.get("dataList") or []
    rows = []
    for r in dl:
        rows.append({
            "code": _xg_get(r, "SECURITY_CODE"),
            "name": _xg_get(r, "SECURITY_SHORT_NAME"),
            "price": _xg_get(r, "NEWEST_PRICE"),
            "pct": _xg_get(r, "CHG"),
            "turnover": _xg_get(r, "TURNOVER_RATE"),
            "qrr": _xg_get(r, "QRR"),
            "amount": _xg_get(r, "TRADING_VOLUMES"),
            "pe": _xg_get(r, "PE_DYNAMIC"),
            "total_value": _xg_get(r, "TOAL_MARKET_VALUE<140>"),
            "float_value": _xg_get(r, "CIRCULATION_MARKET_VALUE<140>"),
        })
    total = res.get("total") or len(rows)
    pages = max(1, (total + size - 1) // size)
    return {"q": q, "total": total, "page": page, "pages": pages,
            "size": size, "rows": rows,
            "msg": "东财智能解析 · 共 %d 只 · 第 %d/%d 页 · 每页 %d 只" % (
                total, page, pages, min(size, len(rows)))}


# ---------------- 腾讯 K线数据 ----------------
# 东财 K线 API 在加密机环境下被 SSL 代理拦截, 改用腾讯前复权 K线
_KLINE_CACHE = {}
_KLINE_LOCK = threading.Lock()
_KLINE_INFLIGHT = {}       # code -> threading.Event(该股票K线正在拉取中)
_KLINE_INFLIGHT_LOCK = threading.Lock()


def get_kline_data(code):
    """腾讯前复权日K(320根, 缓存1小时), 返回 {date: {open/close/high/low/volume/amplitude/turnover}}

    单飞: 同一股票只允许一个线程发起网络拉取, 其他线程轮询等待复用结果,
    避免预热(warmup)与过滤(filter)并发时重复请求。
    """
    sc = _secid(code)
    now_t = time.time()
    with _KLINE_LOCK:
        hit = _KLINE_CACHE.get(code)
        if hit and now_t - hit["ts"] < 3600:
            return hit["rows"]

    # 单飞: 已有线程在拉取该股票 -> 轮询等待其写入缓存
    with _KLINE_INFLIGHT_LOCK:
        ev = _KLINE_INFLIGHT.get(code)
        mine = False
        if ev is None:
            ev = threading.Event()
            _KLINE_INFLIGHT[code] = ev
            mine = True
    if not mine:
        for _ in range(60):  # 最多等约12秒
            if ev.wait(0.2):
                break
            with _KLINE_LOCK:
                hit = _KLINE_CACHE.get(code)
                if hit:
                    return hit["rows"]
        with _KLINE_LOCK:
            hit = _KLINE_CACHE.get(code)
            if hit:
                return hit["rows"]
        return {}

    try:
        url = ("/appstock/app/fqkline/get?param=%s,day,,,320,qfq" % sc)
        try:
            d = fetch_tencent(url)
        except Exception:
            return {}

        node = (d.get("data") or {}).get(sc) or {}
        key = "qfqday" if "qfqday" in node else "day"
        rows_raw = node.get(key) or []
        if not rows_raw:
            return {}

        rows = {}
        for it in rows_raw:
            if len(it) < 6:
                continue
            try:
                rows[it[0]] = {
                    "open": float(it[1]), "close": float(it[2]),
                    "high": float(it[3]), "low": float(it[4]),
                    "volume": float(it[5]), "amplitude": 0, "turnover": 0,
                }
            except (ValueError, IndexError):
                continue

        if rows:
            with _KLINE_LOCK:
                _KLINE_CACHE[code] = {"ts": time.time(), "rows": rows}
        return rows
    finally:
        with _KLINE_INFLIGHT_LOCK:
            _KLINE_INFLIGHT.pop(code, None)
        ev.set()  # 唤醒等待者


# ---------------- 个股行情(腾讯) ----------------
_QUOTE_CACHE = {}
_QUOTE_LOCK = threading.Lock()


def get_quote(code):
    """腾讯个股实时行情"""
    sc = _secid(code)
    now_t = time.time()
    with _QUOTE_LOCK:
        hit = _QUOTE_CACHE.get(code)
        if hit and now_t - hit["ts"] < 10:
            return hit["q"]
    try:
        raw = fetch_url("http://qt.gtimg.cn/q=" + sc, decode="gbk")
    except Exception:
        return {"error": "行情获取失败"}
    import re
    m = re.search(r'v_(\w+)="([^"]*)"', raw)
    if not m:
        return {"error": "未找到该股票"}
    f = m.group(2).split("~")
    if len(f) < 40 or not f[1]:
        return {"error": "未找到该股票"}

    def g(i, default="-"):
        return f[i] if i < len(f) and f[i] != "" else default

    q = {
        "code": g(2), "name": g(1), "price": g(3), "pre_close": g(4), "open": g(5),
        "volume": g(6), "amount": g(37), "turnover": g(38), "pe": g(39),
        "high": g(33), "low": g(34), "change": g(31), "pct": g(32),
        "amplitude": g(43), "float_value": g(44), "total_value": g(45),
        "pb": g(46), "limit_up": g(47), "limit_down": g(48), "vol_ratio": g(49),
        "avg": g(51), "time": g(30),
    }
    with _QUOTE_LOCK:
        _QUOTE_CACHE[code] = {"ts": time.time(), "q": q}
    return q


# ---------------- K线接口(腾讯, 前复权) ----------------
def api_kline(code, period="day", count=320):
    """历史K线 - 腾讯前复权, 支持 day/week/month"""
    sc = _secid(code)
    p = {"day": "day", "week": "week", "month": "month"}.get(period, "day")
    n = max(60, min(int(count or 320), 800))
    try:
        d = fetch_tencent("/appstock/app/fqkline/get?param=%s,%s,,,%d,qfq" % (sc, p, n))
    except Exception:
        return {"error": "K线获取失败"}
    node = (d.get("data") or {}).get(sc) or {}
    key = "qfq" + p if "qfq" + p in node else p
    rows = node.get(key) or []
    klines = []
    for it in rows:
        if len(it) < 6:
            continue
        klines.append({"date": it[0], "open": float(it[1]), "close": float(it[2]),
                       "high": float(it[3]), "low": float(it[4]), "volume": float(it[5])})
    name = (node.get("qt") or {}).get(sc, [None, ""])[1] if isinstance(node.get("qt"), dict) else ""
    return {"code": sc, "period": p, "name": name, "klines": klines}


# ---------------- 筹码分布(基于腾讯日K) ----------------
def api_chips(code, date):
    """筹码分布(通达信式三角分布, 基于腾讯前复权日K)

    从目标日起往前累计至多 120 个交易日的成交量, 每日成交量按
    三角形分布(峰值在当日均价附近)分配到 [最低, 最高] 区间,
    汇总为价格-筹码直方图, 并计算平均成本/90%与70%成本区间/获利盘。
    """
    rows = get_kline_data(code)
    if not rows:
        return {"error": "筹码数据获取失败"}
    dates = sorted(rows)
    target = date if date in rows else dates[-1]
    idx = dates.index(target)
    hist = [rows[d] for d in dates[max(0, idx - 119): idx + 1]]
    lo = min(r["low"] for r in hist)
    hi = max(r["high"] for r in hist)
    if hi <= lo:
        return {"error": "数据异常"}
    nb = 80
    step = (hi - lo) / nb
    bins = [0.0] * nb
    for r in hist:
        v = r["volume"]
        if v <= 0 or r["high"] <= r["low"]:
            continue
        a, b = r["low"], r["high"]
        mid = (a + b) / 2.0
        half = (b - a) / 2.0
        tot = 0.0
        fracs = []
        for i in range(12):  # 每日区间采样12份近似三角分布
            p = a + (b - a) * (i + 0.5) / 12.0
            w = 1.0 - abs(p - mid) / half
            w = max(w, 0.05)
            fracs.append((p, w))
            tot += w
        for p, w in fracs:
            bi = int((p - lo) / step)
            if 0 <= bi < nb:
                bins[bi] += v * w / tot
    total = sum(bins)
    if total <= 0:
        return {"error": "筹码计算失败"}
    prices = [lo + (i + 0.5) * step for i in range(nb)]
    avg = sum(p * b for p, b in zip(prices, bins)) / total
    acc = 0.0

    def frac(f):
        nonlocal acc
        acc = 0.0
        for i, b in enumerate(bins):
            acc += b / total
            if acc >= f:
                return prices[i]
        return prices[-1]

    c90 = [frac(0.05), frac(0.95)]
    c70 = [frac(0.15), frac(0.85)]
    close = rows[target]["close"]
    profit = sum(b for p, b in zip(prices, bins) if p <= close) / total * 100.0
    c90_conc = ((c90[1] - c90[0]) / (c90[1] + c90[0]) * 100.0) if (c90[1] + c90[0]) else 0.0
    return {"code": code, "date": target, "close": close,
            "bins": [[round(p, 3), round(b, 2)] for p, b in zip(prices, bins)],
            "avg_cost": round(avg, 3),
            "c90": [round(c90[0], 3), round(c90[1], 3)],
            "c70": [round(c70[0], 3), round(c70[1], 3)],
            "c90_conc": round(c90_conc, 2),
            "profit_ratio": round(profit, 2)}


# ---------------- 分时接口(腾讯) ----------------
def api_minute(code, date=""):
    """分时数据 - 腾讯(当日或近5个交易日历史)"""
    sc = _secid(code)
    if date:
        # 历史分时: 腾讯 day/query 提供近5个交易日分时, 按日期过滤
        try:
            d = fetch_tencent("/appstock/app/day/query?code=" + sc)
        except Exception:
            return {"error": "分时获取失败"}
        node = (d.get("data") or {}).get(sc) or {}
        days = node.get("data") or []
        qdate = (date or "").replace("-", "")
        day_node = None
        for it in days:
            if isinstance(it, dict) and it.get("date") == qdate:
                day_node = it
                break
        if not day_node and days:
            day_node = days[-1]
        if not day_node:
            return {"error": "该日期无分时数据(仅支持近5个交易日)"}
        lines = day_node.get("data") or []
        qt = node.get("qt") or {}
        qt = qt.get(sc) or []
        pre_close = None
        # 腾讯 day/query 无昨收, 从日K推算
        try:
            krows = get_kline_data(code)
            ds = sorted(krows)
            target = qdate if qdate in krows else ds[-1]
            i = ds.index(target)
            if i > 0:
                pre_close = krows[ds[i - 1]]["close"]
            else:
                pre_close = krows[target]["open"]
        except Exception:
            pre_close = None
        points = []
        for ln in lines:
            parts = ln.split()
            if len(parts) >= 2:
                points.append({"t": parts[0], "price": float(parts[1]),
                               "volume": float(parts[2]) if len(parts) > 2 else 0})
        avgs = []
        for ln in lines:
            parts = ln.split()
            if len(parts) >= 4:
                try:
                    amt2 = float(parts[3])
                    vol = float(parts[2])
                    avgs.append(amt2 / vol if vol else None)
                except (ValueError, ZeroDivisionError):
                    avgs.append(None)
            else:
                avgs.append(None)
        return {"code": sc, "date": qdate, "pre_close": pre_close,
                "points": points, "avgs": avgs}
    # 当日分时
    try:
        d = fetch_tencent("/appstock/app/minute/query?code=" + sc)
    except Exception:
        return {"error": "分时获取失败"}
    node = (d.get("data") or {}).get(sc) or {}
    data = node.get("data") or {}
    lines = data.get("data") or []
    points = []
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 2:
            points.append({"t": parts[0], "price": float(parts[1]),
                           "volume": float(parts[2]) if len(parts) > 2 else 0})
    qt = node.get("qt") or {}
    qt = qt.get(sc) or []
    pre_close = float(qt[4]) if len(qt) > 4 else None
    # 均价 = 累计额/累计量(腾讯第4字段为累计额)
    avgs = []
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 4:
            try:
                amt2 = float(parts[3])
                vol = float(parts[2])
                avgs.append(amt2 / vol if vol else None)
            except (ValueError, ZeroDivisionError):
                avgs.append(None)
        else:
            avgs.append(None)
    return {"code": sc, "date": data.get("date", ""), "pre_close": pre_close,
            "points": points, "avgs": avgs}


# ---------------- 个股行情/K线/分时/筹码(腾讯) ----------------
# K线弹窗数据源: 本机环境下东财 K线 API 被 SSL 代理拦截(见 get_kline_data 注释),
# 行情/K线/分时走腾讯, 筹码分布改用腾讯前复权日K计算, 与K线主图价格体系同源对齐。
def em_quote(code):
    """个股实时行情 - 腾讯完整格式"""
    sc = _secid(code)
    try:
        raw = fetch_url("http://qt.gtimg.cn/q=" + sc, decode="gbk")
    except Exception:
        return {"error": "行情获取失败"}
    m = re.search(r'v_(\w+)="([^"]*)"', raw)
    if not m:
        return {"error": "未找到该股票"}
    f = m.group(2).split("~")
    if len(f) < 40 or not f[1]:
        return {"error": "未找到该股票"}

    def g(i, default="-"):
        return f[i] if i < len(f) and f[i] != "" else default

    return {
        "code": g(2), "name": g(1), "price": g(3), "pre_close": g(4), "open": g(5),
        "volume": g(6), "amount": g(37), "turnover": g(38), "pe": g(39),
        "high": g(33), "low": g(34), "change": g(31), "pct": g(32),
        "amplitude": g(43), "float_value": g(44), "total_value": g(45),
        "pb": g(46), "limit_up": g(47), "limit_down": g(48), "vol_ratio": g(49),
        "avg": g(51), "time": g(30),
    }


def em_kline(code, period="day"):
    """历史K线 - 腾讯前复权(day/week/month, 320根)"""
    sc = _secid(code)
    p = {"day": "day", "week": "week", "month": "month"}.get(period, "day")
    try:
        d = fetch_tencent("/appstock/app/fqkline/get?param=%s,%s,,,320,qfq" % (sc, p))
    except Exception:
        return {"error": "K线获取失败"}
    node = (d.get("data") or {}).get(sc) or {}
    key = "qfq" + p if ("qfq" + p) in node else p
    rows = node.get(key) or []
    klines = []
    for it in rows:
        if len(it) < 6:
            continue
        try:
            klines.append({"date": it[0], "open": float(it[1]),
                           "close": float(it[2]), "high": float(it[3]),
                           "low": float(it[4]), "volume": float(it[5])})
        except (ValueError, IndexError):
            continue
    return {"code": sc, "period": p, "klines": klines}


def em_minute(code):
    """分时数据 - 腾讯(当日)"""
    sc = _secid(code)
    try:
        d = fetch_tencent("/appstock/app/minute/query?code=" + sc)
    except Exception:
        return {"error": "分时获取失败"}
    node = (d.get("data") or {}).get(sc) or {}
    data = node.get("data") or {}
    lines = data.get("data") or []
    points = []
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 2:
            try:
                points.append({"t": parts[0], "price": float(parts[1]),
                               "volume": float(parts[2]) if len(parts) > 2 else 0})
            except ValueError:
                continue
    qt = node.get("qt") or {}
    qt = qt.get(sc) or []
    pre_close = float(qt[4]) if len(qt) > 4 else None
    # 均价 = 累计额/累计量(腾讯第4字段为累计额)
    avgs = []
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 4:
            try:
                amt_v = float(parts[3])
                vol = float(parts[2])
                avgs.append(amt_v / vol if vol else None)
            except (ValueError, ZeroDivisionError):
                avgs.append(None)
        else:
            avgs.append(None)
    return {"code": sc, "date": data.get("date", ""), "pre_close": pre_close,
            "points": points, "avgs": avgs}


def em_chips(code, date):
    """筹码分布(通达信式三角分布, 基于腾讯前复权日K)

    从目标日起往前累计至多 120 个交易日的成交量, 每日成交量按
    三角形分布(峰值在当日均价附近)分配到 [最低, 最高] 区间,
    汇总为价格-筹码直方图, 并计算平均成本/90%与70%成本区间/获利盘。
    腾讯前复权日K与K线主图同源, 成本线可直接投影到主图价格轴。
    """
    sc = _secid(code)
    rows = get_kline_data(code)
    if not rows:
        return {"error": "筹码数据获取失败"}
    dates = sorted(rows)
    target = date if date in rows else dates[-1]
    idx = dates.index(target)
    hist = [rows[d] for d in dates[max(0, idx - 119): idx + 1]]
    lo = min(r["low"] for r in hist)
    hi = max(r["high"] for r in hist)
    if hi <= lo:
        return {"error": "数据异常"}
    nb = 80
    step = (hi - lo) / nb
    bins = [0.0] * nb
    for r in hist:
        v = r["volume"]
        if v <= 0 or r["high"] <= r["low"]:
            continue
        a, b = r["low"], r["high"]
        mid = (a + b) / 2.0
        half = (b - a) / 2.0
        tot = 0.0
        fracs = []
        for i in range(12):  # 每日区间采样12份近似三角分布
            p = a + (b - a) * (i + 0.5) / 12.0
            w = 1.0 - abs(p - mid) / half
            w = max(w, 0.05)
            fracs.append((p, w))
            tot += w
        for p, w in fracs:
            bi = int((p - lo) / step)
            if 0 <= bi < nb:
                bins[bi] += v * w / tot
    total = sum(bins)
    if total <= 0:
        return {"error": "筹码计算失败"}
    prices = [lo + (i + 0.5) * step for i in range(nb)]
    avg = sum(p * b for p, b in zip(prices, bins)) / total
    acc = 0.0

    def frac(f):
        nonlocal acc
        acc = 0.0
        for i, b in enumerate(bins):
            acc += b / total
            if acc >= f:
                return prices[i]
        return prices[-1]

    c90 = [frac(0.05), frac(0.95)]
    c70 = [frac(0.15), frac(0.85)]
    close = rows[target]["close"]
    profit = sum(b for p, b in zip(prices, bins) if p <= close) / total * 100.0
    c90_conc = ((c90[1] - c90[0]) / (c90[1] + c90[0]) * 100.0) if (c90[1] + c90[0]) else 0.0
    return {"code": sc, "date": target, "close": close,
            "bins": [[round(p, 3), round(b, 2)] for p, b in zip(prices, bins)],
            "avg_cost": round(avg, 3),
            "c90": [round(c90[0], 3), round(c90[1], 3)],
            "c70": [round(c70[0], 3), round(c70[1], 3)],
            "c90_conc": round(c90_conc, 2),
            "profit_ratio": round(profit, 2)}


# ---------------- 第二段: 跌幅过滤 ----------------
def _filter_one(code, months, drop_pct, mode, today_str, cutoff):
    """单只股票跌幅过滤, 返回 (log, result)"""
    log = {"code": code, "type": "info", "text": ""}
    try:
        klines = get_kline_data(code)
        if not klines:
            log["type"] = "warn"
            log["text"] = "[%s] K线数据获取失败, 跳过" % code
            return log, {"code": code, "name": "", "pass": False,
                         "high": None, "low": None, "today": None,
                         "drop_pct": None, "reason": "K线数据获取失败"}

        dates = sorted(klines.keys())
        in_range = [d for d in dates if cutoff <= d <= today_str]
        if not in_range:
            log["type"] = "warn"
            log["text"] = "[%s] 无 %d 个月内K线数据, 跳过" % (code, months)
            return log, {"code": code, "name": "", "pass": False,
                         "high": None, "low": None, "today": None,
                         "drop_pct": None, "reason": "无该时间段K线数据"}

        range_high = max(klines[d]["high"] for d in in_range)
        range_low = min(klines[d]["low"] for d in in_range)

        latest_close = None
        for d in reversed(dates):
            if d <= today_str:
                latest_close = klines[d]["close"]
                break
        if latest_close is None:
            latest_close = klines[dates[-1]]["close"]

        if mode == "至今":
            drop = (latest_close - range_high) / range_high * 100
        else:
            drop = (range_low - range_high) / range_high * 100

        passed = drop <= drop_pct

        if passed:
            log["type"] = "pass"
            log["text"] = ("[%s] %s个月内最高价 %.2f, %s价 %.2f, 跌幅 %.2f%%, "
                           "超过 %.0f%%, 筛选通过 ✓") % (
                code, months, range_high,
                "今日" if mode == "至今" else "最低",
                latest_close if mode == "至今" else range_low,
                drop, drop_pct)
        else:
            log["type"] = "fail"
            log["text"] = ("[%s] %s个月内最高价 %.2f, %s价 %.2f, 跌幅 %.2f%%, "
                           "未达到 %.0f%%, 未通过") % (
                code, months, range_high,
                "今日" if mode == "至今" else "最低",
                latest_close if mode == "至今" else range_low,
                drop, drop_pct)

        return log, {
            "code": code, "name": "", "pass": passed,
            "high": round(range_high, 2),
            "low": round(range_low, 2),
            "today": round(latest_close, 2) if latest_close else None,
            "drop_pct": round(drop, 2),
            "reason": "",
        }
    except Exception as e:
        log["type"] = "error"
        log["text"] = "[%s] 计算异常: %s" % (code, str(e))
        return log, {"code": code, "name": "", "pass": False,
                     "high": None, "low": None, "today": None,
                     "drop_pct": None, "reason": str(e)}


def _do_filter(codes, months, drop_pct, mode, out_q):
    """在独立线程中并发执行过滤, 结果通过 queue 推送给 SSE

    每只股票一次腾讯K线请求, 改为多线程并发拉取(最多10并发),
    20只当前页股票约1~2秒完成; 已缓存的K线(1小时TTL)直接命中内存。
    """
    today_str = latest_trade_date()
    cutoff = (datetime.date.today() - datetime.timedelta(days=int(months) * 30)).strftime("%Y-%m-%d")
    results = []
    workers = min(10, max(1, len(codes)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        # ex.map 按输入顺序返回, 保证日志与结果顺序稳定
        for log, res in ex.map(
                lambda c: _filter_one(c, months, drop_pct, mode, today_str, cutoff),
                codes):
            results.append(res)
            out_q.put(log)

    out_q.put({"type": "done", "results": results})
    out_q.put(None)  # 结束信号


# ---------------- API 端点 ----------------
@app.post("/api/xuangu")
async def api_xuangu(request: Request):
    data = await request.json()
    q = data.get("q", "MACD金叉 非ST")
    size = data.get("size", 60)
    page = data.get("page", 1)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, em_xuangu, q, size, page)
    return result


@app.get("/api/quote")
def api_quote(code: str = Query("")):
    """个股实时行情(腾讯)"""
    return em_quote(code)


@app.get("/api/kline")
def api_kline(code: str = Query(""), period: str = Query("day")):
    """历史K线(腾讯前复权)"""
    return em_kline(code, period)


@app.get("/api/minute")
def api_minute(code: str = Query("")):
    """分时数据(腾讯)"""
    return em_minute(code)


@app.get("/api/chips")
def api_chips(code: str = Query(""), date: str = Query("")):
    """筹码分布(基于腾讯前复权日K计算)"""
    return em_chips(code, date)


@app.get("/api/warmup")
def api_warmup(codes: str = Query("")):
    """后台预热K线缓存(立即返回), 选股列表加载后调用, 过滤时即可命中缓存"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()][:100]
    if code_list:
        def _warm():
            workers = min(8, len(code_list))
            try:
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    list(ex.map(get_kline_data, code_list))
            except Exception:
                pass
        threading.Thread(target=_warm, daemon=True).start()
    return {"ok": True, "count": len(code_list)}


@app.get("/api/filter")
async def api_filter_stream(
    codes: str = Query(""),
    months: int = Query(3),
    drop_pct: float = Query(-30),
    mode: str = Query("至今"),
):
    """SSE 流式推送过滤进度"""
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    out_q = queue.Queue()

    # 在独立线程中执行过滤
    t = threading.Thread(target=_do_filter,
                         args=(code_list, months, drop_pct, mode, out_q),
                         daemon=True)
    t.start()

    async def generate():
        while True:
            try:
                item = await asyncio.get_event_loop().run_in_executor(
                    None, out_q.get, True, 5)
            except queue.Empty:
                # 超时, 发心跳
                yield "data: {}\n\n"
                continue
            if item is None:
                break
            yield "data: %s\n\n" % json.dumps(item, ensure_ascii=False)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    print("=" * 50)
    print("  A股智能选股 Web 服务")
    print("  地址: http://127.0.0.1:%d" % PORT)
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")