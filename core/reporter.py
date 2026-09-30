"""
报告生成：把 RunReport 落盘成 JSON + 一份能直接双击打开的 HTML 报告。

HTML 模板就内联在这了，没去单独搞个模板文件，小工具懒得拆。
"""
import json
from pathlib import Path

from .models import RunReport
from .utils import now_str

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>测试报告 - {{rid}}</title>
<style>
  body{font-family:"Microsoft YaHei",sans-serif;margin:24px;background:#f5f6fa;color:#333}
  .wrap{max-width:960px;margin:0 auto}
  h1{font-size:22px}
  .summary{display:flex;gap:16px;margin:16px 0}
  .card{background:#fff;border-radius:8px;padding:14px 18px;box-shadow:0 1px 4px rgba(0,0,0,.08);min-width:90px}
  .card b{font-size:26px;display:block}
  .ok b{color:#2ecc71}.fail b{color:#e74c3c}.skip b{color:#f39c12}
  table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
  th,td{padding:9px 12px;border-bottom:1px solid #eee;text-align:left;font-size:13px}
  th{background:#fafafa}
  .tag{padding:2px 8px;border-radius:10px;font-size:12px;color:#fff}
  .tag.pass{background:#2ecc71}.tag.fail{background:#e74c3c}.tag.skip{background:#f39c12}
  .err{color:#e74c3c;font-size:12px;white-space:pre-wrap}
</style>
</head>
<body>
<div class="wrap">
  <h1>自动化测试报告</h1>
  <p>报告编号：{{rid}}　｜　开始时间：{{started}}　｜　执行方式：{{gen}}　｜　总耗时：{{duration}}s</p>
  <div class="summary">
    <div class="card"><b>{{total}}</b>总计</div>
    <div class="card ok"><b>{{passed}}</b>通过</div>
    <div class="card fail"><b>{{failed}}</b>失败</div>
    <div class="card skip"><b>{{skipped}}</b>跳过</div>
    <div class="card"><b>{{rate}}%</b>通过率</div>
  </div>
  <table>
    <tr><th>#</th><th>用例</th><th>来源</th><th>结果</th><th>耗时(s)</th><th>说明</th></tr>
    {% for r in rows %}
    <tr>
      <td>{{loop.index}}</td>
      <td>{{r.name}}</td>
      <td>{{r.src}}</td>
      <td><span class="tag {{r.cls}}">{{r.txt}}</span></td>
      <td>{{r.elapsed}}</td>
      <td class="err">{{r.err}}</td>
    </tr>
    {% endfor %}
  </table>
</div>
</body>
</html>
"""


def save_report(report: RunReport, gen_mode: str = "") -> str:
    """落盘报告，返回报告 id（用于 Web 端回查）。"""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    rid = f"report_{now_str()}"
    report.report_id = rid

    json_path = REPORTS_DIR / f"{rid}.json"
    # 转成可序列化的普通 dict
    payload = {
        "report_id": rid,
        "started_at": report.started_at,
        "gen_mode": gen_mode or report.gen_mode,
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "skipped": report.skipped,
        "pass_rate": report.pass_rate,
        "duration": report.duration,
        "results": [
            {
                "name": r.case.name,
                "source": r.case.source_file,
                "passed": r.passed,
                "status_code": r.status_code,
                "elapsed": r.elapsed,
                "errors": r.errors,
                "response": r.response_text,
                "skip": r.skip_reason,
            }
            for r in report.results
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    _write_html(report, rid)
    return rid


def _write_html(report: RunReport, rid: str):
    from jinja2 import Template

    rows = []
    for r in report.results:
        if r.passed:
            cls, txt = "pass", "通过"
        elif r.skip_reason:
            cls, txt = "skip", "跳过"
        else:
            cls, txt = "fail", "失败"
        rows.append(
            {
                "name": r.case.name,
                "src": r.case.source_file,
                "cls": cls,
                "txt": txt,
                "elapsed": r.elapsed,
                "err": "\n".join(r.errors) if r.errors else (r.skip_reason or "-"),
            }
        )
    tpl = Template(_HTML_TEMPLATE)
    html = tpl.render(
        rid=rid,
        started=report.started_at,
        gen={"manual": "手动", "llm": "AI生成", "mock": "模板生成"}.get(report.gen_mode, report.gen_mode),
        duration=report.duration,
        total=report.total,
        passed=report.passed,
        failed=report.failed,
        skipped=report.skipped,
        rate=report.pass_rate,
        rows=rows,
    )
    with open(REPORTS_DIR / f"{rid}.html", "w", encoding="utf-8") as f:
        f.write(html)


def list_reports() -> list[dict]:
    """列出全部报告（供 Web 端用），只挑 JSON 的当主文件。"""
    out = []
    for f in sorted(REPORTS_DIR.glob("report_*.json"), reverse=True):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        out.append(
            {
                "report_id": data["report_id"],
                "started_at": data["started_at"],
                "total": data["total"],
                "passed": data["passed"],
                "failed": data["failed"],
                "pass_rate": data["pass_rate"],
                "duration": data["duration"],
                "gen_mode": data["gen_mode"],
            }
        )
    return out
