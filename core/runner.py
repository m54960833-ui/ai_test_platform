"""
测试执行引擎（runner）：拿着 ApiClient 把一串 Case 跑掉。

要点：
1. 全程维护一个 env 字典，用例之间靠它传数据（比如注册拿到 user_id 传给下一个用例）
2. 支持在 header/body 里写 @{envKey} 引用、@rand 生成随机后缀
3. 断言在 validate 里声明，type 支持 status_code / jsonpath / contains / regex
4. 跑完返回一个 RunReport，交给 reporter 落盘
"""
import re
import random
import string
import time

from .http_client import ApiClient
from .models import Case, CaseResult, RunReport
from .utils import json_get


def _rand_token():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def _resolve(value, env):
    """把字符串里的 @{key} 和 @rand 替换成实际值，递归处理 dict/list。

    注意：@rand 可能嵌在字符串里（比如 "user_@{rand}"），所以要整体做正则替换。
    """
    if isinstance(value, dict):
        return {k: _resolve(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, env) for v in value]
    if isinstance(value, str):
        # @rand 每出现一次生成一个新的随机串，保证多次使用不会撞；
        # 兼容 @{rand} 和 @rand 两种写法（用例里一般写 @{rand}）
        out = re.sub(r"@\{rand\}", lambda m: _rand_token(), value)
        out = re.sub(r"@rand", lambda m: _rand_token(), out)
        for m in re.findall(r"@\{([^}]+)\}", out):
            if m in env:
                out = out.replace(f"@{{{m}}}", str(env[m]))
        return out
    return value


def _check_assertion(rule, resp, resp_json, errs):
    """对一条断言做校验，不过就记一条错误。

    AI 生成的用例偶尔会混进格式不对的断言（比如把整条写成了字符串），
    这里统一容错：记成该用例失败，而不是让整个执行崩溃。
    """
    if not isinstance(rule, dict):
        errs.append(f"断言格式不正确: {rule!r}（应为 {{type, value, ...}} 对象）")
        return
    typ = rule.get("type")
    if typ == "status_code":
        expected = rule.get("value")
        expects = expected if isinstance(expected, list) else [expected]
        if resp.status_code not in expects:
            errs.append(f"状态码期望 {expects}，实际 {resp.status_code}")
    elif typ == "jsonpath":
        path = rule.get("path", "").lstrip("$").lstrip(".")
        try:
            actual = json_get(resp_json, path)
        except (KeyError, IndexError, TypeError, ValueError):
            errs.append(f"jsonpath {rule.get('path')} 取值失败（响应可能不是预期结构）")
            return
        expected = rule.get("value")
        if expected == "@nonempty":
            # 只要求取到值且非空，常用于 token、列表长度这类
            if actual is None or actual == "" or actual == []:
                errs.append(f"{rule.get('path')} 应为非空，实际为空")
        elif actual != expected:
            errs.append(f"{rule.get('path')} 期望 {expected!r}，实际 {actual!r}")
    elif typ == "contains":
        text = resp.text
        if rule.get("value") not in text:
            errs.append(f"响应文本应包含 {rule.get('value')!r}")
    elif typ == "regex":
        if not re.search(rule.get("value", ""), resp.text):
            errs.append(f"响应文本未匹配正则 {rule.get('value')!r}")
    else:
        errs.append(f"未知断言类型 {typ!r}")


def _do_save(rule, resp, resp_json, body_sent, env):
    key = rule.get("key")
    if not key:
        return
    src = rule.get("from", "")
    if src.startswith("body."):
        # 从实际发出去的请求体里取（这里可能用了 @rand，值是运行时的）
        try:
            env[key] = json_get(body_sent, src[len("body."):])
        except Exception:
            pass
    else:
        path = src.lstrip("$").lstrip(".")
        try:
            env[key] = json_get(resp_json, path)
        except Exception:
            pass


def run_cases(cases: list[Case], client: ApiClient, gen_mode: str = "manual") -> RunReport:
    report = RunReport(started_at=time.strftime("%Y-%m-%d %H:%M:%S"), gen_mode=gen_mode)
    env = {}
    run_start = time.time()
    for case in cases:
        result = _run_one(case, client, env)
        report.results.append(result)
        report.total += 1
        if result.passed:
            report.passed += 1
        elif result.skip_reason:
            report.skipped += 1
        else:
            report.failed += 1
    report.duration = round(time.time() - run_start, 2)
    return report


def _run_one(case: Case, client: ApiClient, env: dict) -> CaseResult:
    result = CaseResult(case=case)
    if case.url.startswith("skip:"):
        result.skip_reason = case.url[len("skip:"):]
        return result

    headers = _resolve(case.headers, env)
    body = _resolve(case.body, env)
    # URL 里也可能有 @{oid} 这类变量引用，必须一起解析
    url = _resolve(case.url, env)

    start = time.time()
    try:
        resp = client.request(case.method, url, headers=headers, body=body)
    except Exception as e:
        result.passed = False
        result.errors = [f"请求异常: {e}"]
        result.elapsed = round(time.time() - start, 3)
        return result

    result.status_code = resp.status_code
    result.elapsed = round(time.time() - start, 3)
    result.response_text = resp.text[:2000]

    try:
        resp_json = resp.json()
    except ValueError:
        resp_json = None

    # 断言
    errs = []
    for rule in case.validate or []:
        _check_assertion(rule, resp, resp_json, errs)
    # 保存变量给后面的用例用
    for rule in case.save or []:
        _do_save(rule, resp, resp_json, body, env)

    result.passed = not errs
    result.errors = errs
    return result
