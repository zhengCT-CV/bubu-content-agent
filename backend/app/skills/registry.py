from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.domain.errors import NotFoundError
from app.domain.models import SkillSnapshot

ALIASES = {
    "topic_strategy": "topic-strategy",
    "storyboard_design": "storyboard-design",
    "content_review": "content-review",
    "visual_prompt": "visual-prompt",
    "performance_retro": "performance-retro",
}


@dataclass(frozen=True, slots=True)
class SkillPackage:
    name: str
    version: str
    instructions: str
    prompt: str
    rules: dict[str, Any]
    examples: list[dict[str, Any]]
    eval_path: Path
    prompt_hash: str

    @property
    def snapshot(self) -> SkillSnapshot:
        return SkillSnapshot(name=self.name, version=self.version, prompt_hash=self.prompt_hash)


class SkillRegistry:
    """按版本读取 Skill；checkpoint 记录版本后可重放同一包。"""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parent
        self._cache: dict[tuple[str, str], SkillPackage] = {}

    @staticmethod
    def normalize_name(name: str) -> str:
        return ALIASES.get(name, name.replace("_", "-"))

    def available(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for manifest_path in sorted(self.root.glob("*/manifest.yaml")):
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            result[manifest["name"]] = sorted(manifest["versions"], reverse=True)
        return result

    def load(self, name: str, version: str | None = None) -> SkillPackage:
        normalized = self.normalize_name(name)
        folder = self.root / normalized
        manifest_path = folder / "manifest.yaml"
        if not manifest_path.is_file():
            raise NotFoundError(f"Skill 不存在：{name}")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        selected = version or manifest["current_version"]
        if selected not in manifest["versions"]:
            raise NotFoundError(f"Skill {normalized} 不存在版本 {selected}")
        key = (normalized, selected)
        if key in self._cache:
            return self._cache[key]

        version_root = folder / "versions" / selected
        # 新版本可以携带自己的 SKILL.md。旧版本仍回退到根目录文件，
        # 因而新增版本不会改变历史版本的 Prompt 内容和 hash。
        version_instructions = version_root / "SKILL.md"
        instructions_path = version_instructions if version_instructions.is_file() else folder / "SKILL.md"
        instructions = instructions_path.read_text(encoding="utf-8")
        prompt = (version_root / "prompt.md").read_text(encoding="utf-8")
        rules = yaml.safe_load((version_root / "rules.yaml").read_text(encoding="utf-8"))
        examples = yaml.safe_load((version_root / "examples.yaml").read_text(encoding="utf-8"))
        digest = hashlib.sha256(
            f"{instructions}\n{prompt}\n{yaml.safe_dump(rules, allow_unicode=True, sort_keys=True)}".encode()
        ).hexdigest()
        package = SkillPackage(
            name=normalized,
            version=selected,
            instructions=instructions,
            prompt=prompt,
            rules=rules,
            examples=examples,
            eval_path=version_root / "evals" / "cases.jsonl",
            prompt_hash=digest,
        )
        self._cache[key] = package
        return package
