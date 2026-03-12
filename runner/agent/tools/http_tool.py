"""
HTTP 工具 — 发送网络请求
"""

from __future__ import annotations
from typing import Any

import httpx

from agent.tools.base import BaseTool, ToolParameter
from utils.logger import logger


class HttpTool(BaseTool):
    name = "http_request"
    description = "发送 HTTP 请求并返回响应。支持 GET/POST。"
    parameters = [
        ToolParameter(name="url", type="string", description="请求 URL"),
        ToolParameter(name="method", type="string", description="HTTP 方法", enum=["GET", "POST"]),
        ToolParameter(name="body", type="string", description="POST 请求体 (JSON 字符串)", required=False),
        ToolParameter(name="headers", type="string", description="自定义 Headers (JSON 字符串)", required=False),
    ]

    def __init__(self, config: dict):
        self.timeout = config.get("timeout", 15)

    async def execute(self, url: str = "", method: str = "GET", body: str = "", headers: str = "", **kwargs: Any) -> str:
        import json

        if not url:
            return "错误: URL 为空"

        # 基础 SSRF 防护：禁止访问内网地址
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0") or hostname.startswith("192.168.") or hostname.startswith("10.") or hostname.startswith("172."):
            return "安全拒绝: 不允许访问内网地址"

        try:
            req_headers = json.loads(headers) if headers else {}
            req_body = json.loads(body) if body else None
        except json.JSONDecodeError as e:
            return f"参数解析失败: {e}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                if method.upper() == "POST":
                    resp = await client.post(url, json=req_body, headers=req_headers)
                else:
                    resp = await client.get(url, headers=req_headers)

                text = resp.text
                if len(text) > 10000:
                    text = text[:10000] + "\n... (响应被截断)"
                return f"[{resp.status_code}]\n{text}"

        except httpx.TimeoutException:
            return f"请求超时 ({self.timeout}s)"
        except Exception as e:
            return f"请求失败: {e}"
