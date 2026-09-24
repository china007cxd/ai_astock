# 01-config：全局配置（`src/astock_agent/config.py`）

## 职责

项目的"总开关"。所有路径、服务地址、模型配置都从这里读取，
其他模块不写死配置，全部引用这里。

## 关键变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `BASE_DIR` | 项目根目录 | 由本文件位置向上两级推导 |
| `CASES_DIR` / `RULES_DIR` / `RUNS_DIR` / `DRAFTS_DIR` | 四个数据目录 | 文件存储的四个根目录 |
| `WEB_DIR` | `web/` | 前端静态资源目录 |
| `DEEPSEEK_API_KEY` | 空 | 从 `.env` 读取；为空则 LLM 功能不可用 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 接口地址，一般不用改 |
| `TEXT_MODEL` | `deepseek-chat` | 文本模型（规则提炼/结果说明） |
| `VISION_MODEL` | `deepseek-v4-flash-vision-exp` | 视觉模型（截图解读） |
| `ASTOCK_BASE` | `http://127.0.0.1:8765` | astock 数据服务地址 |
| `AGENT_HOST` / `AGENT_PORT` | `127.0.0.1` / `8766` | agent 自身监听地址 |
| `IMAGE_EXTS` | png/jpg/jpeg/gif/webp | 案例截图允许的扩展名集合 |

## 对外的函数

- `ensure_dirs()`：创建所有数据目录（服务启动时调用一次，幂等）

## 数据流

`.env 文件 → load_dotenv() → os.getenv() → 全局常量 → 各模块引用`

## 谁依赖它

几乎全部模块都 `from . import config`。

## 修改注意点

1. **加新配置**：先加常量（带 `os.getenv("名字", 默认值)`），
   再在 `.env.example` 里补一行说明。
2. **`ensure_dirs` 必须在服务启动最早期调用**——`main.py` 顶部已调用，
   新增目录时记得加进循环里的元组。
3. **改 `ASTOCK_BASE` 或端口**：要与 `astock/` 下看盘服务的实际监听
   端口一致，与 `启动.bat` 中的启动参数一致。
