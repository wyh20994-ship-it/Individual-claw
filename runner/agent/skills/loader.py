"""
SkillLoader — 技能热重载系统
扫描 skills 目录下的 SKILL.md 文件，解析 triggers、description 等元信息
支持文件变更时自动重新加载
"""

from __future__ import annotations
import os
import re
import time
import threading
from pathlib import Path
from typing import Any

from utils.logger import logger

# SKILL.md 的 YAML frontmatter 正则
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class Skill:
    """解析后的技能对象"""

    def __init__(self, name: str, version: str, description: str, triggers: list[str], content: str, path: Path):
        self.name = name
        self.version = version
        self.description = description
        self.triggers = triggers      # 触发词 / 命令列表
        self.content = content        # SKILL.md 的完整内容（指令逻辑）
        self.path = path
        self.loaded_at = time.time()


class SkillLoader:
    def __init__(self, config: dict):
        skill_cfg = config.get("runner", {}).get("skills", {})
        self.directory = Path(skill_cfg.get("directory", "./runner/agent/skills"))
        self.scan_interval = skill_cfg.get("scan_interval", 10)
        self.auto_reload = skill_cfg.get("auto_reload", True)
        self.skills: dict[str, Skill] = {}
        self._mtimes: dict[str, float] = {}
        self._watcher_thread: threading.Thread | None = None

        # 首次加载
        self._scan()

    def _scan(self):
        """扫描所有 SKILL.md 文件"""
        if not self.directory.exists():
            return
        for skill_md in self.directory.rglob("SKILL.md"):
            self._load_skill(skill_md)

    def _load_skill(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8")
            mtime = path.stat().st_mtime
            str_path = str(path)

            # 跳过未变更的
            if str_path in self._mtimes and self._mtimes[str_path] == mtime:
                return

            self._mtimes[str_path] = mtime

            meta = self._parse_frontmatter(content)
            name = meta.get("name", path.parent.name)
            skill = Skill(
                name=name,
                version=meta.get("version", "0.1.0"),
                description=meta.get("description", ""),
                triggers=meta.get("triggers", []),
                content=content,
                path=path,
            )
            self.skills[name] = skill
            logger.info(f"[SkillLoader] Loaded skill: {name} v{skill.version}")

        except Exception as e:
            logger.error(f"[SkillLoader] Failed to load {path}: {e}")

    @staticmethod
    def _parse_frontmatter(text: str) -> dict:
        """简单解析 SKILL.md 的 YAML frontmatter"""
        match = FRONTMATTER_RE.match(text)
        if not match:
            return {}
        import yaml
        try:
            return yaml.safe_load(match.group(1)) or {}
        except Exception:
            return {}

    def match_skill(self, text: str) -> Skill | None:
        """根据用户输入匹配触发的技能"""
        for skill in self.skills.values():
            for trigger in skill.triggers:
                if trigger.startswith("/"):
                    # 命令触发: /xxx
                    if text.strip().startswith(trigger):
                        return skill
                else:
                    # 关键词触发
                    if trigger in text:
                        return skill
        return None

    def start_watching(self):
        """启动文件变更监控线程"""
        if not self.auto_reload:
            return

        def _watch():
            while True:
                time.sleep(self.scan_interval)
                self._scan()

        self._watcher_thread = threading.Thread(target=_watch, daemon=True)
        self._watcher_thread.start()
