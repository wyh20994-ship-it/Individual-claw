from __future__ import annotations

from agent.tools.base import BaseTool
from agent.tools.bash_tool import BashTool
from agent.tools.file_tool import FileTool
from agent.tools.http_tool import HttpTool
from agent.tools.search_tool import SearchTool


def get_all_tools(config: dict, sandbox_client=None) -> list[BaseTool]:
    tools: list[BaseTool] = []

    if config.get("file", {}).get("enabled"):
        tools.append(FileTool(config["file"], sandbox_client=sandbox_client))
    if config.get("bash", {}).get("enabled"):
        tools.append(BashTool(config["bash"], sandbox_client=sandbox_client))
    if config.get("http", {}).get("enabled"):
        tools.append(HttpTool(config["http"]))
    if config.get("search", {}).get("enabled"):
        tools.append(SearchTool(config["search"]))

    return tools
