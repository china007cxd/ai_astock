# -*- coding: utf-8 -*-
"""
A股复盘看盘 Web 应用 - 后端服务
================================
纯 Python 标准库实现，无需安装任何第三方依赖。

功能:
  - 代理各大行情数据源接口(同花顺/选股宝/东方财富/财联社/短线侠/堆书/腾讯)
  - 解决浏览器跨域限制
  - 数据归一化、缓存、失败重试

启动:  python server.py  (或双击 启动.bat)
访问:  http://127.0.0.1:8765
"""
import datetime
import json
import os
import random
import re
import threading
import time
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html.parser import HTMLParser

PORT = 8765
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 文件路径基于脚本目录, 不受启动目录影响
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")

# ---------------- 缓存 ----------------
_cache = {}
_cache_lock = threading.Lock()


def cached(key, ttl, fn):
    """带 TTL 的简单缓存"""
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    val = fn()
    with _cache_lock:
        _cache[key] = (time.time(), val)
    return val


# ---------------- HTTP 请求 ----------------
def fetch(url, decode="utf-8", timeout=8, retry=2):
    """GET 请求，自动重试"""
    last_err = None
    for _ in range(retry + 1):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        req.add_header("Accept", "*/*")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if decode:
                    return raw.decode(decode, errors="replace")
                return raw
        except Exception as e:  # noqa
            last_err = e
            time.sleep(0.4)
    raise last_err


def fetch_json(url):
    return json.loads(fetch(url))


# ---------------- 工具 ----------------
def today():
    return time.strftime("%Y-%m-%d")


def yesterday():
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))


def compact_date(s):
    return (s or "").replace("-", "")


# ---------------- 交易日历 ----------------
# 法定节假日数据来自 Timor 节假日公开接口(http://timor.tech/api/holiday/year/2026):
#   holiday=true   -> 法定假日(休市)
#   holiday=false  -> 调休补班(周六日也要开市)
# 拉取成功后落盘 trade_calendar.json, 下次启动离线可用; 拉取失败降级为仅周末判断。
_CAL_FILE = os.path.join(BASE_DIR, "trade_calendar.json")
_HOLIDAYS = {}  # {year: {"YYYY-MM-DD": {"holiday": bool, "name": str}}}


def _load_calendar():
    try:
        with open(_CAL_FILE, encoding="utf-8") as f:
            _HOLIDAYS.update(json.load(f))
    except Exception:
        pass


def _save_calendar():
    try:
        with open(_CAL_FILE, "w", encoding="utf-8") as f:
            json.dump(_HOLIDAYS, f, ensure_ascii=False)
    except Exception:
        pass


def _fetch_holidays(year):
    """拉取某年法定节假日表"""
    try:
        j = fetch_json("http://timor.tech/api/holiday/year/%d" % year)
        out = {}
        for mmdd, info in (j.get("holiday") or {}).items():
            if isinstance(info, dict):
                out["%d-%s" % (year, mmdd)] = {
                    "holiday": bool(info.get("holiday")),
                    "name": info.get("name", ""),
                }
        return out
    except Exception:
        return {}


def holidays_of(year):
    """某年节假日表(内存缓存 + 本地文件兜底)"""
    year = int(year)
    if year not in _HOLIDAYS:
        _HOLIDAYS[year] = _fetch_holidays(year)
        _save_calendar()
    return _HOLIDAYS.get(year) or {}


def is_trade_date(d):
    """判断 yyyy-mm-dd 是否为交易日"""
    try:
        dt = datetime.datetime.strptime(str(d)[:10], "%Y-%m-%d")
    except ValueError:
        return False
    key = dt.strftime("%Y-%m-%d")
    info = holidays_of(dt.year).get(key)
    if info is not None:
        return not info["holiday"]  # 法定假日休市, 调休补班照常开市
    return dt.weekday() < 5


def _seek_trade_date(offset_days):
    """从今天往回(offset_days 起步)找最近一个交易日"""
    d = datetime.date.today() - datetime.timedelta(days=offset_days)
    for _ in range(30):
        if is_trade_date(d.strftime("%Y-%m-%d")):
            return d.strftime("%Y-%m-%d")
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def latest_trade_date():
    """最近交易日(含今天, 涨停池等盘中即有数据的面板用)"""
    return _seek_trade_date(0)


def prev_trade_date():
    """上一交易日(严格早于今天, 龙虎榜等盘后发布的面板用)"""
    return _seek_trade_date(1)


def api_trade_dates(year):
    """全年交易日历: days={'MM-DD': {'t': 是否交易日, 'h': 节假日名}}"""
    if not str(year).isdigit():
        year = datetime.date.today().year
    year = int(year)
    hl = holidays_of(year)
    days = {}
    for mm in range(1, 13):
        for dd in range(1, 32):
            try:
                d = datetime.date(year, mm, dd)
            except ValueError:
                continue
            key = d.strftime("%m-%d")
            info = hl.get(d.strftime("%Y-%m-%d"))
            t = (not info["holiday"]) if info else (d.weekday() < 5)
            days[key] = {"t": t, "h": (info or {}).get("name", "")}
    return {"year": year, "latest": latest_trade_date(),
            "prev": prev_trade_date(), "days": days}


_load_calendar()


def fmt_amount(v):
    """金额格式化: 12345.6万 -> 1.23亿"""
    if v is None or v == "-":
        return "-"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(v) >= 1e8:
        return "%.2f亿" % (v / 1e8)
    if abs(v) >= 1e4:
        return "%.0f万" % (v / 1e4)
    return "%.0f" % v


# ================= 数据源适配器 =================

def api_indices():
    """大盘指数 - 腾讯行情(GBK) + 东财涨跌家数"""
    idx = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300",
           "sh000905", "sh000852", "bj899050"]
    raw = fetch("http://qt.gtimg.cn/q=" + ",".join("s_" + i for i in idx), decode="gbk")
    items = []
    for line in raw.strip().splitlines():
        m = re.search(r'v_(\w+)="([^"]*)"', line)
        if not m:
            continue
        f = m.group(2).split("~")
        if len(f) < 6:
            continue
        items.append({
            "code": f[2],
            "name": f[1],
            "price": f[3],
            "change": f[4],
            "pct": f[5],
            "volume": f[6] if len(f) > 6 else "-",
            "amount": f[7] if len(f) > 7 else "-",
        })
    # 涨跌家数(东财 push2delay)
    up = down = flat = "-"
    try:
        d = fetch_json("https://push2delay.eastmoney.com/api/qt/ulist.np/get"
                       "?fltt=2&secids=1.000001&fields=f104,f105,f106")
        diff = ((d.get("data") or {}).get("diff") or [{}])[0]
        up, down, flat = diff.get("f104", "-"), diff.get("f105", "-"), diff.get("f106", "-")
    except Exception:
        pass
    return {"time": time.strftime("%H:%M:%S"), "items": items,
            "up": up, "down": down, "flat": flat}


def api_limit_up(date):
    """涨停池 - 同花顺"""
    d = date or latest_trade_date()
    url = ("https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool"
           "?page=1&limit=200&filter=HS,GEM2STAR&order_field=133970&order_type=0"
           "&field=199112,10,9001,330323,330324,330325,9002,330329,133971,133970,"
           "1968584,3475914,9003,9004&date=%s" % compact_date(d))
    data = fetch_json(url).get("data", {}) or {}
    rows = []
    for it in (data.get("info") or []):
        rows.append({
            "code": it.get("code"),
            "name": it.get("name"),
            "high_days": it.get("high_days"),          # 连板
            "ltype": it.get("limit_up_type"),          # 涨停类型
            "first_time": it.get("first_limit_up_time"),  # 首封时间(秒级时间戳)
            "last_time": it.get("last_limit_up_time"),
            "amount": fmt_amount(it.get("order_amount")),   # 封单额
            "order_amount": it.get("order_amount"),        # 原始值(排序用)
            "reason": it.get("reason_type"),           # 涨停原因
            "pct": it.get("change_rate"),              # 涨幅
            "turnover": it.get("turnover_rate"),       # 换手
            "value": fmt_amount(it.get("currency_value")),  # 流通值
            "currency_value": it.get("currency_value"),     # 原始值(排序用)
            "price": it.get("latest"),                 # 现价
            "suc_rate": it.get("limit_up_suc_rate"),   # 涨停成功率
            "again": it.get("is_again_limit"),         # 是否回封
            "preview": it.get("time_preview") or [],   # 分时涨幅
            "market": it.get("market_type"),
        })
    return {"date": d, "total": len(rows), "rows": rows}


def api_xgb(pool, date):
    """涨停池/破板池 - 选股宝"""
    d = date or latest_trade_date()
    url = ("https://flash-api.xuangubao.com.cn/api/pool/detail"
           "?pool_name=%s&date=%s" % (pool, d))
    try:
        data = fetch_json(url).get("data") or []
    except Exception:
        data = []
    if not data and d == latest_trade_date():
        # 当日数据尚未发布时回退到上一交易日
        yd = prev_trade_date()
        try:
            data = fetch_json("https://flash-api.xuangubao.com.cn/api/pool/detail"
                              "?pool_name=%s&date=%s" % (pool, yd)).get("data") or []
        except Exception:
            data = []
        if data:
            d = yd
    rows = []
    for it in data:
        surge = it.get("surge_reason") or {}
        plates = surge.get("related_plates") or []
        rows.append({
            "code": it.get("symbol"),
            "name": it.get("stock_chi_name"),
            "high_days": it.get("limit_up_days") or it.get("m_days_n_boards_days"),
            "pct": it.get("change_percent"),
            "first_time": it.get("first_limit_up"),
            "last_time": it.get("last_limit_up"),
            "break_times": it.get("break_limit_up_times"),
            "break_down_times": it.get("break_limit_down_times"),
            "break_time": it.get("first_break_limit_up") or it.get("last_break_limit_up"),
            "turnover": it.get("turnover_ratio"),
            "reason": surge.get("stock_reason") or "、".join(
                p.get("plate_name", "") + ":" + p.get("plate_reason", "") for p in plates),
        })
    return {"date": d, "total": len(rows), "rows": rows}


def api_ladder():
    """涨跌停统计 + 连板梯队 + 板块涨停 - 财联社"""
    url = "https://x-quote.cls.cn/v2/quote/a/plate/up_down_analysis"
    try:
        data = fetch_json(url).get("data") or {}
    except Exception:
        data = {}
    # 连板梯队
    ladder = []
    for grp in (data.get("continuous_limit_up") or []):
        ladder.append({
            "height": grp.get("height"),
            "stocks": [{"code": s.get("secu_code"), "name": s.get("secu_name")}
                       for s in (grp.get("stock_list") or [])],
        })
    # 板块涨停
    plates = []
    for p in (data.get("plate_stock") or []):
        plates.append({
            "name": p.get("secu_name"),
            "change": p.get("change"),
            "up_num": p.get("plate_stock_up_num"),
            "reason": p.get("up_reason"),
            "stocks": [{"code": s.get("secu_code"), "name": s.get("secu_name")}
                       for s in (p.get("stock_list") or [])],
        })
    limit_up = sum(len(g.get("stocks") or []) for g in ladder)
    return {
        "time": time.strftime("%H:%M:%S"),
        "limit_up": limit_up,
        "limit_down": data.get("limit_down", "-"),
        "broken_count": data.get("broken_limit_up", "-"),
        "ladder": sorted(ladder, key=lambda x: -(x["height"] or 0)),
        "plates": plates,
        "raw_stats": data,
    }


def api_hot_plate():
    """热门板块 - 同花顺"""
    url = "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_plate/concept/data.txt"
    try:
        data = fetch_json(url).get("data", {}) or {}
    except Exception:
        data = {}
    rows = []
    for it in (data.get("plate_list") or []):
        rows.append({
            "code": it.get("code"),
            "name": it.get("name"),
            "order": it.get("order"),
            "rate": it.get("rate"),
            "tag": it.get("tag"),
            "hot_tag": it.get("hot_tag"),
            "etf": it.get("etf_name"),
            "etf_code": it.get("etf_product_id"),
        })
    return {"time": time.strftime("%H:%M:%S"), "total": len(rows), "rows": rows}


def api_lhb(date):
    """龙虎榜 - 龙虎VIP"""
    d = date or prev_trade_date()
    token = "d336f47db0d11c37400313830329564e"
    uid = "1973778"
    url = ("https://applhb.longhuvip.com/w1/api/index.php?st=200&a=GetStockList"
           "&c=LongHuBang&PhoneOSNew=1&Token=%s&Time=%s&Index=0&Type=2&UserID=%s"
           % (token, d, uid))
    try:
        data = fetch_json(url)
    except Exception:
        data = {}
    rows = []
    for it in (data.get("list") or []):
        rows.append({
            "code": it.get("ID"),
            "name": it.get("Name"),
            "pct": it.get("IncreaseAmount"),
            "buy_in": fmt_amount(it.get("BuyIn")),        # 净买额
            "join_num": it.get("JoinNum"),                # 上榜机构数
            "turnover": fmt_amount(it.get("Turnover")),   # 成交额
            "circ_value": fmt_amount(it.get("CircPrice")),  # 流通市值
            "amplitude": it.get("Amplitude"),             # 振幅
            "turnover_ratio": it.get("TurnoverRatio"),    # 换手率
            "capital": fmt_amount(it.get("Capitalization")),
            "reason": it.get("D3"),
        })
    return {"date": d, "rows": rows}


def api_bidding():
    """竞价封单 - 短线侠"""
    url = "https://duanxianxia.com/api/getFengdanLast"
    try:
        data = fetch_json(url)
    except Exception:
        data = {}
    if not data:
        return {"rows": [], "date": "", "t15": "-", "t20": "-", "t25": "-"}
    date = sorted(data.keys())[-1]
    d = data[date]
    rows = parse_bidding_html(d.get("table", ""))
    return {"date": date, "t15": d.get("t15", "-"), "t20": d.get("t20", "-"),
            "t25": d.get("t25", "-"), "rows": rows}


class _BidParser(HTMLParser):
    """解析短线侠封单内嵌 HTML 表格"""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.cur = None
        self.in_b = False
        self.in_i = False
        self.in_span = False
        self.buf = []
        self.tags = []
        self.spans = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and "code" in a:
            self.cur = {"code": a["code"], "name": "", "tags": [], "amounts": []}
        elif tag == "b":
            self.in_b = True
            self.buf = []
        elif tag == "i" and self.cur is not None:
            # <i> 之前缓冲的文本即为股票名称
            self.cur["name"] = "".join(self.buf).strip()
            self.in_i = True
            self.tags = []
            self.buf = []
        elif tag == "p" and self.in_i:
            self.buf = []
        elif tag == "span" and self.cur is not None:
            self.in_span = True
            self.buf = []

    def handle_data(self, txt):
        if self.cur is None:
            return
        if self.in_b and not self.in_i:
            self.buf.append(txt)
        elif self.in_i:
            self.buf.append(txt)
        elif self.in_span:
            self.buf.append(txt)

    def handle_endtag(self, tag):
        if self.cur is None:
            return
        if tag == "b":
            if not self.cur["name"]:
                self.cur["name"] = "".join(self.buf).strip()
            self.in_b = False
        elif tag == "p" and self.in_i:
            t = "".join(self.buf).strip()
            if t:
                self.tags.append(t)
        elif tag == "i":
            self.cur["tags"] = self.tags
            self.in_i = False
        elif tag == "span":
            self.cur["amounts"].append("".join(self.buf).strip())
            self.in_span = False
        elif tag == "td":
            self.rows.append(self.cur)
            self.cur = None


def parse_bidding_html(html):
    p = _BidParser()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.rows


def api_duishu(date, ptype, page, size):
    """盯盘 - 堆书(涨停/跌停/强势股/潜力榜/曾涨停/曾跌停/试盘)"""
    url = ("https://api.duishu.com/lhbapp/zhangting/index?pagecount=%d&page=%d"
           "&type=%s&apiversion=8.9&device_id=wuxiao20fb7a24-6420-46f3-b104"
           "-4f3ff8ec15dc&dxwappid=dxw88888" % (size, page, ptype))
    try:
        data = fetch_json(url).get("data") or {}
    except Exception:
        data = {}
    return {
        "date": data.get("date", date),
        "date_list": data.get("date_list") or [],
        "title": data.get("title", ""),
        "sum_list": data.get("sum_list") or [],
        "baopan": data.get("baopan") or [],
        "tab_list": data.get("tab_list") or [],
        "stock_list": data.get("stock_list") or {"head_info": [], "list": [], "multi": []},
    }


def api_market(sort, page, size):
    """全市场行情 - 东方财富(多主机轮询重试)"""
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"  # 沪深主板+创业板+科创板+北交所
    fields = "f2,f3,f5,f6,f8,f10,f12,f14,f20,f21,f62,f184"
    pn = max(1, min(page or 1, 100))
    pz = max(10, min(size or 50, 200))
    hosts = ["https://push2.eastmoney.com", "http://90.push2.eastmoney.com",
             "https://push2delay.eastmoney.com"]
    data = {}
    for host in hosts:
        url = (host + "/api/qt/clist/get?pn=%d&pz=%d&po=1&np=1"
               "&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=%s&fs=%s"
               "&fields=%s" % (pn, pz, sort or "f3", fs, fields))
        try:
            data = fetch_json(url).get("data") or {}
        except Exception:
            data = {}
        if (data.get("diff")):
            break
        time.sleep(0.3)
    diff = data.get("diff") or []
    if isinstance(diff, dict):
        diff = diff.get("diff") or []
    if not isinstance(diff, list):
        diff = []
    rows = []
    for it in diff:
        rows.append({
            "code": it.get("f12"),
            "name": it.get("f14"),
            "price": it.get("f2"),
            "pct": it.get("f3"),
            "volume": it.get("f5"),
            "amount": it.get("f6"),
            "turnover": it.get("f8"),
            "vol_ratio": it.get("f10"),
            "total_value": it.get("f20"),
            "float_value": it.get("f21"),
            "main_net": it.get("f62"),
            "main_pct": it.get("f184"),
        })
    total = data.get("total") or 0
    return {"total": total, "page": pn, "size": pz,
            "pages": (total + pz - 1) // pz if total else 0, "rows": rows}


def api_dates():
    """可用交易日列表(来自堆书)"""
    return cached("dates", 600, lambda: api_duishu("", "1", 1, 1).get("date_list") or [])


# ---------------- 个股相关(腾讯) ----------------
def _secid(code):
    """任意格式代码 -> 腾讯代码(sh600000/sz000001/bj830799)"""
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


def api_quote(code):
    """个股实时行情 - 腾讯完整格式"""
    sc = _secid(code)
    try:
        raw = fetch("http://qt.gtimg.cn/q=" + sc, decode="gbk")
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


# ---------------- 股票搜索 + 批量行情 ----------------
def _pinyin_first(ch):
    """汉字 -> 拼音首字母(GB2312 区位码分段), 非汉字原样返回"""
    try:
        b = ch.encode("gbk")
    except Exception:
        return ch
    if len(b) != 2:
        return ch
    code = (b[0] << 8) | b[1]
    segs = [
        (0xB0A1, 0xB0C4, "a"), (0xB0C5, 0xB2C0, "b"), (0xB2C1, 0xB4ED, "c"),
        (0xB4EE, 0xB6E9, "d"), (0xB6EA, 0xB7A1, "e"), (0xB7A2, 0xB8C0, "f"),
        (0xB8C1, 0xB9FD, "g"), (0xB9FE, 0xBBF6, "h"), (0xBBF7, 0xBFA5, "j"),
        (0xBFA6, 0xC0AB, "k"), (0xC0AC, 0xC2E7, "l"), (0xC2E8, 0xC4C2, "m"),
        (0xC4C3, 0xC5B5, "n"), (0xC5B6, 0xC5BD, "o"), (0xC5BE, 0xC6D9, "p"),
        (0xC6DA, 0xC8BA, "q"), (0xC8BB, 0xC8F5, "r"), (0xC8F6, 0xCBF9, "s"),
        (0xCBFA, 0xCDD9, "t"), (0xCDDA, 0xCEF3, "w"), (0xCEF4, 0xD188, "x"),
        (0xD189, 0xD4D0, "y"), (0xD4D1, 0xD7F9, "z"),
    ]
    for lo, hi, c in segs:
        if lo <= code <= hi:
            return c
    return ch  # GB2312 区外生僻字原样保留


def _py(name):
    """名称 -> 拼音首字母串(如 中国平安 -> zgpa)"""
    return "".join(_pinyin_first(ch) for ch in name)


_stock_cache = None  # {"list": [...], "ts": ...}
_stock_lock = threading.Lock()  # 拉取互斥, 防止并发请求重复拉取全量列表
_STOCK_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
_STOCK_FILE = os.path.join(BASE_DIR, "stock_list.json")  # 磁盘缓存: 重启后 24 小时内直接可用


def _stock_pages(host):
    """串行拉取该主机全部页(60 页 x 100 只), 任一页失败返回 None

    实测: pz>100 会被东财静默截断; 并发拉取易触发限流, 串行 60 页约 20-30 秒。
    """
    rows = []
    for pn in range(1, 61):
        url = (host + "/api/qt/clist/get?pn=%d&pz=100&po=1&np=1"
               "&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12"
               "&fs=%s&fields=f12,f14" % (pn, _STOCK_FS))
        diff = None
        for _ in range(2):  # 每页失败重试一次
            try:
                data = fetch_json(url).get("data") or {}
            except Exception:
                data = {}
                time.sleep(0.5)
                continue
            diff = data.get("diff") or []
            if isinstance(diff, dict):
                diff = diff.get("diff") or []
            if isinstance(diff, list) and diff:
                break
            diff = None
        if diff is None:
            return None  # 该页拉取失败, 整机结果弃用
        for it in diff:
            if it.get("f12") and it.get("f14"):
                rows.append({"code": it["f12"], "name": it["f14"],
                             "py": _py(it["f14"])})
    return rows


def _load_stock_disk():
    """读磁盘缓存(24 小时内有效)"""
    try:
        with open(_STOCK_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("list") and time.time() - d.get("ts", 0) < 86400:
            return d["list"]
    except Exception:
        pass
    return None


def _save_stock_disk(rows):
    try:
        with open(_STOCK_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "list": rows}, f,
                      ensure_ascii=False)
    except Exception:
        pass


def _stock_list():
    """全市场 A 股代码+名称(东财 clist 全量拉取)

    缓存优先级: 内存 1 小时 -> 磁盘 24 小时 -> 拉取。
    每主机独立完整拉取, 中途失败即弃用该主机结果换下一主机,
    避免缓存不完整列表(部分股票搜索不到); 拉取进行中时返回旧缓存。
    """
    global _stock_cache
    now = time.time()
    if _stock_cache and now - _stock_cache["ts"] < 3600:
        return _stock_cache["list"]
    # 内存未命中: 先试磁盘缓存(24h), 重启后立即可用无需等待预热
    disk = _load_stock_disk()
    if disk:
        _stock_cache = {"list": disk, "ts": time.time()}
        return disk
    if _stock_lock.locked():  # 已有请求在拉取, 先返回旧数据
        return _stock_cache["list"] if _stock_cache else []
    with _stock_lock:
        if _stock_cache and time.time() - _stock_cache["ts"] < 3600:
            return _stock_cache["list"]
        hosts = ["https://push2.eastmoney.com", "http://90.push2.eastmoney.com",
                 "https://push2delay.eastmoney.com"]
        for host in hosts:
            try:
                rows = _stock_pages(host)
            except Exception:
                rows = None
            if rows:
                _stock_cache = {"list": rows, "ts": time.time()}
                _save_stock_disk(rows)
                return rows
    # 网络全失败: 用磁盘缓存(24h)或旧内存缓存兜底
    disk = _load_stock_disk()
    if disk:
        _stock_cache = {"list": disk, "ts": time.time()}
        return disk
    return _stock_cache["list"] if _stock_cache else []


def _warm_stock_list():
    """后台预热全市场股票列表, 避免用户首次搜索长时间等待"""
    time.sleep(2)
    try:
        _stock_list()
    except Exception:
        pass


def api_search(q):
    """股票搜索: 代码前缀 / 名称包含 / 拼音首字母前缀"""
    q = (q or "").strip().lower()
    if not q:
        return {"rows": []}
    hit_code, hit_py, hit_name = [], [], []
    for it in _stock_list():
        code = it["code"]
        name = it["name"]
        if code.startswith(q):
            hit_code.append({"code": code, "name": name, "py": it["py"]})
        elif it["py"].startswith(q):
            hit_py.append({"code": code, "name": name, "py": it["py"]})
        elif q in name:
            hit_name.append({"code": code, "name": name, "py": it["py"]})
        if len(hit_code) >= 20:
            break
    return {"rows": (hit_code + hit_py + hit_name)[:20]}


def _quote_row(f):
    def g(i, default="-"):
        return f[i] if i < len(f) and f[i] != "" else default
    return {"code": g(2), "name": g(1), "price": g(3), "pct": g(32), "change": g(31)}


def api_quotes(codes):
    """批量实时行情 - 腾讯(q= 逗号分隔, 最多 60 只)"""
    cs = [c.strip() for c in (codes or "").split(",") if c.strip()][:60]
    if not cs:
        return {"rows": []}
    qs = ",".join(_secid(c) for c in cs)
    try:
        raw = fetch("http://qt.gtimg.cn/q=" + qs, decode="gbk")
    except Exception:
        return {"rows": []}
    rows = []
    for m in re.finditer(r'v_(\w+)="([^"]*)"', raw):
        f = m.group(2).split("~")
        if len(f) < 40 or not f[1]:
            continue
        rows.append(_quote_row(f))
    return {"rows": rows}


def api_kline(code, period, count):
    """历史K线 - 腾讯前复权"""
    sc = _secid(code)
    p = {"day": "day", "week": "week", "month": "month"}.get(period, "day")
    n = max(60, min(count or 320, 800))
    url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,%s,,,%d,qfq"
           % (sc, p, n))
    try:
        d = fetch_json(url)
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
    name = (d.get("data") or {}).get(sc, {}).get("qt", {}).get(sc, [None, ""])[1] if False else ""
    # 日K补充振幅/换手率(东财不复权, 按日期合并; 供十字光标与筹码联动展示)
    if p == "day":
        try:
            dq = _dfq_rows(code)
            for k in klines:
                r = dq.get(k["date"])
                if r:
                    k["amplitude"] = r["amplitude"]
                    k["turnover"] = r["turnover"]
        except Exception:
            pass
    return {"code": sc, "period": p, "name": name, "klines": klines}


def api_minute(code):
    """分时数据 - 腾讯"""
    sc = _secid(code)
    url = "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=" + sc
    try:
        d = fetch_json(url)
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
                amt = float(parts[3])
                vol = float(parts[2])
                avgs.append(amt / vol if vol else None)
            except (ValueError, ZeroDivisionError):
                avgs.append(None)
        else:
            avgs.append(None)
    return {"code": sc, "date": data.get("date", ""), "pre_close": pre_close,
            "points": points, "avgs": avgs}


# ---------------- 筹码分布 + 历史分时(东财) ----------------
_EM_HIS_HOSTS = ["http://90.push2his.eastmoney.com",
                 "https://push2his.eastmoney.com"]
_dfq_cache = {}  # code -> {"ts": ..., "rows": {date: {...}}}


def _esecid(code):
    """股票代码 -> 东财 secid(0.000001 / 1.600000 / 0.920992)"""
    sc = _secid(code)
    return ("1." if sc.startswith("sh") else "0.") + sc[2:]


def _dfq_rows(code):
    """东财前复权日K(320根, 缓存1小时), 返回 {date: {开收高低量/振幅/换手率}}

    用前复权(fqt=1)保证筹码平均成本与日K显示价格同体系,
    成本线可直接投影到K线主图; 多主机回退。
    """
    esc = _esecid(code)
    now = time.time()
    hit = _dfq_cache.get(code)
    if hit and now - hit["ts"] < 3600:
        return hit["rows"]
    for host in _EM_HIS_HOSTS:
        url = (host + "/api/qt/stock/kline/get?secid=%s"
               "&fields1=f1,f2,f3,f4,f5,f6"
               "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
               "&klt=101&fqt=1&beg=0&end=20500101&lmt=320" % esc)
        try:
            d = fetch_json(url)
        except Exception:
            continue
        kl = (d.get("data") or {}).get("klines") or []
        if not kl:
            continue
        rows = {}
        for it in kl:
            p = it.split(",")
            if len(p) < 11:
                continue
            try:
                rows[p[0]] = {"open": float(p[1]), "close": float(p[2]),
                              "high": float(p[3]), "low": float(p[4]),
                              "volume": float(p[5]), "amplitude": float(p[7]),
                              "turnover": float(p[10])}
            except (ValueError, IndexError):
                continue
        if rows:
            _dfq_cache[code] = {"ts": time.time(), "rows": rows}
            return rows
    return {}


def api_chips(code, date):
    """筹码分布(通达信式三角分布, 基于东财不复权日K)

    从目标日起往前累计至多 120 个交易日的成交量, 每日成交量按
    三角形分布(峰值在当日均价附近)分配到 [最低, 最高] 区间,
    汇总为价格-筹码直方图, 并计算平均成本/90%与70%成本区间/获利盘。
    """
    sc = _secid(code)
    rows = _dfq_rows(code)
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


def _minute_history(sc, date):
    """历史分时(东财 trends2, 近5个交易日), 按日期过滤"""
    esc = _esecid(sc)
    for host in _EM_HIS_HOSTS:
        url = (host + "/api/qt/stock/trends2/get?secid=%s"
               "&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13"
               "&fields2=f51,f52,f53,f54,f55,f56,f57,f58&ndays=5&iscr=0"
               "&ut=fa5fd1943c7b386f172d6893dbfba10b" % esc)
        try:
            d = fetch_json(url)
        except Exception:
            continue
        data = d.get("data") or {}
        trs = data.get("trends") or []
        if not trs:
            continue
        target = date.replace("-", "")
        points = []
        avgs = []
        for ln in trs:
            p = ln.split(",")
            if len(p) < 8 or not p[0].startswith(date):
                continue
            t = p[0][11:].replace(":", "")
            points.append({"t": t, "price": float(p[2]),
                           "volume": float(p[5])})
            avgs.append(float(p[7]))
        if not points:
            return {"error": "该日期无分时数据(仅支持近5个交易日)"}
        return {"code": sc, "date": target, "pre_close": data.get("preClose"),
                "points": points, "avgs": avgs}
    return {"error": "历史分时获取失败"}


def api_minute_day(code, date=""):
    """分时调度: 无日期(当天)走腾讯, 有日期走东财历史分时"""
    if not date:
        return cached("m:%s" % code, 30, lambda: api_minute(code))
    return cached("mh:%s:%s" % (code, date), 3600,
                  lambda: _minute_history(_secid(code), date))


def api_zt_pool(date):
    """涨停池 - 东方财富"""
    d = date or latest_trade_date()
    qdate = compact_date(d)
    url = ("https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989"
           "&dpt=wz.ztzt&Pageindex=0&pagesize=320&sort=fbt%%3Aasc&date=%s" % qdate)
    try:
        data = fetch_json(url).get("data") or {}
    except Exception:
        data = {}
    pool = data.get("pool") or []
    if not pool and d == latest_trade_date():
        data = {}
        try:
            data = fetch_json("https://push2ex.eastmoney.com/getTopicZTPool"
                              "?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt"
                              "&Pageindex=0&pagesize=320&sort=fbt%%3Aasc&date=%s"
                              % compact_date(prev_trade_date())).get("data") or {}
        except Exception:
            pass
        if data.get("pool"):
            d = prev_trade_date()
    rows = []
    for it in (data.get("pool") or []):
        rows.append({
            "code": it.get("c"),
            "market": it.get("m"),
            "name": it.get("n"),
            "price": it.get("p"),
            "pct": it.get("zdp"),
            "amount": fmt_amount(it.get("amount")),
            "float_value": fmt_amount(it.get("ltsz")),
            "turnover": it.get("hs"),
            "lianban": it.get("lbc"),
            "first_time": it.get("fbt"),
            "last_time": it.get("lbt"),
            "fund": fmt_amount(it.get("fund")),
            "zhaban": it.get("zbc"),
            "industry": it.get("hybk"),
            "days": (it.get("zttj") or {}).get("days"),
            "count": (it.get("zttj") or {}).get("ct"),
        })
    return {"date": d, "total": len(rows), "rows": rows}


def api_dt_pool(date):
    """跌停池 - 东方财富"""
    d = date or latest_trade_date()
    qdate = compact_date(d)
    url = ("https://push2ex.eastmoney.com/getTopicDTPool?ut=7eea3edcaed734bea9cbfc24409ed989"
           "&dpt=wz.ztzt&Pageindex=0&pagesize=320&sort=fund%%3Aasc&date=%s" % qdate)
    try:
        data = fetch_json(url).get("data") or {}
    except Exception:
        data = {}
    if not data.get("pool") and d == latest_trade_date():
        data = {}
        try:
            data = fetch_json("https://push2ex.eastmoney.com/getTopicDTPool"
                              "?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt"
                              "&Pageindex=0&pagesize=320&sort=fund%%3Aasc&date=%s"
                              % compact_date(prev_trade_date())).get("data") or {}
        except Exception:
            pass
        if data.get("pool"):
            d = prev_trade_date()
    rows = []
    for it in (data.get("pool") or []):
        rows.append({
            "code": it.get("c"),
            "name": it.get("n"),
            "price": it.get("p"),
            "pct": it.get("zdp"),
            "amount": fmt_amount(it.get("amount")),
            "float_value": fmt_amount(it.get("ltsz")),
            "turnover": it.get("hs"),
            "lianban": it.get("lbc"),
            "first_time": it.get("fbt"),
            "last_time": it.get("lbt"),
            "fund": fmt_amount(it.get("fund")),
            "industry": it.get("hybk"),
        })
    return {"date": d, "total": len(rows), "rows": rows}


def api_zb_pool(date):
    """炸板池 - 东方财富"""
    d = date or latest_trade_date()
    qdate = compact_date(d)
    url = ("https://push2ex.eastmoney.com/getTopicZBPool?ut=7eea3edcaed734bea9cbfc24409ed989"
           "&dpt=wz.ztzt&Pageindex=0&pagesize=320&sort=fbt%%3Aasc&date=%s" % qdate)
    try:
        data = fetch_json(url).get("data") or {}
    except Exception:
        data = {}
    if not data.get("pool") and d == latest_trade_date():
        data = {}
        try:
            data = fetch_json("https://push2ex.eastmoney.com/getTopicZBPool"
                              "?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt"
                              "&Pageindex=0&pagesize=320&sort=fbt%%3Aasc&date=%s"
                              % compact_date(prev_trade_date())).get("data") or {}
        except Exception:
            pass
        if data.get("pool"):
            d = prev_trade_date()
    rows = []
    for it in (data.get("pool") or []):
        rows.append({
            "code": it.get("c"),
            "name": it.get("n"),
            "price": it.get("p"),
            "pct": it.get("zdp"),
            "limit_price": it.get("ztp"),
            "amount": fmt_amount(it.get("amount")),
            "float_value": fmt_amount(it.get("ltsz")),
            "turnover": it.get("hs"),
            "first_time": it.get("fbt"),
            "last_time": it.get("lbt"),
            "break_time": it.get("zttime") or it.get("firstBreakTime"),
            "break_count": it.get("zbc"),
            "industry": it.get("hybk"),
        })
    return {"date": d, "total": len(rows), "rows": rows}


def api_plate_flow():
    """行业板块主力资金流 - 东方财富"""
    fs = "m:90+t:2+f:!50"
    fields = "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81"
    hosts = ["https://push2.eastmoney.com", "http://90.push2.eastmoney.com",
             "https://push2delay.eastmoney.com"]
    data = {}
    for host in hosts:
        url = (host + "/api/qt/clist/get?pn=1&pz=120&po=1&np=1"
               "&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f62&fs=%s"
               "&fields=%s" % (fs, fields))
        try:
            data = fetch_json(url).get("data") or {}
        except Exception:
            data = {}
        if data.get("diff"):
            break
        time.sleep(0.3)
    diff = data.get("diff") or []
    if isinstance(diff, dict):
        diff = diff.get("diff") or []
    rows = []
    for it in diff:
        rows.append({
            "code": it.get("f12"),
            "name": it.get("f14"),
            "price": it.get("f2"),
            "pct": it.get("f3"),
            "main_net": it.get("f62"),
            "main_pct": it.get("f184"),
            "xl_net": it.get("f66"),   # 超大单净额
            "xl_pct": it.get("f69"),
            "big_net": it.get("f72"),  # 大单净额
            "big_pct": it.get("f75"),
            "mid_net": it.get("f78"),  # 中单净额
            "small_net": it.get("f81"),  # 小单净额
        })
    return {"time": time.strftime("%H:%M:%S"), "rows": rows}


def _board_days(v):
    """同花顺 high_days 形如 '首板'/'2板'/'4天3板' -> 整数连板数"""
    if v is None:
        return 1
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v)
    m = re.search(r"(\d+)\s*[板天]", s)
    if m:
        return int(m.group(1))
    return 1


def _prev_td(d):
    """任意日期的上一个交易日"""
    dt = datetime.datetime.strptime(d, "%Y-%m-%d").date() - datetime.timedelta(days=1)
    for _ in range(30):
        if is_trade_date(dt.strftime("%Y-%m-%d")):
            return dt.strftime("%Y-%m-%d")
        dt -= datetime.timedelta(days=1)
    return d


def api_hot_stock():
    """人气榜 - 同花顺热门个股(小时级热度), 合并腾讯实时行情"""
    url = "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt"
    try:
        j = fetch_json(url)
    except Exception:
        j = {}
    rows = []
    for it in ((j.get("data") or {}).get("stock_list") or []):
        tag = it.get("tag") or {}
        rows.append({
            "order": it.get("order"),
            "code": it.get("code"),
            "name": it.get("name"),
            "rate": it.get("rate"),
            "analyse": it.get("analyse") or "",
            "tags": list(tag.get("concept_tag") or []),
            "pop": tag.get("popularity_tag") or "",
            "rank_chg": it.get("hot_rank_chg"),
        })
    codes = [r["code"] for r in rows][:60]
    if codes:
        try:
            qm = {r["code"]: r for r in api_quotes(",".join(codes)).get("rows", [])}
            for r in rows:
                m = qm.get(r["code"]) or {}
                r["price"] = m.get("price")
                r["pct"] = m.get("pct")
        except Exception:
            pass
    return {"total": len(rows), "rows": rows}


def api_fengkou():
    """最强风口 - 同花顺热门概念板块热度榜"""
    url = "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_plate/concept/data.txt"
    try:
        j = fetch_json(url)
    except Exception:
        j = {}
    rows = []
    for it in ((j.get("data") or {}).get("plate_list") or []):
        rows.append({
            "order": it.get("order"),
            "code": it.get("code"),
            "name": it.get("name"),
            "rate": it.get("rate"),
            "tag": it.get("tag") or "",
            "hot_rank_chg": it.get("hot_rank_chg"),
        })
    return {"total": len(rows), "rows": rows}


def _em_clist(fs, fields, fid, pz=200, extra=""):
    """东财 clist 列表(多主机轮询, 盘后用 push2delay)"""
    hosts = ["https://push2.eastmoney.com", "http://90.push2.eastmoney.com",
             "https://push2delay.eastmoney.com"]
    data = {}
    for host in hosts:
        url = (host + "/api/qt/clist/get?pn=1&pz=%d&po=1&np=1%s"
               "&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=%s&fs=%s&fields=%s"
               % (pz, extra, fid, fs, fields))
        try:
            data = fetch_json(url).get("data") or {}
        except Exception:
            data = {}
        if data.get("diff"):
            break
        time.sleep(0.3)
    return data


def api_near_zt():
    """即将涨停: 涨幅7%以上逼近涨停的个股 - 东方财富全市场涨幅榜"""
    fs = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
    fields = "f2,f3,f5,f6,f8,f10,f12,f14,f62"
    data = _em_clist(fs, fields, "f3", pz=300)
    rows = []
    for it in (data.get("diff") or []):
        try:
            pct = float(it.get("f3"))
        except (TypeError, ValueError):
            continue
        if pct < 7.0:
            continue
        code = it.get("f12") or ""
        name = it.get("f14") or ""
        if code.startswith(("30", "68")):
            zt_th = 19.5            # 创业板/科创板
        elif code.startswith(("4", "8")):
            zt_th = 29.5            # 北交所
        else:
            zt_th = 4.7 if "ST" in name.upper() else 9.7
        if pct >= zt_th:            # 已涨停不列
            continue
        rows.append({
            "code": code, "name": name,
            "price": it.get("f2"),
            "pct": pct,
            "volume": it.get("f5"),
            "amount": fmt_amount(it.get("f6")),
            "turnover": it.get("f8"),
            "vol_ratio": it.get("f10"),
            "main_net": fmt_amount(it.get("f62")),
        })
    return {"time": time.strftime("%H:%M:%S"), "total": len(rows), "rows": rows}


def _fetch_lhv(url):
    """龙虎VIP 请求(带 Referer)"""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "*/*")
    req.add_header("Referer", "https://www.longhuvip.com/")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", errors="replace")


def api_topic_list():
    """题材时间线 - 龙虎VIP 热门题材(按日期分组)"""
    url = ("https://applhb.longhuvip.com/w1/api/index.php?a=InfoList"
           "&st=30&c=Topic&PhoneOSNew=1&index=0")
    try:
        j = json.loads(_fetch_lhv(url))
    except Exception:
        j = {}
    days = []
    for dg in (j.get("List") or []):
        day = dg.get("Day", "")
        items = []
        for it in (dg.get("List") or []):
            items.append({
                "id": it.get("ID"),
                "title": it.get("Title"),
                "hot": it.get("HotVal"),
                "hot_tag": it.get("HotTag"),
                "time": it.get("Time"),
                "new": it.get("New"),
            })
        if items:
            days.append({"day": day, "items": items})
    return {"days": days}


def api_topic_detail(tid):
    """题材详情 - 龙虎VIP"""
    url = ("https://applhb.longhuvip.com/w1/api/index.php?a=InfoGet"
           "&c=Topic&PhoneOSNew=1&ID=%s" % tid)
    try:
        j = json.loads(_fetch_lhv(url))
    except Exception:
        j = {}
    return {"id": tid, "title": j.get("Title") or "",
            "content": j.get("Content") or ""}


def _ths_idx_kline(code):
    """同花顺指数日K(最近140天): [(yyyymmdd, 成交额元), ...]"""
    try:
        raw = fetch("https://d.10jqka.com.cn/v6/line/%s/01/last.js" % code)
        m = re.search(r'"data":"([^"]*)"', raw)
        if not m:
            return []
        out = []
        for row in m.group(1).split(";"):
            f = row.split(",")
            if len(f) >= 7 and f[0].isdigit():
                out.append((f[0], float(f[6] or 0)))
        return out
    except Exception:
        return []


def api_panmian(date):
    """盘面亮点(原版结构): 三大指数 + 今日/昨日两市成交 + 上涨/下跌/涨停/跌停家数, 附情绪评分/题材/龙头"""
    lu = api_limit_up(date)
    d = lu["date"]
    qdate = compact_date(d)
    # 1) 三大指数(腾讯)
    indices = []
    try:
        raw = fetch("http://qt.gtimg.cn/q=s_sh000001,s_sz399001,s_sz399006", decode="gbk")
        for m in re.finditer(r'v_(\w+)="([^"]*)"', raw):
            f = m.group(2).split("~")
            if len(f) >= 6 and f[2]:
                indices.append({"code": f[2], "name": f[1], "price": f[3],
                                "change": f[4], "pct": f[5]})
    except Exception:
        pass
    # 2) 两市成交额(同花顺指数日K: 上证+深证), 今昨对比
    cur_amt = pre_amt = None
    try:
        def _amt(k):
            for i, (dt, am) in enumerate(k):
                if dt == qdate:
                    pre = k[i - 1][1] if i > 0 else None
                    return am, pre
            return None, None
        k1, k2 = _ths_idx_kline("hs_1A0001"), _ths_idx_kline("hs_399001")
        a1, p1 = _amt(k1)
        a2, p2 = _amt(k2)
        if a1 is not None and a2 is not None:
            cur_amt = a1 + a2
        if p1 is not None and p2 is not None:
            pre_amt = p1 + p2
    except Exception:
        pass
    # 3) 涨跌家数(东财 push2delay, push2 主站拒连)
    up = down = flat = None
    try:
        q = fetch_json("https://push2delay.eastmoney.com/api/qt/ulist.np/get"
                       "?fltt=2&secids=1.000001&fields=f104,f105,f106")
        diff = ((q.get("data") or {}).get("diff") or [{}])[0]
        up, down, flat = diff.get("f104"), diff.get("f105"), diff.get("f106")
    except Exception:
        pass
    # 4) 涨停/跌停家数
    zt = lu["total"]
    dt = 0
    try:
        dt = api_dt_pool(d)["total"]
    except Exception:
        pass
    # 5) 炸板数(东财)
    zb = 0
    try:
        zj = fetch_json(
            "https://push2ex.eastmoney.com/getTopicZBPool?ut=7eea3edcaed734bea9cbfc24409ed989"
            "&dpt=wz.ztzt&Pageindex=0&pagesize=10&sort=fbt%%3Aasc&date=%s" % qdate)
        zb = (zj.get("data") or {}).get("tc") or 0
    except Exception:
        pass
    # 晋级率(昨日涨停今日继续涨停占比)
    jj_rate = None
    try:
        lu_y = api_limit_up(_prev_td(d))
        if lu_y["total"]:
            tc = {r["code"] for r in lu["rows"]}
            promoted = sum(1 for r in lu_y["rows"] if r["code"] in tc)
            jj_rate = round(promoted * 100.0 / lu_y["total"])
    except Exception:
        pass
    # 连板高度
    max_days = max([_board_days(r.get("high_days")) for r in lu["rows"]] or [0])
    # 炸板率
    zb_rate = round(zb * 100.0 / max(1, lu["total"] + zb))
    # 情绪温度评分
    score = lu["total"] * 1.0 + max_days * 3 - zb * 0.6
    if jj_rate is not None:
        score += (jj_rate - 30) * 0.2
    score = max(0.0, min(100.0, score))
    if score >= 75:
        level, advice = "高潮", "赚钱效应极强，高位题材注意兑现，主线龙头可持有"
    elif score >= 55:
        level, advice = "回暖", "情绪升温，可积极关注主线题材的低吸与半路机会"
    elif score >= 35:
        level, advice = "修复", "情绪平稳，关注新题材首板与龙头分歧转一致"
    elif score >= 15:
        level, advice = "低迷", "情绪偏弱，控制仓位，等待冰点转折信号"
    else:
        level, advice = "冰点", "情绪冰点，空仓等待，留意率先走强的方向"
    # 涨停原因 TOP
    ztr = api_zt_reason(d)
    top_reasons = [{"reason": g["reason"], "count": g["count"]}
                   for g in ztr["rows"][:6]]
    # 最高板龙头
    top_boards = [{"code": r["code"], "name": r["name"], "days": r.get("high_days")}
                  for r in sorted(lu["rows"], key=lambda r: -_board_days(r.get("high_days")))[:5]]
    # 龙一(最早封板)
    with_time = [r for r in lu["rows"] if r.get("first_time")]
    longyi = sorted(with_time, key=lambda r: int(r["first_time"]))[0] if with_time else None
    return {
        "date": d,
        "indices": indices,
        "cur_amt": cur_amt, "pre_amt": pre_amt,
        "zt": lu["total"], "dt": dt, "zb": zb, "zb_rate": zb_rate,
        "max_days": max_days, "jj_rate": jj_rate,
        "up": up, "down": down, "flat": flat,
        "score": round(score, 1), "level": level, "advice": advice,
        "top_reasons": top_reasons, "top_boards": top_boards, "longyi": longyi,
    }


def api_plate_flow_cn():
    """板块资金轨迹 - 东方财富概念板块主力资金流"""
    fs = "m:90+t:3+f:!50"
    fields = "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81"
    data = _em_clist(fs, fields, "f62", pz=120)
    rows = []
    for it in (data.get("diff") or []):
        rows.append({
            "code": it.get("f12"),
            "name": it.get("f14"),
            "price": it.get("f2"),
            "pct": it.get("f3"),
            "main_net": fmt_amount(it.get("f62")),
            "main_net_raw": it.get("f62"),
            "main_pct": it.get("f184"),
            "xl_net": fmt_amount(it.get("f66")),
            "xl_pct": it.get("f69"),
            "big_net": fmt_amount(it.get("f72")),
            "big_pct": it.get("f75"),
            "mid_net": fmt_amount(it.get("f78")),
            "small_net": fmt_amount(it.get("f81")),
        })
    return {"time": time.strftime("%H:%M:%S"), "rows": rows}


def _xg_fp(n=32):
    """东财智能选股 fingerprint/requestId: n位小写hex"""
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def _xg_get(r, prefix):
    """东财智能选股数据行取值: key 可能带 {日期} 后缀, 前缀匹配"""
    for k, v in r.items():
        if k == prefix or (isinstance(k, str) and k.startswith(prefix + "{")):
            return v
    return None


def api_em_xuangu(q, size):
    """东财智能选股: 输入框自然语言条件, 东财智能解析(原版功能)

    调用 np-tjxg-b search-code 接口(keywordNew 传自然语言, 服务端解析),
    失败时回退本地关键词匹配(问财逻辑)。
    """
    q = (q or "").strip()
    if not q:
        return {"rows": [], "total": 0,
                "msg": "请输入选股条件, 如: 涨停 半导体 / 市盈率低于20 / MACD金叉 / 主力净流入最多"}
    size = max(10, min(int(size or 20), 100))
    try:
        body = {"keywordNew": q, "pageSize": size, "pageNo": 1,
                "fingerprint": _xg_fp(), "timestamp": int(time.time() * 1000),
                "requestId": _xg_fp(), "gids": [], "shareToGuba": False,
                "needShowStockNum": False, "client": "WEB"}
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
        if j.get("code") == "100" and dl:
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
                    "pb": _xg_get(r, "PB"),
                    "total_value": _xg_get(r, "TOAL_MARKET_VALUE<140>"),
                    "float_value": _xg_get(r, "CIRCULATION_MARKET_VALUE<140>"),
                    "lianban": _xg_get(r, "FIRST_LIMITUP"),
                    "first_time": _xg_get(r, "LIMIT_UP_FLT"),
                    "reason": _xg_get(r, "LIMIT_REASON"),
                })
            total = res.get("total") or len(rows)
            return {"q": q, "title": "条件: %s" % q, "total": total, "rows": rows,
                    "msg": "东财智能解析 · 共 %d 只 · 展示前 %d 只" % (total, min(size, len(rows)))}
    except Exception:
        pass
    # 东财解析失败: 回退本地关键词匹配
    fb = api_wencai(q, size)
    fb["title"] = "条件: %s" % q
    fb["msg"] = (fb.get("msg") or "") + " · 东财解析不可用, 已本地匹配"
    return fb


def api_wencai(q, size):
    """问财选股: 关键词智能匹配(涨停原因/题材/板块/名称/拼音)"""
    q = (q or "").strip()
    if not q:
        return {"rows": [], "total": 0, "msg": "请输入选股条件, 如: 涨停 光伏 / 创新药 / 中国平安"}
    size = max(10, min(int(size or 50), 100))
    kws = [k for k in re.split(r"[\s,，、+]+", q) if k]
    seen = set()
    rows = []
    # 0) 池类关键词: 涨停/连板/跌停/炸板 → 对应股票池
    STOP = ("今日", "昨日", "今天", "昨天", "的", "股票", "哪些", "什么", "有", "是")
    pool = None
    pool_lb = False
    pool_tag = "涨停池"
    rest = []
    for k in kws:
        if "涨停" in k:
            pool = api_zt_pool("")
            pool_lb = any(w in k for w in ("连板", "2板", "二板", "连续"))
            pool_tag = "涨停池"
        elif "跌停" in k:
            pool = api_dt_pool("")
            pool_tag = "跌停池"
        elif "炸板" in k:
            pool = api_zb_pool("")
            pool_tag = "炸板池"
        elif k not in STOP:
            rest.append(k)
    kws = rest
    if pool is not None:
        for r in pool.get("rows", []):
            if pool_lb and int(r.get("lianban") or 1) < 2:
                continue
            txt = (r.get("name") or "") + " " + (r.get("industry") or "")
            if all(k in txt for k in kws):
                seen.add(r["code"])
                if pool_tag == "炸板池":
                    days = "炸板"
                else:
                    days = ("%d连板" % r["lianban"]) if r.get("lianban") else "首板"
                rows.append({"code": r["code"], "name": r["name"], "days": days,
                             "reason": r.get("industry") or "", "pct": r.get("pct"),
                             "first_time": r.get("first_time"), "source": pool_tag})
    # 1) 涨停池: 涨停原因/名称匹配(纯池查询无剩余关键词时跳过, 避免空关键词全命中)
    if pool is None or kws:
        for r in api_limit_up("").get("rows", []):
            if r["code"] in seen:
                continue
            txt = (r.get("reason") or "") + " " + (r.get("name") or "")
            if all(k in txt for k in kws):
                seen.add(r["code"])
                rows.append({"code": r["code"], "name": r["name"], "days": r.get("high_days"),
                             "reason": r.get("reason"), "pct": r.get("pct"),
                             "first_time": r.get("first_time"), "source": "涨停池"})
    # 2) 板块涨停: 板块名匹配
    if pool is None or kws:
        try:
            for p in (api_ladder().get("plates") or []):
                if all(k in (p.get("name") or "") for k in kws):
                    for s in (p.get("stocks") or []):
                        if s.get("code") and s["code"] not in seen:
                            seen.add(s["code"])
                            rows.append({"code": s["code"], "name": s["name"], "days": "",
                                         "reason": p.get("name"), "pct": None,
                                         "first_time": None, "source": "板块涨停"})
        except Exception:
            pass
    # 3) 全市场: 名称/拼音匹配(最多补 size*2 只, 池类查询不补全市场)
    if pool is None:
        try:
            for st in (_stock_list() or []):
                if len(rows) >= size * 2:
                    break
                txt = (st.get("name") or "") + " " + (st.get("py") or "")
                if all(k in txt for k in kws) and st["code"] not in seen:
                    seen.add(st["code"])
                    rows.append({"code": st["code"], "name": st["name"], "days": "",
                                 "reason": "", "pct": None, "first_time": None,
                                 "source": "全市场"})
        except Exception:
            pass
    # 批量补实时行情
    codes = [r["code"] for r in rows[:size]]
    if codes:
        try:
            qm = {r["code"]: r for r in api_quotes(",".join(codes[:80])).get("rows", [])}
            for r in rows[:size]:
                m = qm.get(r["code"]) or {}
                if r["pct"] is None and m.get("pct") is not None:
                    r["pct"] = m["pct"]
                r["price"] = m.get("price")
        except Exception:
            pass
    return {"rows": rows[:size], "total": len(rows),
            "date": api_limit_up("").get("date"),
            "msg": "共匹配 %d 只, 展示前 %d 只" % (len(rows), min(size, len(rows)))}


def _find_plate(plates, name):
    """财联社板块名与东财概念名模糊匹配"""
    n = (name or "").replace("概念", "")
    for p in plates:
        pn = (p.get("name") or "").replace("概念", "")
        if not pn:
            continue
        if n == pn or n in pn or pn in n:
            return p
    return None


def api_theme_invest():
    """题材投资系统: 题材机会聚合(热门题材+概念资金+板块涨停)"""
    topics = []
    try:
        tl = api_topic_list()
        if tl.get("days"):
            topics = [{"id": t["id"], "title": t["title"], "hot": t["hot"]}
                      for t in tl["days"][0]["items"][:10]]
    except Exception:
        pass
    try:
        flow = api_plate_flow_cn().get("rows") or []
    except Exception:
        flow = []
    try:
        plates = api_ladder().get("plates") or []
    except Exception:
        plates = []
    rows = []
    for r in flow[:30]:
        p = _find_plate(plates, r.get("name") or "")
        up_num = (p or {}).get("up_num", 0) or 0
        stocks = (p or {}).get("stocks") or []
        rows.append({
            "name": r.get("name"),
            "pct": r.get("pct"),
            "main_net": r.get("main_net"),
            "main_net_raw": r.get("main_net_raw"),
            "main_pct": r.get("main_pct"),
            "up_num": up_num,
            "leaders": [s.get("name") for s in stocks[:3]],
            "reason": (p or {}).get("reason") or "",
        })
    rows.sort(key=lambda r: -(r["main_net_raw"] or 0))
    return {"date": api_limit_up("").get("date"), "topics": topics,
            "rows": rows}


def api_zt_reason(date):
    """涨停原因分组: 同花顺涨停池按题材聚合(原因串按+拆分子题材)"""
    lu = api_limit_up(date)
    groups = {}
    for r in lu["rows"]:
        reason = (r.get("reason") or "其他").strip() or "其他"
        for part in reason.split("+"):
            k = part.strip() or "其他"
            g = groups.setdefault(k, {"reason": k, "count": 0, "max_days": 0, "stocks": []})
            g["count"] += 1
            g["max_days"] = max(g["max_days"], _board_days(r.get("high_days")))
            g["stocks"].append({
                "code": r["code"], "name": r["name"],
                "days": r.get("high_days"), "pct": r.get("pct"),
                "time": r.get("first_time"),
            })
    rows = sorted(groups.values(), key=lambda g: (-g["count"], -g["max_days"]))
    return {"date": lu["date"], "total": lu["total"], "rows": rows}


def api_zt_review(date):
    """涨停复盘图数据: 涨停时间线分布 + 连板金字塔 + 市场统计"""
    lu = api_limit_up(date)
    zb = 0
    try:
        zj = fetch_json(
            "https://push2ex.eastmoney.com/getTopicZBPool?ut=7eea3edcaed734bea9cbfc24409ed989"
            "&dpt=wz.ztzt&Pageindex=0&pagesize=10&sort=fbt%%3Aasc&date=%s" % compact_date(lu["date"]))
        zb = (zj.get("data") or {}).get("tc") or 0
    except Exception:
        pass
    buckets = {}
    pyr = {}
    stocks = []
    for r in lu["rows"]:
        ft = r.get("first_time")
        days = _board_days(r.get("high_days"))
        pyr[days] = pyr.get(days, 0) + 1
        stocks.append({"code": r["code"], "name": r["name"], "days": days,
                       "reason": r.get("reason") or "", "time": ft, "pct": r.get("pct")})
        if ft:
            try:
                hm = time.strftime("%H:%M", time.localtime(int(ft)))
                buckets[hm] = buckets.get(hm, 0) + 1
            except (ValueError, OSError):
                pass
    tl = [{"time": k, "count": v} for k, v in sorted(buckets.items())]
    pyramid = [{"days": k, "count": v} for k, v in sorted(pyr.items(), reverse=True)]
    return {"date": lu["date"], "total": lu["total"], "broken": zb,
            "timeline": tl, "pyramid": pyramid, "stocks": stocks}


def api_dragon(date):
    """龙头晋级: 昨日涨停股今日晋级/断板表现"""
    d = date or latest_trade_date()
    y = _prev_td(d)
    lu_today = api_limit_up(d)
    lu_yest = api_limit_up(y)
    today = {r["code"]: r for r in lu_today["rows"]}
    yest = {r["code"]: r for r in lu_yest["rows"]}
    promoted, broken = [], []
    codes = list(yest.keys())
    quotes = {}
    for i in range(0, len(codes), 60):
        try:
            qr = api_quotes(",".join(codes[i:i + 60])).get("rows", [])
            quotes.update({r["code"]: r for r in qr})
        except Exception:
            pass
    for code, r in yest.items():
        t = today.get(code)
        if t:
            promoted.append({"code": code, "name": r["name"],
                             "ydays": r.get("high_days"), "tdays": t.get("high_days"),
                             "reason": t.get("reason")})
        else:
            m = quotes.get(code) or {}
            try:
                pct = float(m.get("pct") or 0)
            except (TypeError, ValueError):
                pct = 0
            broken.append({"code": code, "name": r["name"],
                           "ydays": r.get("high_days"), "pct": pct,
                           "reason": r.get("reason")})
    promoted.sort(key=lambda x: -_board_days(x.get("tdays")))
    broken.sort(key=lambda x: -(x["pct"] or -99))
    new_boards = [{"code": r["code"], "name": r["name"], "days": r.get("high_days"),
                   "reason": r.get("reason")} for r in lu_today["rows"] if r["code"] not in yest]
    return {"date": d, "yesterday": y, "y_total": lu_yest["total"],
            "promote_total": len(promoted), "promoted": promoted,
            "broken": broken, "new_boards": new_boards}


def api_longyi(date):
    """今日龙一: 首封最早涨停股 + 最高连板龙头"""
    lu = api_limit_up(date)
    with_time = [r for r in lu["rows"] if r.get("first_time")]
    by_time = sorted(with_time, key=lambda r: int(r["first_time"]))
    longyi = by_time[0] if by_time else None
    top_boards = sorted(lu["rows"], key=lambda r: -_board_days(r.get("high_days")))[:10]
    return {"date": lu["date"], "longyi": longyi,
            "first_10": by_time[:10], "top_boards": top_boards}


def api_news():
    """724 快讯 - 东方财富"""
    url = ("https://np-weblist.eastmoney.com/comm/web/getFastNewsList?client=web"
           "&biz=web_724&fastColumn=102&sortEnd=&pageSize=60&req_trace=%d"
           % int(time.time() * 1000))
    try:
        data = fetch_json(url).get("data") or {}
    except Exception:
        data = {}
    rows = []
    for it in (data.get("fastNewsList") or []):
        rows.append({
            "summary": it.get("summary"),
            "title": it.get("title"),
            "time": it.get("showTime") or it.get("time"),
            "code": it.get("code"),
        })
    return {"total": len(rows), "rows": rows}


# ================= HTTP 服务 =================
ROUTES = {
    "indices": lambda q: cached("indices", 10, api_indices),
    "limit_up": lambda q: cached("lu:%s" % q.get("date", ""), 30,
                                 lambda: api_limit_up(q.get("date"))),
    "xgb_limit_up": lambda q: cached("xlu:%s" % q.get("date", ""), 30,
                                    lambda: api_xgb("limit_up", q.get("date"))),
    "xgb_broken": lambda q: cached("xbk:%s" % q.get("date", ""), 30,
                                  lambda: api_xgb("limit_up_broken", q.get("date"))),
    "ladder": lambda q: cached("ladder", 30, api_ladder),
    "hot_plate": lambda q: cached("hotplate", 30, api_hot_plate),
    "lhb": lambda q: cached("lhb:%s" % q.get("date", ""), 600,
                            lambda: api_lhb(q.get("date"))),
    "bidding": lambda q: cached("bidding", 60, api_bidding),
    "duishu": lambda q: api_duishu(q.get("date", ""), q.get("type", "1"),
                                   int(q.get("page", 1)), int(q.get("size", 60))),
    "market": lambda q: api_market(q.get("sort"), int(q.get("page", 1)),
                                   int(q.get("size", 50))),
    "dates": lambda q: api_dates(),
    "trade_dates": lambda q: cached("cal:%s" % q.get("year", ""), 86400,
                                    lambda: api_trade_dates(q.get("year"))),
    "quote": lambda q: cached("q:%s" % q.get("code", ""), 5,
                              lambda: api_quote(q.get("code"))),
    "quotes": lambda q: cached("qs:%s" % q.get("codes", ""), 5,
                               lambda: api_quotes(q.get("codes"))),
    "search": lambda q: cached("sr:%s" % q.get("q", ""), 300,
                               lambda: api_search(q.get("q"))),
    "kline": lambda q: cached("k:%s:%s" % (q.get("code", ""), q.get("period", "day")), 300,
                              lambda: api_kline(q.get("code"), q.get("period"), int(q.get("count", 320)))),
    "minute": lambda q: api_minute_day(q.get("code"), q.get("date", "")),
    "chips": lambda q: cached("chips:%s:%s" % (q.get("code", ""), q.get("date", "")), 3600,
                               lambda: api_chips(q.get("code"), q.get("date", ""))),
    "zt_pool": lambda q: cached("zt:%s" % q.get("date", ""), 30,
                                lambda: api_zt_pool(q.get("date"))),
    "dt_pool": lambda q: cached("dt:%s" % q.get("date", ""), 30,
                                lambda: api_dt_pool(q.get("date"))),
    "zb_pool": lambda q: cached("zb:%s" % q.get("date", ""), 30,
                                lambda: api_zb_pool(q.get("date"))),
    "plate_flow": lambda q: cached("pf", 30, api_plate_flow),
    "news": lambda q: cached("news", 60, api_news),
    "hot_stock": lambda q: cached("hs", 600, api_hot_stock),
    "fengkou": lambda q: cached("fk", 300, api_fengkou),
    "zt_reason": lambda q: cached("ztr:%s" % q.get("date", ""), 30,
                                  lambda: api_zt_reason(q.get("date"))),
    "zt_review": lambda q: cached("ztrv:%s" % q.get("date", ""), 30,
                                  lambda: api_zt_review(q.get("date"))),
    "dragon": lambda q: cached("drg:%s" % q.get("date", ""), 30,
                               lambda: api_dragon(q.get("date"))),
    "longyi": lambda q: cached("ly:%s" % q.get("date", ""), 30,
                               lambda: api_longyi(q.get("date"))),
    "near_zt": lambda q: cached("nzt", 15, api_near_zt),
    "topic_list": lambda q: cached("tpl", 600, api_topic_list),
    "topic_detail": lambda q: cached("tpd:%s" % q.get("id", ""), 3600,
                                     lambda: api_topic_detail(q.get("id"))),
    "panmian": lambda q: cached("pm:%s" % q.get("date", ""), 30,
                                lambda: api_panmian(q.get("date"))),
    "plate_flow_cn": lambda q: cached("pfc", 30, api_plate_flow_cn),
    "em_xuangu": lambda q: cached("exg:%s:%s" % (q.get("q", ""), q.get("size", "")), 30,
                                  lambda: api_em_xuangu(q.get("q"), q.get("size"))),
    "wencai": lambda q: api_wencai(q.get("q", ""), q.get("size", 50)),
    "theme_invest": lambda q: cached("thv", 120, api_theme_invest),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "AStock/1.0"

    # 静态资源 Content-Type 映射(浏览器拒绝 application/octet-stream 的 CSS/字体)
    _CTYPES = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".webp": "image/webp",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".map": "application/json",
    }

    def log_message(self, fmt, *args):  # 安静模式
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path)
        p = path.path
        try:
            if p == "/" or p == "/index.html":
                try:
                    with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                        self._send(200, f.read().decode("utf-8"), "text/html; charset=utf-8")
                except OSError:
                    self._send(404, {"error": "index.html 未找到，请确认与 server.py 同目录"})
                return
            if p.startswith("/static/"):
                try:
                    with open(os.path.join(BASE_DIR, p[1:]), "rb") as f:
                        raw = f.read()
                    ext = "." + p.rsplit(".", 1)[-1].lower() if "." in p else ""
                    ctype = self._CTYPES.get(ext, "application/octet-stream")
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(raw)
                except OSError:
                    self._send(404, {"error": "文件不存在"})
                return
            if p.startswith("/api/"):
                name = p[5:].split("&")[0]
                if name not in ROUTES:
                    self._send(404, {"error": "未知接口: %s" % name})
                    return
                q = {k: v[0] for k, v in urllib.parse.parse_qs(path.query).items()}
                # 兼容不带 ? 的写法: /api/xxx&k=v
                extra = path.path[5:].split("&")[1:]
                for kv in urllib.parse.parse_qs("&".join(extra)):
                    q[kv] = urllib.parse.parse_qs("&".join(extra))[kv][0]
                result = ROUTES[name](q)
                self._send(200, result)
                return
            self._send(404, {"error": "Not Found"})
        except Exception as e:  # noqa
            self._send(500, {"error": str(e)})


def main():
    threading.Thread(target=_warm_stock_list, daemon=True).start()  # 后台预热股票列表
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("=" * 56)
    print("  A股复盘看盘 Web 应用已启动")
    print("  浏览器访问:  http://127.0.0.1:%d" % PORT)
    print("  按 Ctrl+C 停止服务")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
