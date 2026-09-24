# 03-llm：DeepSeek 客户端（`src/astock_agent/llm.py`）

## 职责

全项目唯一的 LLM 出入口。两种接法：
- **文本模型**：langchain-openai 的 `ChatOpenAI`（OpenAI 兼容协议）
- **视觉模型**：openai SDK 直连（base64 内联传图）

## 对外接口

| 函数 | 返回 | 用途 | 失败行为 |
|---|---|---|---|
| `has_llm() -> bool` | 布尔 | 判断 Key 是否已配置 | - |
| `chat_text(prompt, system="", temperature=0.2) -> str` | 文本 | 自由文本（结果说明等） | 返回空串（本实现无重试） |
| `chat_json(prompt, system="") -> dict\|list` | JSON | 结构化输出（规则提炼） | 抛 ValueError（解析失败） |
| `parse_json_text(text) -> dict\|list` | JSON | 从 LLM 输出稳健解析 JSON | 抛 ValueError |
| `analyze_image(image_bytes, mime, prompt) -> str` | 文本 | 视觉模型看单张截图 | 抛异常 |
| `get_chat_llm(temperature, json_mode) -> ChatOpenAI` | 客户端 | 文本模型客户端工厂 | 未配 Key 抛 LLMNotConfiguredError |
| `get_vision_client() -> OpenAI` | 客户端 | 视觉模型客户端工厂 | 未配 Key 抛 LLMNotConfiguredError |

异常：`LLMNotConfiguredError(RuntimeError)`——未配置 Key 时抛出。

## 关键概念

- **JSON 模式**：`response_format={"type": "json_object"}` 要求模型只输出
  合法 JSON。DeepSeek 要求提示词里出现"JSON"字样才启用，所以调用方
  （extract.py 的 build_prompt）必须写明"输出 JSON"。
- **JSON 解析三级兜底**（`parse_json_text`）：
  1. 直接 `json.loads`
  2. 剥 ```` ```json ... ``` ```` 围栏
  3. 截取第一个 `{` 到最后一个 `}`（或 `[` `]`）
- **base64 data URL**：视觉接口的图片以 `data:image/png;base64,xxxx`
  内联在消息里，不传文件路径。

## 谁依赖它

- `learn/vision.py`：`analyze_image` + `parse_json_text`
- `learn/extract.py`：`chat_json`
- `engine.py`：`has_llm` + `chat_json`
- `main.py`：`has_llm`（学习前置校验）

## 修改注意点

1. **文本和视觉用两套客户端**，是历史原因（langchain-openai 对视觉
   消息封装不便）。合并时注意保持两个函数的签名不变，调用方很多。
2. **`chat_json` 失败抛异常**（与 `chat_text` 返回空串不同），
   调用方 extract.py 没有 try/except，异常会一路冒泡到学习任务失败。
   若要改成"失败返回默认值"，需同步调整 extract.py 的错误处理。
3. **Key 校验前置**：`get_chat_llm`/`get_vision_client` 入口先
   `_require_key()`，未配置直接抛错，避免发出注定失败的请求。
4. 超时 180 秒 / max_retries 2 是针对 DeepSeek 高峰慢响应调优过的，
   改动需重新评估。
