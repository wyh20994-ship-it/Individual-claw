"""
工具系统入口 — 注册并返回所有已启用的工具实例
"""

from __future__ import annotations
from typing import Any

from agent.tools.base import BaseTool
from agent.tools.file_tool import FileTool
from agent.tools.bash_tool import BashTool
from agent.tools.http_tool import HttpTool
from agent.tools.search_tool import SearchTool


def get_all_tools(config: dict) -> list[BaseTool]:
    """根据配置返回已启用的工具列表"""
    tools: list[BaseTool] = []

    if config.get("file", {}).get("enabled"):
        tools.append(FileTool(config["file"]))
    if config.get("bash", {}).get("enabled"):
        tools.append(BashTool(config["bash"]))
    if config.get("http", {}).get("enabled"):
        tools.append(HttpTool(config["http"]))
    if config.get("search", {}).get("enabled"):
        tools.append(SearchTool(config["search"]))

    return tools
