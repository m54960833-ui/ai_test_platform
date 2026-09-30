"""
Web 管理平台的 API：用例管理、触发执行、报告查看、AI 生成/分析。

跑测试依赖被测服务在线（127.0.0.1:8001），不在线会返回明确提示。
"""
import json
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.case_loader import load_all_cases, CASES_DIR
from core.http_client import ApiClient
from core.llm_engine import get_engine
from core.reporter import save_report, list_reports, REPORTS_DIR
from core.runner import run_cases

router = APIRouter(prefix="/api")

# Web 端手动加的用例统一放这个文件
WEB_CASES_FILE = CASES_DIR / "web.yaml"


class CaseIn(BaseModel):
    name: str = Field(min_length=1)
    method: str = "GET"
    url: str = Field(min_length=1)
    body: dict | None = None
    # 用 validates 避免跟 pydantic BaseModel 内置的 validate 撞名
    validates: list = Field(default_factory=list)


def _server_alive() -> bool:
    try:
        c = ApiClient()
        r = c.session.get(f"{c.base_url}/api/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


@router.get("/cases")
def list_cases():
    cases = load_all_cases()
    return [
        {
            "name": c.name,
            "method": c.method,
            "url": c.url,
            "source": c.source_file,
            "validates": len(c.validate or []),
        }
        for c in cases
    ]


@router.post("/cases")
def add_case(req: CaseIn):
    # 追加到 web.yaml，保持文件是列表结构
    items = []
    if WEB_CASES_FILE.exists():
        import yaml

        with open(WEB_CASES_FILE, "r", encoding="utf-8") as f:
            items = yaml.safe_load(f) or []
    items.append(
        {
            "name": req.name,
            "method": req.method,
            "url": req.url,
            "body": req.body,
            "validate": req.validates,
        }
    )
    import yaml

    with open(WEB_CASES_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(items, f, allow_unicode=True, sort_keys=False)
    return {"code": 0, "message": f"已添加用例 {req.name}"}


@router.delete("/cases/{name}")
def delete_case(name: str):
    if not WEB_CASES_FILE.exists():
        raise HTTPException(status_code=404, detail="web.yaml 不存在")
    import yaml

    with open(WEB_CASES_FILE, "r", encoding="utf-8") as f:
        items = yaml.safe_load(f) or []
    remain = [i for i in items if i.get("name") != name]
    if len(remain) == len(items):
        raise HTTPException(status_code=404, detail=f"未找到用例 {name}")
    with open(WEB_CASES_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(remain, f, allow_unicode=True, sort_keys=False)
    return {"code": 0, "message": f"已删除用例 {name}"}


@router.post("/run")
def run_tests():
    if not _server_alive():
        raise HTTPException(status_code=503, detail="被测服务未在线，请先运行 python run.py server")
    client = ApiClient()
    # 先准备登录态，业务接口大多要求 token
    try:
        client.login()
    except Exception:
        # 登录失败不阻断，让后续用例自己暴露问题
        pass
    report = run_cases(load_all_cases(), client, gen_mode="manual")
    rid = save_report(report)
    return {
        "report_id": rid,
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "pass_rate": report.pass_rate,
        "duration": report.duration,
    }


@router.get("/reports")
def reports():
    return list_reports()


@router.get("/reports/{rid}")
def report_detail(rid: str):
    p = REPORTS_DIR / f"{rid}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="报告不存在")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/ai/gen")
def ai_generate():
    if not _server_alive():
        raise HTTPException(status_code=503, detail="被测服务未在线，无法读取 openapi")
    # 先读被测服务的 openapi.json
    c = ApiClient()
    resp = c.session.get(f"{c.base_url}/openapi.json", timeout=10)
    spec = resp.json()

    engine = get_engine()
    try:
        cases = engine.generate_test_cases(spec)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI 生成失败: {e}")

    # 落盘到 _ai_generated 目录
    from core.utils import now_str

    out_dir = CASES_DIR / "_ai_generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    gen_mode = "llm" if engine.__class__.__name__ == "LLMClient" else "mock"
    fname = out_dir / f"ai_{now_str()}.yaml"
    import yaml

    with open(fname, "w", encoding="utf-8") as f:
        yaml.safe_dump(cases, f, allow_unicode=True, sort_keys=False)
    return {
        "file": fname.name,
        "count": len(cases),
        "gen_mode": gen_mode,
        "message": "AI 用例已生成（大模型生成）" if gen_mode == "llm" else "AI 用例已生成（未配置 Key，走模板生成）",
    }


@router.post("/ai/analyze")
def ai_analyze():
    # 拿最近一份报告的失败用例去让模型分析
    reports = list_reports()
    if not reports:
        raise HTTPException(status_code=404, detail="还没有报告可分析")
    rid = reports[0]["report_id"]
    with open(REPORTS_DIR / f"{rid}.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    failures = [
        {"name": r["name"], "errors": r["errors"]}
        for r in data["results"]
        if not r["passed"] and not r.get("skip")
    ]
    engine = get_engine()
    text = engine.analyze_badcases(failures)
    return {"report_id": rid, "failed_count": len(failures), "analysis": text}
