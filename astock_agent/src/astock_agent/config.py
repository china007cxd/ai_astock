"""全局配置：路径、环境变量、DeepSeek/astock 连接参数

【这个文件是干什么的】
项目的"总开关"：所有其他模块都从这里读取配置（数据目录在哪、
DeepSeek 的 Key 是什么、astock 服务地址等），而不是自己写死。

【给小白的关键概念】
- Path：Python 处理文件路径的工具，BASE_DIR 就是项目根目录
- .env 文件：存放敏感配置（如 API Key）的文本文件，
  load_dotenv() 会把它读进环境变量，os.getenv() 再取出来。
  这样 Key 不会写死在代码里（写死会不小心泄露）。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录 = astock_agent/
# 本文件位于 src/astock_agent/config.py，向上两级（parents[2]）就是项目根
BASE_DIR = Path(__file__).resolve().parents[2]

# 四个数据目录：案例库 / 规则库 / 运行记录 / 待确认草案（对应方案中的文件存储设计）
CASES_DIR = BASE_DIR / "cases"
RULES_DIR = BASE_DIR / "rules"
RUNS_DIR = BASE_DIR / "runs"
DRAFTS_DIR = BASE_DIR / "drafts"
# Web 前端目录（index.html 和 static/ 都在这里）
WEB_DIR = BASE_DIR / "web"

# 读取项目根目录下的 .env 文件（如果存在），把其中的 KEY=VALUE 加载为环境变量
load_dotenv(BASE_DIR / ".env")

# ---------------- DeepSeek 模型配置 ----------------
# API Key：DeepSeek 官网申请。为空 = 学习/结果解读等 LLM 功能不可用
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
# 接口地址：DeepSeek 兼容 OpenAI 协议，一般不用改
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
# 文本模型：负责规则提炼、结果说明生成（便宜够用）
TEXT_MODEL = os.getenv("TEXT_MODEL", "deepseek-chat").strip()
# 视觉模型：负责案例截图解读（实验版，能看图）
VISION_MODEL = os.getenv("VISION_MODEL", "deepseek-v4-flash-vision-exp").strip()

# ---------------- 服务地址 ----------------
# astock 看盘服务的地址：本项目的所有行情数据都通过 HTTP 调用它获取
# （注意：不是 import 它的代码，而是像浏览器一样发请求，避免路径依赖坑）
ASTOCK_BASE = os.getenv("ASTOCK_BASE", "http://127.0.0.1:8765").strip().rstrip("/")
# agent 自身（本项目）的监听地址与端口
AGENT_HOST = os.getenv("AGENT_HOST", "127.0.0.1").strip()
AGENT_PORT = int(os.getenv("AGENT_PORT", "8766"))

# 案例截图支持的图片扩展名（用 set 集合，判断 "xxx.png" 是否在其中很快）
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def ensure_dirs() -> None:
    """确保所有数据目录存在（不存在则创建）

    在 main.py 服务启动时调用一次，避免后续读写文件时目录还不存在报错。
    exist_ok=True 表示目录已存在也不报错（幂等操作，重复调用无副作用）。
    """
    for d in (CASES_DIR, RULES_DIR, RUNS_DIR, DRAFTS_DIR, WEB_DIR):
        d.mkdir(parents=True, exist_ok=True)
