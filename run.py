"""
AITestPlatform 统一入口。

用法：
  python run.py server   只启动被测服务(8001)
  python run.py web      启动 Web 管理平台(8002)，会自动带上被测服务
  python run.py test     等被测服务在线后跑一遍全部用例并生成报告
  python run.py dev      被测服务 + Web 一起启动

跑测试前需要被测服务在线；用 server / dev / web 起服务即可。
"""
import sys
import threading
import time

from core.utils import load_config


def _wait_server(host: str, port: int, timeout: int = 20):
    """轮询 /api/health，等服务真正起来再往下走。"""
    import requests

    base = f"http://{host}:{port}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{base}/api/health", timeout=2).status_code == 200:
                return base
        except Exception:
            pass
        time.sleep(0.4)
    raise RuntimeError(f"被测服务 {base} 在 {timeout}s 内未就绪")


def start_server_thread(cfg: dict) -> threading.Thread:
    import uvicorn
    from app.main import app as demo_app

    srv = cfg.get("server", {})
    t = threading.Thread(
        target=lambda: uvicorn.run(demo_app, host=srv.get("host", "127.0.0.1"), port=srv.get("port", 8001), log_level="warning"),
        daemon=True,
    )
    t.start()
    return t


def cmd_server(cfg: dict):
    srv = cfg.get("server", {})
    print(f"[server] 被测服务启动中 http://{srv.get('host','127.0.0.1')}:{srv.get('port',8001)}")
    start_server_thread(cfg).join()


def cmd_test(cfg: dict):
    srv = cfg.get("server", {})
    base = _wait_server(srv.get("host", "127.0.0.1"), srv.get("port", 8001))
    print(f"[test] 被测服务在线: {base}")

    from core.case_loader import load_all_cases
    from core.http_client import ApiClient
    from core.reporter import save_report
    from core.runner import run_cases

    client = ApiClient(base_url=base)
    try:
        client.login()
        print("[test] 已准备登录态 (demo)")
    except Exception as e:
        print(f"[test] 登录态准备失败，继续执行: {e}")

    cases = load_all_cases(include_ai=False)  # 命令行回归只跑人工精修过的精选用例
    print(f"[test] 共加载 {len(cases)} 条用例")
    report = run_cases(cases, client)
    rid = save_report(report)

    print("\n========== 测试结果 ==========")
    print(f"总数 {report.total} | 通过 {report.passed} | 失败 {report.failed} | 跳过 {report.skipped}")
    print(f"通过率 {report.pass_rate}% | 耗时 {report.duration}s")
    print(f"报告已生成: reports/{rid}.html（可直接双击打开）")
    if report.failed:
        print("\n失败用例：")
        for r in report.results:
            if not r.passed and not r.skip_reason:
                print(f"  - {r.case.name} [{r.case.source_file}]: {'; '.join(r.errors[:2])}")
    return rid


def cmd_web(cfg: dict):
    from web.server import app as web_app

    # 先确保被测服务在线，再起 web
    srv = cfg.get("server", {})
    start_server_thread(cfg)
    base = _wait_server(srv.get("host", "127.0.0.1"), srv.get("port", 8001))
    print(f"[web] 被测服务在线: {base}")

    import uvicorn

    w = cfg.get("web", {})
    print(f"[web] Web 平台启动中 http://{w.get('host','127.0.0.1')}:{w.get('port',8002)}")
    uvicorn.run(web_app, host=w.get("host", "127.0.0.1"), port=w.get("port", 8002), log_level="warning")


def cmd_dev(cfg: dict):
    # dev = server 线程 + web 主进程，Ctrl+C 一起退出
    from web.server import app as web_app

    start_server_thread(cfg)
    srv = cfg.get("server", {})
    base = _wait_server(srv.get("host", "127.0.0.1"), srv.get("port", 8001))
    print(f"[dev] 被测服务在线: {base}")

    import uvicorn

    w = cfg.get("web", {})
    print(f"[dev] Web 平台: http://{w.get('host','127.0.0.1')}:{w.get('port',8002)}")
    uvicorn.run(web_app, host=w.get("host", "127.0.0.1"), port=w.get("port", 8002), log_level="warning")


def main():
    cfg = load_config()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "server":
        cmd_server(cfg)
    elif cmd == "test":
        cmd_test(cfg)
    elif cmd == "web":
        cmd_web(cfg)
    elif cmd == "dev":
        cmd_dev(cfg)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
