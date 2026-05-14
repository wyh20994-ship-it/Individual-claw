from __future__ import annotations

import re
import time
from pathlib import Path

from utils.logger import logger

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class Skill:
    def __init__(self, name: str, version: str, description: str, triggers: list[str], content: str, path: Path):
        self.name = name
        self.version = version
        self.description = description
        self.triggers = triggers
        self.content = content
        self.path = path
        self.loaded_at = time.time()

    def prompt_description(self) -> str:
        triggers = ", ".join(self.triggers) if self.triggers else "none"
        return f"Skill: {self.name}\nDescription: {self.description}\nTriggers: {triggers}"


class SkillLoader:
    def __init__(self, config: dict):
        skill_cfg = config.get("runner", {}).get("skills", {})
        self.directory = Path(skill_cfg.get("directory", "./runner/agent/skills"))
        self.auto_reload = bool(skill_cfg.get("auto_reload", False))
        self.skills: dict[str, Skill] = {}
        self._scan()

    def _scan(self):
        if not self.directory.exists():
            return
        for skill_md in self.directory.rglob("SKILL.md"):
            self._load_skill(skill_md)

    def _load_skill(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8")
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
        match = FRONTMATTER_RE.match(text)
        if not match:
            return {}
        import yaml

        try:
            return yaml.safe_load(match.group(1)) or {}
        except Exception:
            return {}

    def match_skill(self, text: str) -> Skill | None:
        for skill in self.skills.values():
            for trigger in skill.triggers:
                if trigger.startswith("/") and text.strip().startswith(trigger):
                    return skill
                if trigger and not trigger.startswith("/") and trigger in text:
                    return skill
        return None

    def start_watching(self):
        if self.auto_reload:
            logger.warning("[SkillLoader] auto_reload is disabled by architecture; skills load at startup only")
