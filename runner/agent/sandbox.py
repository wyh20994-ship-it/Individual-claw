from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from agent.schemas import SandboxCommand, SandboxResult
from utils.logger import logger


class SandboxClient:
    def __init__(self, config: dict):
        remote_cfg = config.get("remote", {})
        self.enabled = bool(remote_cfg.get("enabled", False))
        self.provider = remote_cfg.get("provider", "open_source_sdk")
        self.endpoint = str(remote_cfg.get("endpoint", "http://127.0.0.1:8080")).rstrip("/")
        self.sync_skills_on_start = bool(remote_cfg.get("sync_skills_on_start", False))
        self.timeout = int(remote_cfg.get("timeout", 30))

    async def execute(self, action: str, payload: dict[str, Any]) -> SandboxResult:
        command = SandboxCommand(action=action, payload=payload)
        if not self.enabled:
            return SandboxResult(ok=False, error="remote sandbox is disabled")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.endpoint}/execute", json=command.model_dump())
                resp.raise_for_status()
                return SandboxResult.model_validate(resp.json())
        except Exception as e:
            logger.warning(f"[Sandbox] Remote execute failed: {e}")
            return SandboxResult(ok=False, error=str(e))

    async def sync_skills(self, skills_dir: Path):
        if not self.enabled or not self.sync_skills_on_start or not skills_dir.exists():
            return

        files: list[dict[str, str]] = []
        for path in skills_dir.rglob("*"):
            if path.is_file():
                files.append(
                    {
                        "path": str(path.relative_to(skills_dir)).replace("\\", "/"),
                        "content": path.read_text(encoding="utf-8", errors="replace"),
                    }
                )

        result = await self.execute("sync_skills", {"files": files})
        if result.ok:
            logger.info(f"[Sandbox] Synced {len(files)} skill file(s)")
        else:
            logger.warning(f"[Sandbox] Skill sync failed: {result.error}")
