from __future__ import annotations

import json

from app.skills.registry import SkillRegistry


def test_all_versioned_skills_are_loadable() -> None:
    registry = SkillRegistry()
    available = registry.available()
    assert set(available) == {
        "topic-strategy",
        "storyboard-design",
        "content-review",
        "visual-prompt",
        "performance-retro",
    }
    for name in available:
        package = registry.load(name, "1.0.0")
        assert package.prompt_hash
        assert package.version == "1.0.0"
        assert package.eval_path.is_file()
        for line in package.eval_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert json.loads(line)["id"]


def test_underscore_alias_keeps_business_name_compatible() -> None:
    assert SkillRegistry().load("topic_strategy").name == "topic-strategy"


def test_v11_uses_version_specific_instructions_without_changing_v10() -> None:
    registry = SkillRegistry()
    legacy = registry.load("visual-prompt", "1.0.0")
    current = registry.load("visual-prompt")
    assert legacy.version == "1.0.0"
    assert "对白不是让模型绘制可读文字" in legacy.instructions
    assert current.version == "1.1.0"
    assert "正文对白直接绘制" in current.instructions
    assert legacy.prompt_hash != current.prompt_hash
