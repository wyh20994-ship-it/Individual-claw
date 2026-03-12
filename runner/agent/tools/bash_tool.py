"""
Bash 工具 — 受限的命令执行
安全约束：仅允许白名单内的命令前缀
"""

from __future__ import annotations
import asyncio
import shlex
from typing import Any

from agent.tools.base import BaseTool, ToolParameter
from utils.logger import logger


class BashTool(BaseTool):
    name = "bash_execute"
    description = "在服务器上执行受限的 Bash 命令（仅限白名单命令）。"
    parameters = [
        ToolParameter(name="command", type="string", description="要执行的 Bash 命令"),
    ]

    def __init__(self, config: dict):
        self.timeout = config.get("timeout", 30)
        self.whitelist: list[str] = config.get("whitelist", [])

    def _is_allowed(self, cmd: str) -> bool:
        """检查命令是否在白名单内"""
        if not self.whitelist:
            return False
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return False
        if not parts:
            return False
        binary = parts[0].split("/")[-1]  # 取基础命令名
        return binary in self.whitelist

    async def execute(self, command: str = "", **kwargs: Any) -> str:
        if not command.strip():
            return "错误: 命令为空"

        if not self._is_allowed(command):
            logger.warning(f"[BashTool] Blocked: {command}")
            return f"安全拒绝: 命令 '{command.split()[0]}' 不在白名单中。允许的命令: {', '.join(self.whitelist)}"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n[STDERR] " + stderr.decode("utf-8", errors="replace")
            # 截断过长输出
            if len(output) > 10000:
                output = output[:10000] + "\n... (输出被截断)"
            return output or "(无输出)"

        except asyncio.TimeoutError:
            return f"错误: 命令执行超时 ({self.timeout}s)"
        except Exception as e:
            return f"执行失败: {e}"
