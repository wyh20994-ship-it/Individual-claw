from __future__ import annotations

import asyncio
import shlex
from typing import Any

from agent.tools.base import BaseTool, ToolParameter
from utils.logger import logger


class BashTool(BaseTool):
    name = "bash_execute"
    description = "Execute a shell command in the configured sandbox."
    parameters = [
        ToolParameter(name="command", type="string", description="Shell command to execute"),
    ]

    def __init__(self, config: dict, sandbox_client=None):
        self.timeout = int(config.get("timeout", 30))
        self.whitelist: list[str] = config.get("whitelist", [])
        self.sandbox_client = sandbox_client

    def _is_allowed(self, cmd: str) -> bool:
        if not self.whitelist:
            return False
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return False
        if not parts:
            return False
        binary = parts[0].split("/")[-1]
        return binary in self.whitelist

    async def execute(self, command: str = "", **kwargs: Any) -> str:
        if not command.strip():
            return "Error: command is empty"

        if self.sandbox_client and self.sandbox_client.enabled:
            result = await self.sandbox_client.execute("bash", {"command": command, "timeout": self.timeout})
            return result.output if result.ok else f"Remote sandbox error: {result.error}"

        if not self._is_allowed(command):
            logger.warning(f"[BashTool] Blocked: {command}")
            return f"Blocked: command '{command.split()[0]}' is not in whitelist: {', '.join(self.whitelist)}"

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
            if len(output) > 10000:
                output = output[:10000] + "\n... (truncated)"
            return output or "(no output)"
        except asyncio.TimeoutError:
            return f"Error: command timed out ({self.timeout}s)"
        except Exception as e:
            return f"Error: {e}"
