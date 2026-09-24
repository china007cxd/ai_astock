"""DeepSeek 客户端：文本模型(chat) + 视觉模型(vision)

【这个文件是干什么的】
全项目唯一的 LLM（大模型）出入口。学习管线靠它解读截图、提炼规则，
运行引擎靠它给结果生成说明。其他模块不直接连 DeepSeek，都调这里。

【两种模型的两套接法（历史原因，两种库都演示了用法）】
- 文本：langchain-openai 的 ChatOpenAI（OpenAI 兼容协议）
  优点：和 LangChain 生态无缝衔接，消息用 ("system","...") 元组即可
- 视觉：openai SDK 直连 deepseek-v4-flash-vision-exp（base64 内联传图）
  因为当时 langchain-openai 对视觉消息封装不方便，直接裸调 SDK 更稳

【给小白的关键概念】
- API Key 校验：所有 LLM 函数入口先 _require_key() 检查 .env 里配了
  Key 没有，没配就直接抛 LLMNotConfiguredError，让调用方拿到明确错误。
- JSON 模式：response_format={"type":"json_object"} 要求模型只输出
  合法 JSON 文本，方便程序直接解析，而不是输出一段人话。
- base64：图片要发给模型，得先把图片的二进制字节编码成文本
  （data:image/png;base64,xxxx 这种 data URL 格式）。
"""
from __future__ import annotations

import base64
import json
import re

from langchain_openai import ChatOpenAI
from openai import OpenAI

from . import config


class LLMNotConfiguredError(RuntimeError):
    """未配置 DEEPSEEK_API_KEY 时抛出的异常（继承 RuntimeError，方便上层 except 捕获）"""


def has_llm() -> bool:
    """LLM 是否可用：.env 里是否填了 DEEPSEEK_API_KEY"""
    return bool(config.DEEPSEEK_API_KEY)


def _require_key() -> None:
    """内部守护函数：没配 Key 就抛异常，阻止后续真正发请求时才发现"""
    if not config.DEEPSEEK_API_KEY:
        raise LLMNotConfiguredError(
            "未配置 DEEPSEEK_API_KEY，请在 astock_agent/.env 中填写后重启服务"
        )


def get_chat_llm(temperature: float = 0.2, json_mode: bool = False) -> ChatOpenAI:
    """创建文本模型客户端（每次调用现建，因为 ChatOpenAI 不支持热更新配置）

    参数：
        temperature: 温度，0~1。越低越"听话稳定"，越高越有创造性。
                     提炼规则/解析 JSON 建议 0.2 或更低
        json_mode: True 时要求模型强制输出 JSON（response_format 参数）
    """
    _require_key()
    kwargs = {}
    if json_mode:
        # OpenAI 协议的 JSON 模式开关：要求模型输出合法 JSON
        kwargs["response_format"] = {"type": "json_object"}
    return ChatOpenAI(
        model=config.TEXT_MODEL,              # 用哪个模型（默认 deepseek-chat）
        api_key=config.DEEPSEEK_API_KEY,      # 密钥
        base_url=config.DEEPSEEK_BASE_URL,    # DeepSeek 接口地址（OpenAI 兼容）
        temperature=temperature,
        timeout=180,                          # 单次请求超时（秒），DeepSeek 慢时也够
        max_retries=2,                        # 网络层自动重试次数
        **kwargs,                             # 展开 json_mode 时的额外参数
    )


def get_vision_client() -> OpenAI:
    """创建视觉模型客户端（openai SDK 直连，用于看截图）"""
    _require_key()
    return OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        timeout=180,
        max_retries=2,
    )


def parse_json_text(text: str) -> dict | list:
    """从 LLM 输出中稳健解析 JSON（容忍 markdown 围栏/前后杂文）

    为什么需要这个函数：模型偶尔不"听话"，输出类似
    "好的，结果如下：\n```json\n{...}\n```"
    本函数依次尝试三种解析策略：
    1. 直接 json.loads（最理想的情况）
    2. 剥掉 ```json ... ``` 代码块围栏再解析
    3. 找第一个 { 到最后一个 }（或 [ ]）之间的内容解析
    全部失败 → 抛 ValueError（带上输出前 200 字，便于排查）
    """
    t = (text or "").strip()
    # 策略2：匹配 ```json ... ``` 或 ``` ... ``` 围栏（re.S 让 . 能跨行）
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # 策略3a：截取第一个 { 到最后一个 }（对象）
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e > s:
            return json.loads(t[s:e + 1])
        # 策略3b：截取第一个 [ 到最后一个 ]（数组）
        s, e = t.find("["), t.rfind("]")
        if s != -1 and e > s:
            return json.loads(t[s:e + 1])
        raise ValueError("无法从输出中解析 JSON: %s" % t[:200])


def chat_text(prompt: str, system: str = "", temperature: float = 0.2) -> str:
    """文本模型对话，返回原文（用于生成结果说明等自由文本）

    参数：
        prompt: 问题（user 消息）
        system: 系统提示词（可选，设定角色）
        temperature: 温度，默认 0.2
    """
    llm = get_chat_llm(temperature=temperature)
    # LangChain 风格消息列表：[("角色", "内容"), ...]，角色用 system/human
    msgs = []
    if system:
        msgs.append(("system", system))
    msgs.append(("human", prompt))
    resp = llm.invoke(msgs)
    # content 可能是 str，也可能是多段 list，统一转成 str 返回
    return resp.content if isinstance(resp.content, str) else str(resp.content)


def chat_json(prompt: str, system: str = "") -> dict | list:
    """文本模型对话并强制 JSON 输出，返回解析好的 dict/list

    注意：DeepSeek 要求"提示词中必须出现 JSON 字样"才会启用 JSON 模式，
    所以调用方要在 system 或 prompt 里写清楚"输出 JSON"。
    解析失败会抛 ValueError，调用方需要 try/except 兜底。
    """
    llm = get_chat_llm(json_mode=True)
    msgs = []
    if system:
        msgs.append(("system", system))
    msgs.append(("human", prompt))
    resp = llm.invoke(msgs)
    return parse_json_text(resp.content if isinstance(resp.content, str) else str(resp.content))


def analyze_image(image_bytes: bytes, mime: str, prompt: str) -> str:
    """视觉模型分析单张截图，返回文本（图片只能放 user 消息）

    参数：
        image_bytes: 图片的原始二进制内容（读文件得到的 bytes）
        mime: 图片 MIME 类型，如 "image/png"、"image/jpeg"
        prompt: 要求模型从图里看什么（如"解读这张K线截图中的选股条件"）
    """
    client = get_vision_client()
    # 图片二进制 → base64 文本（OpenAI 视觉接口只收 data URL 字符串）
    b64 = base64.b64encode(image_bytes).decode("ascii")
    resp = client.chat.completions.create(
        model=config.VISION_MODEL,
        temperature=0.1,  # 看图提取信息要稳定，温度调低
        messages=[
            {
                "role": "user",  # 视觉模型要求图片放 user 消息
                "content": [
                    {"type": "text", "text": prompt},                 # 文字问题
                    {"type": "image_url",                              # 图片
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
    )
    return resp.choices[0].message.content or ""
