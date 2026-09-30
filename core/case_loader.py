"""
用例加载器：把 cases/ 目录下的 YAML/JSON 文件读进来，转成 Case 对象。

用例文件结构：一个文件是一个列表，每个元素是一条用例，例如
---
- name: 登录-正常
  method: POST
  url: /api/auth/login
  body:
    username: "demo"
    password: "demo1234"
  validate:
    - type: jsonpath
      path: "$.code"
      value: 0
"""
from pathlib import Path

from .models import Case
from .utils import load_yaml

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


def load_all_cases(cases_dir: Path = None, include_ai: bool = True) -> list[Case]:
    """加载目录下所有用例文件，返回排好序的用例列表。

    主目录 cases/ 里是人工维护的精选用例；_ai_generated/ 是 AI 批量生成的"初稿"，
    需要人工复核后才能纳入回归。include_ai=False 时只返回精选用例，
    用于命令行跑稳定的回归套件；Web 端保留 AI 初稿以便复核。
    """
    d = cases_dir or CASES_DIR
    files = sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")) + sorted(d.glob("*.json"))
    if include_ai:
        ai_dir = d / "_ai_generated"
        if ai_dir.exists():
            files += sorted(ai_dir.glob("*.yaml")) + sorted(ai_dir.glob("*.yml"))
    cases: list[Case] = []
    for f in files:
        cases.extend(load_case_file(f))
    return cases


def load_case_file(path: Path) -> list[Case]:
    data = load_yaml(path)
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(f"用例文件 {path.name} 顶层必须是列表")
    out = []
    for idx, item in enumerate(data):
        # 文件里的 name 可能重复，用 文件名#序号 兜底保证唯一
        name = item.get("name") or f"{path.stem}#{idx + 1}"
        out.append(
            Case(
                name=name,
                method=item.get("method", "GET").upper(),
                url=item.get("url", ""),
                headers=item.get("headers") or {},
                body=item.get("body"),
                validate=item.get("validate") or [],
                save=item.get("save") or [],
                source_file=path.name,
            )
        )
    return out
