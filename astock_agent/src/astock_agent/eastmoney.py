"""缺失数据直连东财（astock 未提供的两个数据点）

【这个文件是干什么的】
astock 服务没有提供的两个数据点，这里直接请求东方财富的公开接口补齐：
- 个股所属板块（push2 qt/slist spt=3）
- 个股资金流（push2 qt/ulist.np）
其他数据一律走 astock（astock_client），只有这两个走这里。

【给小白的关键概念】
- 东财 secid：东财的股票编号格式。6 开头沪市 → "1.600000"，
  0/3 开头深市 → "0.000001"，北交所 → "0.92xxxx"。
  本文件 _esecid() 负责代码转换。
- 多主机轮询：push2 系列有多个镜像域名（push2 / 90.push2 / push2delay），
  主域名偶尔故障或限流，挨个试，谁通用谁。之前就遇到过 push2 挂掉
  而 push2delay 正常的情况，所以保留三个。
- 内存 TTL 缓存：同一批数据短时间重复请求不重复发网络（板块缓存5分钟、
  资金流缓存60秒），既快又降低被东财限流的概率。
- diff 字段：东财接口返回的 "diff" 可能是 dict（{0:行,1:行}）也可能
  是 list（[行,行]），_rows_of() 统一转成 list。
"""
from __future__ import annotations

import time

import httpx

# 东财 push2 的多个镜像主机，轮询使用（挂了就换下一个）
_HOSTS = [
    "https://push2.eastmoney.com",
    "http://90.push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
]
# 伪装成浏览器（User-Agent），东财对没有 UA 的请求会拒绝
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
# 内存缓存：key → (写入时间戳, 数据)。进程重启即失效，够用。
_cache: dict[str, tuple[float, object]] = {}


def _esecid(code: str) -> str:
    """股票代码 -> 东财 secid（1.600000 / 0.000001 / 0.920992）

    支持三种输入：纯数字 "600519"、带前缀 "sh600519"/"sz000001"。
    规则：6/5/9 开头 → 沪市(1)；其余 → 深市(0)。北交所 92 开头按深市处理。
    """
    c = (code or "").strip().lower()
    if c.startswith(("sh", "sz", "bj")):          # 带前缀的直接拆
        mkt = "1" if c.startswith("sh") else "0"
        return "%s.%s" % (mkt, c[2:])
    if c.startswith(("6", "5", "9")):             # 沪市特征开头
        return "1.%s" % c
    return "0.%s" % c


def _cached(key: str, ttl: float):
    """查缓存：命中且未过期返回数据，否则返回 None

    ttl = 有效期（秒）。time.time() - 写入时间 > ttl 就视为过期。
    """
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    return None


def _cache_set(key: str, val) -> None:
    """写缓存：记录 (当前时间, 数据)"""
    _cache[key] = (time.time(), val)


async def _fetch_json(url: str) -> dict:
    """发一个 GET 请求并返回 JSON（内部工具，失败抛异常由调用方轮询下一个主机）"""
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": _UA}) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.json()


def _rows_of(diff) -> list[dict]:
    """东财 diff 可能是 list 或 {0:row,1:row}，统一转成行列表"""
    if isinstance(diff, dict):
        return list(diff.values())
    return diff or []


async def stock_boards(code: str) -> list[dict]:
    """个股所属板块: [{code, name, pct, mkt}]（缓存5分钟）

    东财接口：/api/qt/slist/get?spt=3 按股票查所属板块列表。
    pz=100 表示最多取100个板块（一只股票一般不会超过）。
    """
    key = "bd:%s" % code
    hit = _cached(key, 300)
    if hit is not None:
        return hit
    esc = _esecid(code)
    rows: list[dict] = []
    for host in _HOSTS:  # 多主机轮询：第一个通了就 break
        url = (host + "/api/qt/slist/get?spt=3&secid=%s&pi=0&pz=100&po=1&np=1"
               "&fltt=2&invt=2&fields=f12,f13,f14,f3" % esc)
        try:
            data = (await _fetch_json(url)).get("data") or {}
        except Exception:
            continue  # 本主机失败，试下一个
        diff = data.get("diff") or []
        if not diff:
            continue  # 返回空也可能是接口异常，继续试下一个
        for it in _rows_of(diff):
            # f12=板块代码 f13=市场 f14=板块名 f3=涨跌幅
            rows.append({"code": it.get("f12"), "mkt": it.get("f13"),
                         "name": it.get("f14"), "pct": it.get("f3")})
        break
    _cache_set(key, rows)  # 即使为空也缓存，避免短时间反复打失败的主机
    return rows


async def stock_flow(codes: list[str]) -> list[dict]:
    """个股资金流: [{code,name,price,pct,main_net,main_pct,xl_net,big_net,mid_net,small_net}]（缓存60秒）

    东财接口：/api/qt/ulist.np/get 批量查资金流，一次最多60只（接口限制）。
    字段含义：main_net主力净额 main_pct主力净占比 xl_net超大单 big_net大单
    mid_net中单 small_net小单。
    """
    # 过滤空代码 + 截断到 60 只（东财单次上限）
    cs = [c for c in (codes or []) if c][:60]
    if not cs:
        return []
    # 缓存 key 用排序后的代码串：同一批股票不管顺序如何都命中同一缓存
    key = "fl:%s" % ",".join(sorted(cs))
    hit = _cached(key, 60)
    if hit is not None:
        return hit
    escs = ",".join(_esecid(c) for c in cs)
    rows: list[dict] = []
    for host in _HOSTS:
        url = (host + "/api/qt/ulist.np/get?fltt=2&invt=2&secids=%s"
               "&fields=f12,f14,f2,f3,f62,f184,f66,f72,f78,f84" % escs)
        try:
            data = (await _fetch_json(url)).get("data") or {}
        except Exception:
            continue
        diff = data.get("diff") or []
        if not diff:
            continue
        for it in _rows_of(diff):
            rows.append({
                "code": it.get("f12"), "name": it.get("f14"),
                "price": it.get("f2"), "pct": it.get("f3"),
                "main_net": it.get("f62"), "main_pct": it.get("f184"),
                "xl_net": it.get("f66"), "big_net": it.get("f72"),
                "mid_net": it.get("f78"), "small_net": it.get("f84"),
            })
        break
    _cache_set(key, rows)
    return rows
