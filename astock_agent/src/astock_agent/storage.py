"""文件存储层：案例库(cases/) / 规则库(rules/) / 草案(drafts/) / 运行记录(runs/)

【这个文件是干什么的】
数据的"落盘层"（把数据保存到硬盘）。整个项目不接数据库，直接用
文件夹 + YAML/JSON 文件当存储，好处是：用户可以自己打开文件看、
改、备份，对小白友好。

【四个存储区（目录结构约定，全项目通用）】
- cases/模式名/案例名/截图1.png + 说明.md —— 学习素材（案例库）
- rules/模式名.yaml —— 人审通过的正式规则（运行引擎读这个）
- drafts/模式名.yaml —— LLM 学出来的规则草案（等人审，审完转正）
- runs/时间戳.json —— 每次选股运行的完整结果（历史记录）

【给小白的关键概念】
- YAML：比 JSON 更易读的配置文件格式（不需要写引号逗号），
  用 yaml.safe_dump 写、yaml.safe_load 读。
- Pydantic 序列化：Rule.model_dump() 把对象转 dict 再存 YAML；
  Rule.model_validate() 读回来时做字段校验（防手改坏文件）。
- 幂等与容错：load_rule/load_draft 读文件失败返回 None 而不是崩，
  保证一个坏文件不会拖垮整个服务。
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

import yaml

from . import config
from .models import Rule, RunResult


# ---------------- 案例库 ----------------

def list_modes() -> list[dict]:
    """模式列表：cases/ 下每个文件夹即一个模式

    返回列表元素含：模式id/案例数/是否有正式规则/是否有待审草案/规则内容。
    Web 首页（模式管理）直接渲染这个列表。
    """
    modes = []
    if not config.CASES_DIR.is_dir():
        return modes
    for d in sorted(config.CASES_DIR.iterdir()):
        if not d.is_dir():
            continue
        cases = list_cases(d.name)
        rule = load_rule(d.name)
        draft = load_draft(d.name)
        modes.append({
            "mode_id": d.name,
            "name": d.name,
            "case_count": len(cases),
            "has_rule": rule is not None,    # 前端据此显示"已就绪/未学习"状态
            "has_draft": draft is not None,  # 前端据此提示"有待确认草案"
            "rule": rule.model_dump() if rule else None,
        })
    return modes


def create_mode(name: str) -> str:
    """新建模式（cases/ 下建文件夹）

    模式名会做"文件名安全"处理：把 Windows 不允许出现在文件名里的
    字符 \\ / : * ? " < > | 替换成下划线。
    """
    name = re.sub(r'[\\/:*?"<>|]', "_", (name or "").strip())
    if not name:
        raise ValueError("模式名不能为空")
    (config.CASES_DIR / name).mkdir(parents=True, exist_ok=True)
    return name


def delete_mode(mode_id: str) -> None:
    """删除模式：案例文件夹整体删除 + 规则文件 + 草案文件一起清掉"""
    d = config.CASES_DIR / mode_id
    if d.is_dir():
        shutil.rmtree(d)  # 递归删文件夹（比 os.remove 危险，只对已知路径使用）
    # 同时清掉 rules/xxx.yaml 和 drafts/xxx.yaml（如果存在）
    for p in (config.RULES_DIR / (mode_id + ".yaml"),
              config.DRAFTS_DIR / (mode_id + ".yaml")):
        if p.exists():
            p.unlink()


def list_cases(mode_id: str) -> list[dict]:
    """某模式下案例列表：每个子文件夹一个案例（截图 + 说明.md）

    案例文件夹里所有图片文件都是该案例的截图，说明.md 是文字描述。
    """
    d = config.CASES_DIR / mode_id
    out = []
    if not d.is_dir():
        return out
    for c in sorted(d.iterdir()):
        if not c.is_dir():
            continue
        # 按文件名排序收集该案例下的截图
        images = sorted(p.name for p in c.iterdir()
                        if p.suffix.lower() in config.IMAGE_EXTS)
        desc = ""
        md = c / "说明.md"
        if md.exists():
            desc = md.read_text(encoding="utf-8")
        out.append({
            "case_id": c.name,
            "images": images,
            "image_count": len(images),
            "description": desc,
        })
    return out


def read_case(mode_id: str, case_id: str) -> dict:
    """读取单个案例完整内容（含图片绝对路径）

    绝对路径是给学习管线用的（vision.py 读图片文件）；
    前端展示走 /api/cases/.../image 接口（相对路径）。
    """
    d = config.CASES_DIR / mode_id / case_id
    images = sorted(p for p in d.iterdir() if p.suffix.lower() in config.IMAGE_EXTS)
    desc = ""
    md = d / "说明.md"
    if md.exists():
        desc = md.read_text(encoding="utf-8")
    return {"case_id": case_id, "image_paths": images, "description": desc}


def add_case(mode_id: str, case_name: str, description: str,
             image_files: list[tuple[str, bytes]]) -> str:
    """新增案例：建案例文件夹 + 说明.md + 截图文件（重名自动加序号）

    参数：
        mode_id: 模式名
        case_name: 案例名（用户填的，可为空 → 用时间戳当名字）
        description: 案例文字说明（写入 说明.md）
        image_files: [(原始文件名, 文件字节内容), ...] 上传的截图

    返回实际创建的案例文件夹名（重名时会被追加 _2/_3 后缀）。
    """
    mode_dir = config.CASES_DIR / mode_id
    if not mode_dir.is_dir():
        raise ValueError("模式不存在: %s" % mode_id)
    # 清理非法文件名字符；空名字 → 用当前时间生成 "案例MMDDHHMMSS"
    case_name = re.sub(r'[\\/:*?"<>|]', "_", (case_name or "").strip()) \
        or time.strftime("案例%m%d%H%M%S")
    case_dir = mode_dir / case_name
    # 重名处理：案例 / 案例_2 / 案例_3 ... 直到找到一个不存在的名字
    i = 2
    while case_dir.exists():
        case_dir = mode_dir / ("%s_%d" % (case_name, i))
        i += 1
    case_dir.mkdir(parents=True)
    (case_dir / "说明.md").write_text(description or "", encoding="utf-8")
    # 截图统一重命名为 截图1.png / 截图2.jpg ...（顺序即上传顺序）
    for idx, (fname, data) in enumerate(image_files, 1):
        ext = Path(fname).suffix.lower()
        ext = ext if ext in config.IMAGE_EXTS else ".png"  # 未知类型按 png 存
        (case_dir / ("截图%d%s" % (idx, ext))).write_bytes(data)
    return case_dir.name


def delete_case(mode_id: str, case_id: str) -> None:
    """删除单个案例（整个案例文件夹）"""
    d = config.CASES_DIR / mode_id / case_id
    if d.is_dir():
        shutil.rmtree(d)


# ---------------- 规则库 / 草案 ----------------

def _rule_path(mode_id: str) -> Path:
    """规则的存储路径：rules/模式名.yaml"""
    return config.RULES_DIR / (mode_id + ".yaml")


def _draft_path(mode_id: str) -> Path:
    """草案的存储路径：drafts/模式名.yaml"""
    return config.DRAFTS_DIR / (mode_id + ".yaml")


def load_rule(mode_id: str) -> Rule | None:
    """读正式规则；文件不存在或内容损坏返回 None（不抛异常，容错）"""
    p = _rule_path(mode_id)
    if not p.exists():
        return None
    try:
        # YAML 文本 → dict → Pydantic 校验 → Rule 对象
        return Rule.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
    except Exception:
        return None


def save_rule(rule: Rule) -> None:
    """写正式规则（Rule 对象 → YAML 文件）

    allow_unicode=True：中文不转义成 \\uXXXX，保持文件可读。
    sort_keys=False：保持字段顺序，diff 时更友好。
    """
    config.RULES_DIR.mkdir(parents=True, exist_ok=True)
    _rule_path(rule.mode_id).write_text(
        yaml.safe_dump(rule.model_dump(), allow_unicode=True, sort_keys=False),
        encoding="utf-8")


def load_draft(mode_id: str) -> dict | None:
    """读草案（学习产出、待人审的规则）；不存在/损坏返回 None"""
    p = _draft_path(mode_id)
    if not p.exists():
        return None
    try:
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def save_draft(mode_id: str, draft: dict) -> None:
    """写草案（前端编辑保存时调用）"""
    config.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    _draft_path(mode_id).write_text(
        yaml.safe_dump(draft, allow_unicode=True, sort_keys=False),
        encoding="utf-8")


def delete_draft(mode_id: str) -> None:
    """删草案（人审确认后清掉；也用于"放弃草案"）"""
    p = _draft_path(mode_id)
    if p.exists():
        p.unlink()


def confirm_draft(mode_id: str) -> Rule:
    """确认草案：drafts/ 中的规则经过人审后落盘为正式规则

    流程：读草案 → Pydantic 校验 → 打上确认时间戳 → 存 rules/ → 删草案。
    草案结构：{"rule": {...}, "notes": "...", "case_count": n}
    """
    draft = load_draft(mode_id)
    if not draft or "rule" not in draft:
        raise ValueError("该模式没有待确认的草案")
    rule = Rule.model_validate(draft["rule"])
    rule.verified_at = time.strftime("%Y-%m-%d %H:%M:%S")  # 记录人审时间
    save_rule(rule)
    delete_draft(mode_id)
    return rule


# ---------------- 运行记录 ----------------

def save_run(run: RunResult) -> None:
    """保存一次运行结果：runs/{run_id}.json

    ensure_ascii=False 让中文直接可读；indent=2 格式化便于肉眼查看。
    """
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (config.RUNS_DIR / ("%s.json" % run.run_id)).write_text(
        run.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")


def list_runs() -> list[dict]:
    """运行记录列表（按文件名倒序 = 最新在前）

    只返回摘要字段（不含完整股票明细），列表页轻量加载；
    点开某条记录时再 load_run 拉完整内容。
    """
    out = []
    if not config.RUNS_DIR.is_dir():
        return out
    for p in sorted(config.RUNS_DIR.glob("*.json"), reverse=True):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue  # 单个记录文件损坏不影响整个列表
        out.append({"run_id": r.get("run_id"), "mode_id": r.get("mode_id"),
                    "mode_name": r.get("mode_name"), "time": r.get("time"),
                    "status": r.get("status"),
                    "stock_count": len(r.get("stocks") or [])})
    return out


def load_run(run_id: str) -> RunResult | None:
    """读单次运行完整结果；不存在/损坏返回 None"""
    p = config.RUNS_DIR / ("%s.json" % run_id)
    if not p.exists():
        return None
    try:
        return RunResult.model_validate(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return None
