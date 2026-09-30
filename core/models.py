"""
数据模型：一个用例（Case）、一次执行的单个结果（CaseResult）、
一次完整执行的总报告（RunReport）。

字段尽量少而直白，够平台内部流转就行，不想整太重的 ORM。
"""
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Case:
    # name 用来做唯一标识，也能当报告里的展示名
    name: str
    method: str = "GET"
    url: str = ""
    headers: dict = field(default_factory=dict)
    # 请求体，字符串/字典都行，字符串会原样发出去
    body: Any = None
    # 断言列表，见 runner 里支持的几种断言
    validate: list = field(default_factory=list)
    # 执行后把响应/请求里的值存到全局 env，供后面的用例引用
    # 每一项形如 {key: str, from: str}，from 以 body. 开头取请求体，否则按响应 jsonpath 取
    save: list = field(default_factory=list)
    # 执行前要先把 $env 里的某些值套进 header/body 的引用关系
    # （在 loader 里就做掉了，这里只留个标记方便排查）
    source_file: str = ""


@dataclass
class CaseResult:
    case: Case
    passed: bool = False
    status_code: int = 0
    # 服务返回的原始文本（save_resp 开的时候会写进报告）
    response_text: str = ""
    # 失败原因，逐条断言结果拼出来的
    errors: list = field(default_factory=list)
    # 单个用例耗时
    elapsed: float = 0.0
    skip_reason: str = ""


@dataclass
class RunReport:
    started_at: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    results: list = field(default_factory=list)
    # 写报告时补的 ID，格式 reports/report_YYYYmmdd_HHMMSS
    report_id: str = ""
    gen_mode: str = "manual"  # manual / llm / mock

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.passed / self.total * 100, 2)
