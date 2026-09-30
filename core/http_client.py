"""
HTTP 客户端封装，主要做几件事：
1. 统一从 config 拼 base_url
2. 给请求加超时、简单重试
3. 提供 login() 拿到 token，方便用例走"先登录再调业务接口"这种流程
"""
import time

import requests

from .utils import load_config


class ApiClient:
    def __init__(self, base_url: str = ""):
        cfg = load_config()
        if not base_url:
            srv = cfg.get("server", {})
            base_url = f"http://{srv.get('host','127.0.0.1')}:{srv.get('port',8001)}"
        self.base_url = base_url.rstrip("/")
        test_cfg = cfg.get("test", {})
        self.timeout = test_cfg.get("timeout", 15)
        self.retry = test_cfg.get("retry", 0)
        self._token = None
        self.session = requests.Session()

    # ---- token 相关 ----
    def login(self, username: str = "demo", password: str = "demo1234") -> str:
        """登录拿 token，存在内存里，后续请求自动带上。"""
        resp = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"登录失败: {data.get('message')}")
        self._token = data["data"]["token"]
        return self._token

    def set_token(self, token: str):
        self._token = token

    # ---- 核心请求 ----
    def request(self, method: str, url: str, headers: dict = None, body=None):
        method = method.upper()
        full_url = url if url.startswith("http") else f"{self.base_url}{url}"
        h = dict(headers or {})
        if self._token:
            h.setdefault("Authorization", f"Bearer {self._token}")

        last_err = None
        for attempt in range(self.retry + 1):
            try:
                resp = self.session.request(
                    method, full_url, headers=h, json=body,
                    timeout=self.timeout,
                )
                return resp
            except requests.RequestException as e:
                last_err = e
                if attempt < self.retry:
                    time.sleep(0.5 * (attempt + 1))
        # 网络层都失败了，抛出去由 runner 记成失败用例
        raise last_err

    def close(self):
        self.session.close()
