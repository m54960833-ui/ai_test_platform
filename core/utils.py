# 一些零散的公共小工具
import json
from pathlib import Path

import yaml


def load_config():
    """读项目根目录的 config.yaml，没有就返回空 dict（尽量不崩）。"""
    root = Path(__file__).resolve().parent.parent
    cfg_path = root / "config.yaml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def json_get(data, path: str):
    """
    极简版 JSONPath，只支持 a.b.c 和 a[0].b 这种写法。
    值取不到就抛 KeyError，调用方自己兜。
    """
    if not path:
        return data
    # 把 a[0] 拆成 a、0 两段
    parts = []
    for seg in path.split("."):
        if "[" in seg and seg.endswith("]"):
            head, rest = seg.split("[", 1)
            if head:
                parts.append(head)
            idx = rest[:-1].strip("'\"")
            parts.append(idx)
        else:
            parts.append(seg)
    cur = data
    for p in parts:
        if isinstance(cur, list):
            cur = cur[int(p)]
        elif isinstance(cur, dict):
            cur = cur[p]
        else:
            raise KeyError(f"路径 {path} 取不到值")
    return cur


def now_str():
    import datetime

    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
