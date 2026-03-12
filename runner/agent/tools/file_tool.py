"""
文件工具 — 沙箱内文件读写
安全约束：所有操作限制在 sandbox_path 内
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any

import aiofiles

from agent.tools.base import BaseTool, ToolParameter
from utils.logger import logger


class FileTool(BaseTool):
    name = "file_operation"
    description = "在沙箱目录内读取或写入文件。仅限 sandbox 路径下操作。"
    parameters = [
        ToolParameter(name="action", type="string", description="操作类型", enum=["read", "write", "list"]),
        ToolParameter(name="path", type="string", description="相对于沙箱的文件路径"),
        ToolParameter(name="content", type="string", description="写入内容（action=write 时必填）", required=False),
    ]

    def __init__(self, config: dict):
        self.sandbox = Path(config.get("sandbox_path", "./data/sandbox")).resolve()
        self.sandbox.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, rel: str) -> Path:
        """确保路径不逃逸出沙箱"""
        target = (self.sandbox / rel).resolve()
        if not str(target).startswith(str(self.sandbox)):
            raise PermissionError(f"路径越界: {rel}")
        return target

    async def execute(self, action: str = "read", path: str = ".", content: str = "", **kwargs: Any) -> str:
        try:
            target = self._safe_path(path)

            if action == "list":
                if not target.is_dir():
                    return f"错误: {path} 不是目录"
                items = [f.name + ("/" if f.is_dir() else "") for f in target.iterdir()]
                return "\n".join(items) if items else "(空目录)"

            elif action == "read":
                if not target.is_file():
                    return f"错误: 文件 {path} 不存在"
                async with aiofiles.open(target, "r", encoding="utf-8") as f:
                    return await f.read()

            elif action == "write":
                target.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(target, "w", encoding="utf-8") as f:
                    await f.write(content)
                return f"已写入 {path} ({len(content)} 字符)"

            else:
                return f"未知操作: {action}"

        except PermissionError as e:
            logger.warning(f"[FileTool] Security: {e}")
            return f"安全错误: {e}"
        except Exception as e:
            return f"文件操作失败: {e}"
