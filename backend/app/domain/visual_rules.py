from __future__ import annotations

from collections import Counter
from typing import Any

from app.domain.models import (
    ReviewIssue,
    ReviewResult,
    Storyboard,
    TimelineItem,
    VisualHandoffCard,
    VisualPromptPackage,
)

BRAND_NAMES = {
    "一二": "Yier",
    "yier": "Yier",
    "布布": "Bubu",
    "bubu": "Bubu",
}


def _brand_name(value: str) -> str | None:
    return BRAND_NAMES.get(value.strip().lower()) or BRAND_NAMES.get(value.strip())


def _issue(
    code: str,
    severity: str,
    message: str,
    suggestion: str,
) -> ReviewIssue:
    return ReviewIssue(
        code=code,
        severity=severity,
        message=message,
        suggestion=suggestion,
        source="deterministic",
    )


def _default_peak(storyboard: Storyboard) -> int:
    candidates = [
        panel.index
        for panel in storyboard.panels
        if any(word in panel.purpose for word in ("高潮", "升级", "转折", "冲突"))
    ]
    return candidates[-1] if candidates else storyboard.panels[max(0, len(storyboard.panels) // 2)].index


def normalize_storyboard_handoff(
    storyboard: Storyboard,
    narrative_mechanism: str = "",
) -> Storyboard:
    """补全旧 checkpoint 可安全推导的交接字段，并明确记录推断来源。"""

    original = storyboard.handoff_card
    handoff = original.model_copy(deep=True) if original else VisualHandoffCard()
    notes = list(handoff.inferred_notes)

    def inferred(message: str) -> None:
        if message not in notes:
            notes.append(message)

    if not handoff.time_anchor:
        handoff.time_anchor = storyboard.panels[0].time_of_day
        inferred("【推断，请核对】时间锚点取自第 1 格")
    if not handoff.environment_baseline:
        handoff.environment_baseline = storyboard.panels[0].scene
        inferred("【推断，请核对】环境基准取自第 1 格场景")
    if not handoff.fixed_props:
        counts = Counter(prop for panel in storyboard.panels for prop in panel.props)
        repeated = [prop for prop, count in counts.items() if count >= 2]
        handoff.fixed_props = repeated or list(counts)
        inferred("【推断，请核对】固定道具由逐格 props 汇总")
    if not handoff.timeline:
        handoff.timeline = [
            TimelineItem(panel_index=panel.index, time_of_day=panel.time_of_day)
            for panel in storyboard.panels
        ]
        inferred("【推断，请核对】逐格时间轴由 panels.time_of_day 生成")
    if handoff.emotional_peak_panel is None:
        handoff.emotional_peak_panel = _default_peak(storyboard)
        inferred("【推断，请核对】情绪最高点根据叙事目的推断")
    if not handoff.narrative_mechanism:
        handoff.narrative_mechanism = narrative_mechanism
        if narrative_mechanism:
            inferred("【推断，请核对】叙事机制取自已批准选题")
    if not handoff.cover_brief:
        handoff.cover_brief = storyboard.cover_brief
        inferred("【推断，请核对】封面简报取自 storyboard.cover_brief")
    handoff.inferred_notes = notes
    return storyboard.model_copy(update={"handoff_card": handoff})


def validate_storyboard_for_visual(storyboard: Storyboard) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    found_brand = False
    for character in storyboard.characters:
        brand = _brand_name(character.name)
        if not brand:
            continue
        found_brand = True
        anchor = character.visual_anchor.lower()
        human_visual = any(word in anchor for word in ("human", "short hair", "glasses", "人类", "短发"))
        if brand == "Yier":
            valid = ("panda-like bear" in anchor and "black ears" in anchor) or (
                "熊猫" in anchor and "黑耳" in anchor
            )
        else:
            valid = "round brown bear" in anchor or ("圆" in anchor and "棕熊" in anchor)
        if not valid or human_visual:
            issues.append(
                _issue(
                    "brand-character-broken",
                    "blocking",
                    f"角色 {character.name} 没有使用固定的 {brand} 品牌动物形象。",
                    "恢复 v5.3 固定外形；职业身份只能作为剧情身份，不能替换动物视觉锚点。",
                )
            )
    if not found_brand:
        issues.append(
            _issue(
                "brand-character-broken",
                "blocking",
                "分镜没有声明一二或布布品牌角色。",
                "至少加入一二或布布，并使用固定动物视觉锚点。",
            )
        )

    handoff = storyboard.handoff_card
    if handoff is None:
        issues.append(
            _issue(
                "handoff-missing",
                "blocking",
                "缺少分镜交接卡。",
                "补齐 handoff_card 后再生成绘图 Prompt。",
            )
        )
    else:
        required = {
            "time_anchor": handoff.time_anchor,
            "environment_baseline": handoff.environment_baseline,
            "time_object_strategy": handoff.time_object_strategy,
            "narrative_mechanism": handoff.narrative_mechanism,
            "cover_brief": handoff.cover_brief,
        }
        for field, value in required.items():
            if not value:
                issues.append(
                    _issue(
                        "handoff-missing",
                        "blocking",
                        f"交接卡缺少 {field}。",
                        f"在分镜审批页补充 {field}。",
                    )
                )
        timeline = {item.panel_index: item for item in handoff.timeline}
        if set(timeline) != {panel.index for panel in storyboard.panels}:
            issues.append(
                _issue(
                    "timeline-conflict",
                    "blocking",
                    "交接卡时间轴没有与全部分镜一一对应。",
                    "为每格保留且只保留一个相同 panel_index 的时间条目。",
                )
            )
        else:
            for panel in storyboard.panels:
                if timeline[panel.index].time_of_day != panel.time_of_day:
                    issues.append(
                        _issue(
                            "timeline-conflict",
                            "blocking",
                            f"第 {panel.index} 格的时间与交接卡冲突。",
                            "统一 panel.time_of_day 与 handoff_card.timeline。",
                        )
                    )
        for conflict in handoff.conflicts:
            issues.append(_issue("handoff-conflict", "blocking", conflict, "先在分镜审批页消解冲突。"))

    for panel in storyboard.panels:
        if panel.dialogue and not panel.dialogue_items:
            issues.append(
                _issue(
                    "dialogue-structure-missing",
                    "blocking",
                    f"第 {panel.index} 格有对白但缺少结构化 dialogue_items。",
                    "为每句文字填写类型、说话人和精确原文。",
                )
            )
        for item in panel.dialogue_items:
            if item.exact_text not in panel.dialogue:
                issues.append(
                    _issue(
                        "dialogue-mismatch",
                        "blocking",
                        f"第 {panel.index} 格 legacy dialogue 没有逐字包含“{item.exact_text}”。",
                        "同步 legacy dialogue 与 dialogue_items，保留全部标点。",
                    )
                )
            if len(item.exact_text) > 12:
                issues.append(
                    _issue(
                        "dialogue-too-long",
                        "warning",
                        f"第 {panel.index} 格“{item.exact_text}”超过 12 个字符。",
                        "建议拆成短气泡；如剧情必须保留，可由人工批准。",
                    )
                )

    for previous, current in zip(storyboard.panels, storyboard.panels[1:], strict=False):
        if previous.camera.strip().casefold() == current.camera.strip().casefold():
            issues.append(
                _issue(
                    "camera-repeated",
                    "blocking",
                    f"第 {previous.index}、{current.index} 格使用完全相同机位。",
                    "调整其中一格的景别、角度或道具视点。",
                )
            )
    if len(storyboard.panels) >= 6:
        cameras = " ".join(panel.camera.lower() for panel in storyboard.panels)
        checks = {
            "close-up": any(word in cameras for word in ("close-up", "close up", "特写", "近景")),
            "medium": any(word in cameras for word in ("medium", "中景")),
            "alternate": any(word in cameras for word in ("俯", "仰", "肩后", "道具", "over", "top", "low")),
        }
        missing = [name for name, present in checks.items() if not present]
        if missing:
            issues.append(
                _issue(
                    "camera-variety-missing",
                    "blocking",
                    f"6 格以上分镜缺少镜头类型：{', '.join(missing)}。",
                    "至少包含特写、中景/中远景和明显不同角度或道具特写。",
                )
            )
    return issues


def validate_visual_prompts(
    storyboard: Storyboard,
    prompts: VisualPromptPackage,
    rules: dict[str, Any],
) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    style = str(rules["style_prefix"])
    full_bleed = str(rules["full_bleed_clause"])
    time_clause = str(rules["default_time_clause"])
    background_clause = str(rules["background"]["clause"])
    bubble_clause = str(rules["dialogue"]["speech_bubble"])
    crop_clause = str(rules["cover"]["crop_clause"])
    no_text_clause = str(rules["cover"]["no_text_clause"])
    expected_indices = [panel.index for panel in storyboard.panels]
    actual_indices = [panel.panel_index for panel in prompts.panels]
    if actual_indices != expected_indices:
        issues.append(
            _issue(
                "panel-mapping-invalid",
                "blocking",
                "绘图 Prompt 没有与分镜逐格一一对应。",
                "保持相同格数和连续 panel_index。",
            )
        )
    if prompts.style_prefix != style:
        issues.append(
            _issue(
                "visual-rule-missing",
                "blocking",
                "画风基准不是 v5.3 固定全文。",
                "原样使用 rules.style_prefix。",
            )
        )
    expected_references = list(rules["reference_priority"])
    if prompts.reference_reminders != expected_references:
        issues.append(
            _issue(
                "reference-priority-invalid",
                "blocking",
                "参考图提醒或优先级不正确。",
                "使用：角色定妆表 > 分镜交接卡 > 画风参考图 > 首格 > 上一格。",
            )
        )

    storyboard_by_index = {panel.index: panel for panel in storyboard.panels}
    brand_anchors = dict(rules["brand_characters"])
    present_brands = {
        brand
        for character in storyboard.characters
        if (brand := _brand_name(character.name)) is not None
    }
    for panel_prompt in prompts.panels:
        source = storyboard_by_index.get(panel_prompt.panel_index)
        if source is None:
            continue
        prompt = panel_prompt.prompt_en
        missing_clauses = [
            label
            for label, clause in (
                ("满幅规则", full_bleed),
                ("时间规则", time_clause),
                ("背景减法", background_clause),
                ("主体占比", panel_prompt.subject_ratio),
            )
            if clause not in prompt
        ]
        if not prompt.startswith(style):
            missing_clauses.insert(0, "开头的固定画风")
        if missing_clauses:
            issues.append(
                _issue(
                    "visual-rule-missing",
                    "blocking",
                    f"第 {source.index} 格缺少：{', '.join(missing_clauses)}。",
                    "按 v5.3 拼装顺序展开完整英文，不使用缩写。",
                )
            )
        if panel_prompt.aspect_ratio != storyboard.panel_aspect_ratio:
            issues.append(
                _issue(
                    "panel-ratio-invalid",
                    "blocking",
                    f"第 {source.index} 格比例不是 {storyboard.panel_aspect_ratio}。",
                    "同篇正文使用统一比例。",
                )
            )
        if len(panel_prompt.background_objects) > 2:
            issues.append(
                _issue(
                    "background-too-complex",
                    "blocking",
                    f"第 {source.index} 格包含超过两个可识别背景物。",
                    "只保留最多两个叙事必要背景物。",
                )
            )
        for brand in present_brands:
            if brand_anchors[brand] not in prompt:
                issues.append(
                    _issue(
                        "brand-character-broken",
                        "blocking",
                        f"第 {source.index} 格没有展开 {brand} 固定角色锚点。",
                        "在每格 Prompt 原样重复相关品牌角色英文定义。",
                    )
                )
        if [item.model_dump() for item in panel_prompt.dialogue_items] != [
            item.model_dump() for item in source.dialogue_items
        ]:
            issues.append(
                _issue(
                    "dialogue-mismatch",
                    "blocking",
                    f"第 {source.index} 格结构化对白与分镜不一致。",
                    "逐字复制 dialogue_items，不能改标点或归属。",
                )
            )
        for item in source.dialogue_items:
            exact_clause = f'exact Chinese text: "{item.exact_text}"'
            if exact_clause not in prompt:
                issues.append(
                    _issue(
                        "dialogue-mismatch",
                        "blocking",
                        f"第 {source.index} 格 Prompt 没有逐字包含“{item.exact_text}”。",
                        f"加入 `{exact_clause}`。",
                    )
                )
            if item.kind == "speech":
                speaker = _brand_name(item.speaker or "")
                tail = f"the speech bubble tail clearly points to {speaker}"
                if not speaker or tail not in prompt or bubble_clause not in prompt:
                    issues.append(
                        _issue(
                            "dialogue-owner-invalid",
                            "blocking",
                            f"第 {source.index} 格气泡没有正确指向说话人。",
                            "明确写出 speech bubble tail 指向 Yier 或 Bubu。",
                        )
                    )
            if len(item.exact_text) > 12:
                issues.append(
                    _issue(
                        "dialogue-too-long",
                        "warning",
                        f"第 {source.index} 格单泡超过 12 个字符。",
                        "建议拆泡；该 warning 不阻止人工批准。",
                    )
                )

    cover = prompts.cover_prompt_en
    if not cover.startswith(style):
        issues.append(
            _issue(
                "visual-rule-missing",
                "blocking",
                "封面 Prompt 没有以 v5.3 固定画风全文开头。",
                "将 rules.style_prefix 原样放在封面 Prompt 最前面。",
            )
        )
    for label, clause in (
        ("固定画风", style),
        ("双裁切规则", crop_clause),
        ("封面无文字", no_text_clause),
        ("满幅规则", full_bleed),
        ("时间规则", time_clause),
    ):
        if clause not in cover:
            issues.append(
                _issue(
                    "cover-crop-unsafe" if label == "双裁切规则" else "visual-rule-missing",
                    "blocking",
                    f"封面 Prompt 缺少{label}全文。",
                    "按 v5.3 封面拼装顺序加入完整约束。",
                )
            )
    rendered_story_text = [
        item.exact_text
        for panel in storyboard.panels
        for item in panel.dialogue_items
        if item.exact_text
    ]
    if "exact Chinese text:" in cover or any(text in cover for text in rendered_story_text):
        issues.append(
            _issue(
                "cover-rendered-text",
                "blocking",
                "封面 Prompt 夹带了正文对白或可绘制中文。",
                "删除全部正文文字，只保留 no rendered text 封面约束。",
            )
        )
    required_package_fields = {
        "global_space.environment_en": prompts.global_space.environment_en,
        "cover_type": prompts.cover_type,
        "cover_background_mode": prompts.cover_background_mode,
        "cover_crop_safety": prompts.cover_crop_safety,
    }
    for field, value in required_package_fields.items():
        if not value:
            issues.append(
                _issue("schema-invalid", "blocking", f"视觉 Prompt 包缺少 {field}。", "补齐结构化说明字段。")
            )
    if prompts.cover_type and prompts.cover_type not in rules["cover"]["types"]:
        issues.append(
            _issue(
                "cover-type-invalid",
                "blocking",
                f"封面类型“{prompts.cover_type}”不在 v5.3 九种类型中。",
                "从 rules.cover.types 中选择。",
            )
        )
    if (
        prompts.cover_background_mode
        and prompts.cover_background_mode not in rules["cover"]["background_modes"]
    ):
        issues.append(
            _issue(
                "cover-background-invalid",
                "blocking",
                f"封面背景模式“{prompts.cover_background_mode}”不符合 v5.3。",
                "选择品牌纯色型或正文场景型。",
            )
        )
    return issues


def merge_review_results(llm_review: ReviewResult, deterministic: list[ReviewIssue]) -> ReviewResult:
    blocking = any(issue.severity == "blocking" for issue in deterministic)
    issues = deterministic + llm_review.issues
    instructions = [issue.suggestion for issue in deterministic if issue.severity == "blocking"]
    if llm_review.rewrite_instruction:
        instructions.append(llm_review.rewrite_instruction)
    return ReviewResult(
        passed=llm_review.passed and not blocking,
        score=min(llm_review.score, 79) if blocking else llm_review.score,
        issues=issues,
        rewrite_instruction="；".join(dict.fromkeys(instructions)),
    )
