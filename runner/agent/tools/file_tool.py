from __future__ import annotations

from pathlib import Path
from typing import Any

import aiofiles

from agent.tools.base import BaseTool, ToolParameter
from utils.logger import logger


class FileTool(BaseTool):
    name = "file_operation"
    description = "Read, write, or list files in the configured sandbox."
    parameters = [
        ToolParameter(name="action", type="string", description="File action", enum=["read", "write", "list"]),
        ToolParameter(name="path", type="string", description="Relative path inside sandbox"),
        ToolParameter(name="content", type="string", description="Content for write action", required=False),
    ]

    def __init__(self, config: dict, sandbox_client=None):
        self.sandbox_client = sandbox_client
        self.sandbox = Path(config.get("sandbox_path", "./runner/data/sandbox")).resolve()
        if not (self.sandbox_client and self.sandbox_client.enabled):
            self.sandbox.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, rel: str) -> Path:
        target = (self.sandbox / rel).resolve()
        if not str(target).startswith(str(self.sandbox)):
            raise PermissionError(f"path escapes sandbox: {rel}")
        return target

    async def execute(self, action: str = "read", path: str = ".", content: str = "", **kwargs: Any) -> str:
        if self.sandbox_client and self.sandbox_client.enabled:
            result = await self.sandbox_client.execute(
                "file",
                {"action": action, "path": path, "content": content},
            )
            return result.output if result.ok else f"Remote sandbox error: {result.error}"

        try:
            target = self._safe_path(path)
            if action == "list":
                if not target.is_dir():
                    return f"Error: {path} is not a directory"
                items = [f.name + ("/" if f.is_dir() else "") for f in target.iterdir()]
                return "\n".join(items) if items else "(empty)"

            if action == "read":
                if not target.is_file():
                    return f"Error: file not found: {path}"
                async with aiofiles.open(target, "r", encoding="utf-8") as f:
                    return await f.read()

            if action == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(target, "w", encoding="utf-8") as f:
                    await f.write(content)
                return f"Written: {path} ({len(content)} chars)"

            return f"Unknown action: {action}"
        except PermissionError as e:
            logger.warning(f"[FileTool] Security: {e}")
            return f"Security error: {e}"
        except Exception as e:
            return f"File operation error: {e}"
