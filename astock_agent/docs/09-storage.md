# 09-storage：文件存储层（`src/astock_agent/storage.py`）

## 职责

数据的"落盘层"。不接数据库，用文件夹 + YAML/JSON 文件当存储，
用户可以直接打开文件看/改/备份。

## 四个存储区（目录约定，全项目通用）

```
astock_agent/
├── cases/   案例库：模式名/案例名/截图1.png + 说明.md
├── rules/   规则库：模式名.yaml（人审通过的正式规则）
├── drafts/  草案：模式名.yaml（学习产出，待人审）
└── runs/    运行记录：时间戳.json（每次选股完整结果）
```

## 函数清单

### 案例库
- `list_modes()`：模式列表（含案例数/有无规则/有无草案）
- `create_mode(name)`：建模式文件夹（非法文件名字符→下划线）
- `delete_mode(mode_id)`：删模式（案例+规则+草案一起清）
- `list_cases(mode_id)` / `read_case(mode_id, case_id)`：案例列表/详情
- `add_case(...)`：建案例（重名自动加 `_2/_3` 后缀，截图统一命名截图N.ext）
- `delete_case(...)`

### 规则库 / 草案
- `load_rule(mode_id) -> Rule | None` / `save_rule(rule)`：正式规则读写
- `load_draft(mode_id) -> dict | None` / `save_draft(...)` / `delete_draft(...)`
- `confirm_draft(mode_id) -> Rule`：草案转正（校验+打时间戳+存rules+删草案）

### 运行记录
- `save_run(run)` / `list_runs()`（摘要）/ `load_run(run_id) -> RunResult | None`

## 关键约定

- **容错**：`load_rule`/`load_draft`/`load_run` 文件损坏一律返回 None，
  一个坏文件不拖垮服务。
- **中文友好**：YAML `allow_unicode=True`、JSON `ensure_ascii=False`，
  文件里中文直接可读。
- **模式名即文件名**：`mode_id` 直接用作文件夹名和 yaml 文件名，
  所以 `create_mode` 要清洗非法字符。

## 谁依赖它

- `main.py`：几乎所有端点
- `engine.py`：`load_rule`（运行入口）、`save_run`（存档）
- `learn` 管线：通过 main.py 间接使用

## 修改注意点

1. **草案结构**：`{"rule": {...}, "evidence": {cond_id: [案例名]}, "diff": {...}}`，
   确认时只取 `draft["rule"]`。改草案结构要同步改 main.py 的
   save_draft/confirm_draft 和前端 app.js。
2. **加新的持久化数据**：优先放这四个目录之一，不要另起新目录；
   新目录要加进 `config.ensure_dirs()`。
3. `delete_mode` 用 `shutil.rmtree`（递归删除），只对"模式名清洗过"
   的路径使用，防止路径注入删到别处。
