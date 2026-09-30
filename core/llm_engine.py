"""
AI 引擎：用大模型自动生成测试用例 + 对失败用例做 Badcase 分析。

亮点在"降级"：没有配 API Key 时自动切到模板生成器（MockGenerator），
从被测服务的 openapi.json 里扫接口、拼一套模板用例出来，
这样即使不开 AI 也能把整条链路演示跑通。

接的是 OpenAI 兼容接口，火山方舟（豆包）也用它这套协议：
  base_url + /chat/completions，header 带 Authorization: Bearer <key>
"""
import json
import os
from pathlib import Path

import requests

from .utils import load_config

# AI 生成出来的用例会落到这个目录，方便 Web 端直接看到/改
AI_CASES_DIR = Path(__file__).resolve().parent.parent / "cases" / "_ai_generated"


def _load_dotenv():
    """读项目根目录的 .env，把还没设置的环境变量补上。

    手写的极简加载器，不引 python-dotenv 那套。key 放在 .env 里（已被 gitignore），
    避免明文 key 进仓库。
    """
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


class LLMClient:
    def __init__(self, cfg: dict):
        _load_dotenv()
        llm_cfg = cfg.get("llm", {})
        self.base_url = llm_cfg.get("base_url", "").rstrip("/")
        self.model = llm_cfg.get("model", "glm-4-flash")
        self.api_key = os.getenv(llm_cfg.get("api_key_env", "ZHIPU_API_KEY"), "").strip()
        # 生成用例要读整个 openapi、模型响应也慢，给足时间（有的平台偶尔卡一下）
        self.timeout = 180

    def available(self) -> bool:
        return bool(self.base_url and self.api_key)

    def chat(self, messages: list) -> str:
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "temperature": 0.3},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    # ---- 生成用例 ----
    def generate_test_cases(self, openapi_spec: dict) -> list[dict]:
        # 只挑出业务接口，把健康检查这类过滤掉，省 token
        paths = []
        for p, methods in openapi_spec.get("paths", {}).items():
            if "/api/health" in p:
                continue
            for m, meta in methods.items():
                if m in ("get", "post", "put", "delete"):
                    paths.append(
                        f"{m.upper()} {p} —— {meta.get('summary','')}"
                    )
        # 只挑出业务接口，把健康检查这类过滤掉；最多给 40 个，避免提示词太长拖慢模型
        spec_short = "\n".join(paths[:40])

        # 给一个精确的 YAML 示例，让模型照着结构输出，减少格式漂移
        example = (
            "- name: 登录-正常\n"
            "  method: POST\n"
            "  url: /api/auth/login\n"
            "  body:\n"
            "    username: demo\n"
            "    password: demo1234\n"
            "  validate:\n"
            "    - type: status_code\n"
            "      value: 200\n"
            "    - type: jsonpath\n"
            "      path: \"$.code\"\n"
            "      value: 0\n"
        )
        prompt = (
            "你是资深测试工程师。根据下面的接口清单，为每个接口生成覆盖"
            "正常+异常场景的测试用例，严格按下面的 YAML 结构输出。\n"
            "要求：\n"
            "1. 只输出 YAML 列表，不要任何解释，不要用 ``` 包裹；\n"
            "2. 每个用例包含 name / method / url / body(可省略) / validate；\n"
            "3. validate 是对象列表，每个对象是 {type, ...}，type 只允许 status_code 或 jsonpath，"
            "jsonpath 断言业务码 code 是否等于 0；\n"
            "4. 异常场景的用例 validate 里也要给出明确的期望值。\n"
            "YAML 示例：\n" + example + "\n接口清单：\n" + spec_short
        )
        content = self.chat(
            [
                {"role": "system", "content": "你只输出符合要求的 YAML，不做任何解释。"},
                {"role": "user", "content": prompt},
            ]
        )
        # 大模型偶尔会包一层 ```yaml，剥掉
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        import yaml

        data = yaml.safe_load(content)
        if not isinstance(data, list):
            raise ValueError("模型返回的不是用例列表")
        return data

    # ---- Badcase 分析 ----
    def analyze_badcases(self, failures: list[dict]) -> str:
        if not failures:
            return "本次没有失败用例，无需分析。"
        brief = "\n".join(
            f"- {f['name']}: {'; '.join(f['errors'][:2])}" for f in failures[:10]
        )
        prompt = (
            "下面是一次自动化测试的失败用例，请逐条给出可能的原因和修复建议，"
            "按问题归类（服务端缺陷/测试用例缺陷/数据问题），简洁点。\n" + brief
        )
        return self.chat(
            [
                {"role": "user", "content": prompt},
            ]
        )


class MockGenerator:
    """没配 AI Key 时的兜底：按 openapi 扫接口生成模板用例，保证演示能跑。"""

    def available(self) -> bool:
        return True

    def generate_test_cases(self, openapi_spec: dict) -> list[dict]:
        cases = []
        for p, methods in openapi_spec.get("paths", {}).items():
            if "/api/health" in p:
                continue
            for m, meta in methods.items():
                if m not in ("get", "post", "put", "delete"):
                    continue
                # 模板用例：至少校验状态码 200，能解析的就再校验 code=0
                base = {
                    "name": f"{m.upper()} {p} - 模板生成",
                    "method": m.upper(),
                    "url": p,
                    "validate": [{"type": "status_code", "value": 200}],
                }
                if meta.get("requestBody"):
                    base["validate"].append({"type": "jsonpath", "path": "$.code", "value": 0})
                cases.append(base)
        return cases

    def analyze_badcases(self, failures: list[dict]) -> str:
        """没接大模型时，用本地规则做个粗粒度归因，总比报错强。"""
        if not failures:
            return "本次没有失败用例，无需分析。"
        lines = ["【本地规则分析】（未配置 AI Key，按状态码粗粒度归因）"]
        buckets = {}
        for f in failures:
            key = "状态码异常"
            for e in f["errors"]:
                if "状态码" in e:
                    key = f"状态码 {e.split('实际')[-1].strip()}"
                    break
            buckets.setdefault(key, []).append(f["name"])
        for k, names in buckets.items():
            lines.append(f"- {k}：{len(names)} 条，涉及 {', '.join(names[:6])}")
        lines.append("提示：配置环境变量 ZHIPU_API_KEY（或 .env）后，可改为大模型逐条归因。")
        return "\n".join(lines)


def get_engine(cfg: dict = None):
    """返回可用的引擎，优先真实 LLM，没有 key 就用模板生成器。"""
    cfg = cfg or load_config()
    if cfg.get("llm", {}).get("enabled", True):
        llm = LLMClient(cfg)
        if llm.available():
            return llm
    return MockGenerator()
