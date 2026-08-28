from __future__ import annotations

import json

import pytest
from app.domain.models import (
    CharacterSpec,
    DialogueItem,
    Storyboard,
    StoryboardPanel,
    TimelineItem,
    VisualHandoffCard,
    VisualPromptPackage,
)
from app.domain.visual_rules import validate_storyboard_for_visual, validate_visual_prompts
from app.integrations.llm import DemoModelGateway
from app.skills.registry import SkillRegistry


def build_storyboard(dialogue: str = "你替我问一下？") -> Storyboard:
    cameras = ["close-up 特写", "medium 中景", "肩后镜头", "俯拍近景", "medium-wide", "道具特写"]
    panels = [
        StoryboardPanel(
            index=index,
            purpose="钩子" if index == 1 else "冲突升级" if index == 4 else "推进",
            scene="餐厅",
            action="一二看向服务员，布布轻轻抬手",
            emotion="紧张后安心",
            dialogue=dialogue if index == 1 else "",
            dialogue_items=(
                [DialogueItem(kind="speech", speaker="一二", exact_text=dialogue)]
                if index == 1
                else []
            ),
            camera=cameras[index - 1],
            time_of_day="evening",
            props=["menu", "water glass"],
        )
        for index in range(1, 7)
    ]
    return Storyboard(
        title="有人替你问服务员",
        summary="一件很小但具体的安全感。",
        interaction_question="你被什么小动作照顾过？",
        characters=[
            CharacterSpec(
                name="一二",
                identity="敏感的一二布布品牌角色",
                visual_anchor=(
                    "a small white panda-like bear with black ears and black eye patches, "
                    "sensitive, gloomy, expressive and slightly anxious vibe"
                ),
            ),
            CharacterSpec(
                name="布布",
                identity="温柔的一二布布品牌角色",
                visual_anchor="a small round brown bear, gentle, warm and slightly dazed vibe",
            ),
        ],
        cover_brief="布布替一二举手询问服务员，双角色居中。",
        panels=panels,
        ending="很小的动作，也能让人松一口气。",
        handoff_card=VisualHandoffCard(
            time_anchor="傍晚同一顿饭",
            environment_baseline="简化餐厅空间",
            fixed_props=["menu", "water glass"],
            time_object_strategy="不显示可读时间",
            timeline=[
                TimelineItem(panel_index=index, time_of_day="evening") for index in range(1, 7)
            ],
            emotional_peak_panel=4,
            narrative_mechanism="生活观察",
            cover_brief="布布替一二举手询问服务员，双角色居中。",
        ),
    )


async def build_prompts(storyboard: Storyboard) -> tuple[VisualPromptPackage, dict]:
    package = SkillRegistry().load("visual-prompt", "1.1.0")
    system_prompt = (
        package.instructions
        + "\n\n# 当前版本模型 Prompt\n"
        + package.prompt
        + "\n\n# 当前版本确定性规则\n"
        + json.dumps(package.rules, ensure_ascii=False)
    )
    output = await DemoModelGateway().generate_structured(
        VisualPromptPackage,
        system_prompt,
        {"storyboard": storyboard.model_dump()},
    )
    return output, package.rules


@pytest.mark.asyncio
async def test_v11_demo_prompt_passes_deterministic_visual_rules() -> None:
    storyboard = build_storyboard()
    prompts, rules = await build_prompts(storyboard)
    issues = validate_visual_prompts(storyboard, prompts, rules)
    assert not [issue for issue in issues if issue.severity == "blocking"]


@pytest.mark.asyncio
async def test_exact_chinese_punctuation_mismatch_is_blocking() -> None:
    storyboard = build_storyboard()
    prompts, rules = await build_prompts(storyboard)
    first = prompts.panels[0].model_copy(
        update={"prompt_en": prompts.panels[0].prompt_en.replace("你替我问一下？", "你替我问一下")}
    )
    broken = prompts.model_copy(update={"panels": [first, *prompts.panels[1:]]})
    issues = validate_visual_prompts(storyboard, broken, rules)
    assert any(issue.code == "dialogue-mismatch" and issue.severity == "blocking" for issue in issues)


@pytest.mark.asyncio
async def test_dialogue_over_twelve_characters_is_warning_only() -> None:
    storyboard = build_storyboard("你可以帮我问一下服务员还有没有位置吗？")
    prompts, rules = await build_prompts(storyboard)
    issues = validate_visual_prompts(storyboard, prompts, rules)
    assert any(issue.code == "dialogue-too-long" and issue.severity == "warning" for issue in issues)
    assert not [issue for issue in issues if issue.severity == "blocking"]


def test_humanized_bubu_is_blocked_before_visual_generation() -> None:
    storyboard = build_storyboard()
    characters = list(storyboard.characters)
    characters[1] = characters[1].model_copy(
        update={"visual_anchor": "a young human with short hair and round glasses"}
    )
    issues = validate_storyboard_for_visual(storyboard.model_copy(update={"characters": characters}))
    assert any(issue.code == "brand-character-broken" for issue in issues)


def test_legacy_artifacts_keep_schema_compatibility() -> None:
    storyboard = build_storyboard().model_dump()
    storyboard.pop("handoff_card")
    storyboard.pop("panel_aspect_ratio")
    for panel in storyboard["panels"]:
        panel.pop("dialogue_items")
    restored = Storyboard.model_validate(storyboard)
    assert restored.handoff_card is None

    legacy_prompts = VisualPromptPackage.model_validate(
        {
            "style_prefix": "legacy",
            "character_bible": "legacy",
            "cover_prompt_en": "legacy cover",
            "cover_negative_prompt_en": "legacy negative",
            "panels": [
                {
                    "panel_index": index,
                    "prompt_en": "legacy panel",
                    "negative_prompt_en": "legacy negative",
                    "continuity_notes": "legacy continuity",
                }
                for index in range(1, 7)
            ],
        }
    )
    assert legacy_prompts.reference_reminders == []


def test_package_allows_more_than_two_background_objects_across_article() -> None:
    prompts = VisualPromptPackage(
        style_prefix="style",
        character_bible="characters",
        allowed_background_objects=["沙发", "茶几", "餐桌"],
        cover_prompt_en="cover",
        cover_negative_prompt_en="negative",
        panels=[],
    )
    assert prompts.allowed_background_objects == ["沙发", "茶几", "餐桌"]
