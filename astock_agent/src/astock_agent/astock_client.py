"""astock 看盘服务 HTTP 客户端

【这个文件是干什么的】
本项目的"数据源头"。所有行情数据（K线/筹码/板块/资金流等）统一
通过 HTTP 调用 astock 看盘服务获取（先启动 astock 目录下的 启动.bat，
端口 8765），本模块不重复实现抓取逻辑，只负责发请求、失败重试。

【给小白的关键概念】
- HTTP 客户端：httpx.AsyncClient 相当于一个"浏览器"，get() 就是
  向 http://127.0.0.1:8765/api/xxx 发请求拿 JSON 数据。
- 为什么用 async（异步）：httpx 支持并发，请求等待网络返回期间
  Python 可以去发别的请求，选股时要查几十只股票，串行会慢死。
- 单例：文件末尾 client = AstockClient() 创建了全局唯一实例，
  其他模块直接 from .astock_client import client 复用同一个连接池。
- 失败自动重试一次：网络偶尔抽风，重试一次能大幅提高成功率。
"""
from __future__ import annotations

import httpx

from . import config


class AstockError(RuntimeError):
    """astock 请求彻底失败时抛出的异常（重试两次仍失败才抛）"""


class AstockClient:
    """astock 服务的异步 HTTP 客户端（懒加载 + 连接池复用）

    用法：
        await client.get("kline", code="000001", period="day", count=320)
    等价于请求 http://127.0.0.1:8765/api/kline?code=000001&...
    """

    def __init__(self, base: str | None = None, timeout: float = 90.0):
        # 服务地址：不传就用配置里的（http://127.0.0.1:8765），去掉末尾斜杠防双斜杠
        self.base = (base or config.ASTOCK_BASE).rstrip("/")
        self.timeout = timeout  # 单次请求超时（秒）。astock 个别接口很慢，调大到 90
        self._client: httpx.AsyncClient | None = None  # 真正的客户端，用到才创建

    @property
    def client(self) -> httpx.AsyncClient:
        """懒加载获取客户端：首次访问才创建，连接池复用不重复建

        @property 把 client 变成"属性"：外面写 self.client 时自动执行此函数。
        is_closed 判断：客户端被关闭过就重建。
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        """关闭底层连接（服务停机时调用，释放连接）"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, name: str, **params) -> dict:
        """GET 请求 astock 的 /api/{name} 接口，返回 JSON dict

        参数：
            name: 接口名，如 "kline"、"chips"、"fengkou"
            **params: 查询参数，如 code="000001"。None/空字符串的参数
                      会被过滤掉（避免发出 code= 这种空参数）

        失败自动重试一次；两次都失败抛 AstockError。
        """
        url = "%s/api/%s" % (self.base, name)
        # 过滤空参数：v not in (None, "") —— 让接口用它的默认值
        p = {k: v for k, v in params.items() if v not in (None, "")}
        last: Exception | None = None
        for _ in range(2):  # 失败重试一次
            try:
                r = await self.client.get(url, params=p)
                r.raise_for_status()  # HTTP 状态码不是 2xx 时抛异常
                return r.json()
            except Exception as e:  # noqa —— 任何异常都先记下来，再试一次
                last = e
        # 两次都失败：抛出带接口名和原因的自定义异常，方便上层识别
        raise AstockError("astock %s 请求失败: %s" % (name, last))

    async def health(self) -> bool:
        """连通性检查：/api/dates 读本地交易日历，轻量无网络依赖（返回 list）

        Web 健康检查端点（/api/health）和启动脚本（启动.bat）都用它
        判断 astock 是否就绪。故意选最轻的接口，检查速度快。
        """
        try:
            j = await self.get("dates")
            return not (isinstance(j, dict) and "error" in j)
        except Exception:
            return False


# 全局单例：整个进程共用一个客户端（复用 httpx 连接池，省资源）
client = AstockClient()
