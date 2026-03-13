"""
PC 远程控制服务 — 锁屏、截图、进程管理、文件浏览
⚠️ 仅在受信任环境下启用
"""

from __future__ import annotations
import asyncio
import base64
import os
import platform
from pathlib import Path
from typing import Any

from utils.logger import logger


class PCRemoteService:
    def __init__(self, config: dict):
        self.allowed_actions: list[str] = config.get("allowed_actions", [])

    def _check_action(self, action: str):
        if action not in self.allowed_actions:
            raise PermissionError(f"操作 '{action}' 未在白名单中")

    async def lock_screen(self) -> str:
        self._check_action("lock_screen")
        system = platform.system()
        if system == "Windows":
            os.system("rundll32.exe user32.dll,LockWorkStation")
        elif system == "Linux":
            os.system("loginctl lock-session")
        elif system == "Darwin":
            os.system("pmset displaysleepnow")
        return "屏幕已锁定"

    async def screenshot(self) -> dict[str, str]:
        """返回 base64 编码的截图"""
        self._check_action("screenshot")
        try:
            import mss
            with mss.mss() as sct:
                img = sct.grab(sct.monitors[1])
                from PIL import Image
                import io
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                return {"format": "png", "base64": b64}
        except ImportError:
            return {"error": "需要安装 mss 和 Pillow: pip install mss Pillow"}

    async def list_processes(self, top_n: int = 20) -> str:
        self._check_action("list_processes")
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                procs.append(p.info)
            procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
            lines = [f"{'PID':<8} {'CPU%':<8} {'MEM%':<8} NAME"]
            for p in procs[:top_n]:
                lines.append(f"{p['pid']:<8} {p.get('cpu_percent',0):<8.1f} {p.get('memory_percent',0):<8.1f} {p['name']}")
            return "\n".join(lines)
        except ImportError:
            return "需要安装 psutil: pip install psutil"

    async def file_browse(self, path: str = ".") -> str:
        self._check_action("file_browse")
        target = Path(path).resolve()
        # 安全检查：限制在用户目录下
        home = Path.home()
        if not str(target).startswith(str(home)):
            return f"安全拒绝: 仅允许浏览 {home} 下的文件"
        if not target.is_dir():
            return f"路径不是目录: {path}"
        items = []
        for f in sorted(target.iterdir()):
            prefix = "📁 " if f.is_dir() else "📄 "
            items.append(f"{prefix}{f.name}")
        return "\n".join(items) if items else "(空目录)"
