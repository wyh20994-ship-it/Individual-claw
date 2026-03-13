"""
搜索工具 — 基于 Tavily API 的网络搜索
"""

from __future__ import annotations
import os
from typing import Any

import httpx

from agent.tools.base import BaseTool, ToolParameter
from utils.logger import logger


class SearchTool(BaseTool):
    name = "web_search"
    description = "使用 Tavily API 搜索互联网信息，返回摘要结果。"
    parameters = [
        ToolParameter(name="query", type="string", description="搜索关键词"),
        ToolParameter(name="max_results", type="string", description="最大结果数（默认 5）", required=False),
    ]

    def __init__(self, config: dict):
        self.api_key = os.getenv("TAVILY_API_KEY", "")
        self.base_url = "https://api.tavily.com"

    async def execute(self, query: str = "", max_results: str = "5", **kwargs: Any) -> str:
        if not query:
            return "错误: 搜索关键词为空"
        if not self.api_key:
            return "错误: TAVILY_API_KEY 未配置"

        try:
            count = min(int(max_results), 10)
        except ValueError:
            count = 5

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": count,
                        "search_depth": "basic",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            if not results:
                return "未找到相关结果"

            lines = []
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **{r.get('title', '')}**\n   {r.get('content', '')}\n   URL: {r.get('url', '')}")
            return "\n\n".join(lines)

        except Exception as e:
            return f"搜索失败: {e}"
