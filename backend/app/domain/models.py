from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    WAITING_METRICS = "waiting_metrics"
    COMPLETED = "completed"
    FAILED = "failed"


class RunStage(StrEnum):
    INITIALIZE = "initialize"
    TOPIC = "topic"
    TOPIC_APPROVAL = "topic_approval"
    STORYBOARD = "storyboard"
    STORYBOARD_APPROVAL = "storyboard_approval"
    VISUAL_PROMPT = "visual_prompt"
    PROMPT_APPROVAL = "prompt_approval"
    READY_TO_PUBLISH = "ready_to_publish"
    WAITING_METRICS = "waiting_metrics"
    RETRO = "retro"
    KNOWLEDGE_APPROVAL = "knowledge_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"
    CUSTOM = "custom"
    REGENERATE = "regenerate"


class EvidenceCitation(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: Literal["playbook", "weekly_review", "article_record", "metrics"]
    title: str
    source_path: str
    excerpt: str
    score: float = Field(ge=0, le=1)
    published_at: datetime | None = None
    retrieval_mode: Literal["hybrid", "semantic", "fulltext", "exact"] = "hybrid"


class TopicCandidate(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(min_length=4, max_length=64)
    core_conflict: str
    narrative_mechanism: str
    audience_value: str
    hook: str
    predicted_strength: int = Field(ge=0, le=100)
    duplicate_risk: int = Field(ge=0, le=100)
    evidence_ids: list[str] = Field(default_factory=list)


class CharacterSpec(StrictModel):
    name: str
    identity: str
    visual_anchor: str


class DialogueItem(StrictModel):
    """分镜中的精确文字指令；保留标点，供 Visual Prompt 逐字引用。"""

    kind: Literal["speech", "narration", "inner_thought"]
    speaker: Literal["一二", "布布", "Yier", "Bubu"] | None = None
    exact_text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_speech_speaker(self) -> DialogueItem:
        if self.kind == "speech" and self.speaker is None:
            raise ValueError("speech 对白必须指定一二或布布")
        return self


class TimelineItem(StrictModel):
    panel_index: int = Field(ge=1, le=12)
    time_of_day: str
    lighting: str = ""


class VisualHandoffCard(StrictModel):
    """Storyboard Agent 交给 Visual Agent 的显式视觉上下文。"""

    time_anchor: str = ""
    environment_baseline: str = ""
    fixed_props: list[str] = Field(default_factory=list)
    time_object_strategy: str = "禁止未在脚本指定的可读时间"
    timeline: list[TimelineItem] = Field(default_factory=list)
    emotional_peak_panel: int | None = Field(default=None, ge=1, le=12)
    comedy_peak_panel: int | None = Field(default=None, ge=1, le=12)
    narrative_mechanism: str = ""
    cover_brief: str = ""
    inferred_notes: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class StoryboardPanel(StrictModel):
    index: int = Field(ge=1, le=12)
    purpose: str
    scene: str
    action: str
    emotion: str
    dialogue: str = ""
    dialogue_items: list[DialogueItem] = Field(default_factory=list)
    camera: str
    time_of_day: str
    props: list[str] = Field(default_factory=list)


class Storyboard(StrictModel):
    title: str
    summary: str
    interaction_question: str
    characters: list[CharacterSpec]
    cover_brief: str
    panels: list[StoryboardPanel]
    ending: str
    panel_aspect_ratio: Literal["4:3", "1:1"] = "4:3"
    handoff_card: VisualHandoffCard | None = None

    @field_validator("panels")
    @classmethod
    def validate_panel_count(cls, value: list[StoryboardPanel]) -> list[StoryboardPanel]:
        if not 6 <= len(value) <= 10:
            raise ValueError("分镜必须为 6–10 格")
        expected = list(range(1, len(value) + 1))
        if [item.index for item in value] != expected:
            raise ValueError("分镜序号必须从 1 连续递增")
        return value


class PanelPrompt(StrictModel):
    panel_index: int = Field(ge=1, le=12)
    description_zh: str = ""
    time_lighting: str = ""
    camera: str = ""
    subject_ratio: str = ""
    core_action: str = ""
    comic_symbols: list[str] = Field(default_factory=list, max_length=2)
    dialogue_items: list[DialogueItem] = Field(default_factory=list)
    background_objects: list[str] = Field(default_factory=list, max_length=2)
    aspect_ratio: Literal["4:3", "1:1"] = "4:3"
    prompt_en: str
    negative_prompt_en: str
    continuity_notes: str


class VisualGlobalSpace(StrictModel):
    environment_en: str = ""
    main_palette: str = ""
    costumes: str = ""
    prop_consistency: str = ""


class TimelineCheck(StrictModel):
    items: list[TimelineItem] = Field(default_factory=list)
    monotonic: bool = True
    time_object_strategy: str = ""
    notes: list[str] = Field(default_factory=list)


class CoverDescription(StrictModel):
    composition_focus: str = ""
    character_action: str = ""
    emotional_hook: str = ""
    key_prop: str = ""
    storyboard_relation: str = ""
    crop_safety: str = ""


class VisualPromptPackage(StrictModel):
    style_prefix: str
    character_bible: str
    core_props: list[str] = Field(default_factory=list)
    # 这是整篇作品可能使用的背景物清单，不是单格清单。每格最多两个背景物
    # 的限制由 PanelPrompt.background_objects 和确定性校验负责。
    allowed_background_objects: list[str] = Field(default_factory=list)
    global_space: VisualGlobalSpace = Field(default_factory=VisualGlobalSpace)
    reference_reminders: list[str] = Field(default_factory=list)
    timeline_check: TimelineCheck = Field(default_factory=TimelineCheck)
    cover_type: str = ""
    cover_background_mode: str = ""
    cover_description_zh: CoverDescription = Field(default_factory=CoverDescription)
    cover_crop_safety: str = ""
    cover_prompt_en: str
    cover_negative_prompt_en: str
    panels: list[PanelPrompt]


class ReviewIssue(StrictModel):
    code: str
    severity: Literal["info", "warning", "blocking"]
    message: str
    suggestion: str
    source: Literal["llm", "deterministic"] = "llm"


class ReviewResult(StrictModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    issues: list[ReviewIssue] = Field(default_factory=list)
    rewrite_instruction: str = ""


class Prediction(StrictModel):
    expected_reads_24h: int = Field(ge=0)
    expected_reads_48h: int = Field(ge=0)
    expected_share_rate: float = Field(ge=0)
    rationale: list[str]


class PublicationInfo(StrictModel):
    title: str
    published_at: datetime
    article_id: str | None = None
    article_url: str | None = None


class MetricsSnapshot(StrictModel):
    article_id: str
    captured_at: datetime
    hours_since_publish: float = Field(ge=0)
    reads: int = Field(ge=0)
    shares: int = Field(ge=0)
    likes: int = Field(ge=0)
    favorites: int = Field(ge=0)
    new_followers: int = Field(ge=0)

    @property
    def share_rate(self) -> float:
        return self.shares / self.reads if self.reads else 0.0


class KnowledgeProposal(StrictModel):
    target: Literal["article_record", "weekly_review", "playbook"]
    heading: str
    markdown: str
    evidence: list[str]


class RetroReport(StrictModel):
    verdict: str
    prediction_comparison: dict[str, Any]
    strengths: list[str]
    weaknesses: list[str]
    next_actions: list[str]
    knowledge_proposals: list[KnowledgeProposal]


class Artifact(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["topics", "storyboard", "visual_prompts", "prediction", "retro"]
    version: int = Field(ge=1)
    data: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)


class SkillSnapshot(StrictModel):
    name: str
    version: str
    prompt_hash: str


class SkillRunRecord(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    thread_id: str
    node_name: str
    skill_name: str
    skill_version: str
    prompt_hash: str
    model_provider: str
    model_name: str
    input_hash: str
    output: dict[str, Any]
    latency_ms: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class LlmTraceContext(StrictModel):
    """一次业务节点调用 LLM 时携带的可追溯上下文。"""

    skill_run_id: str
    project_id: str
    thread_id: str
    node_name: str
    skill_name: str
    skill_version: str
    prompt_hash: str


class LlmTraceRecord(StrictModel):
    """一次真实模型请求；Schema 修复和网络重试会分别产生记录。"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    skill_run_id: str
    project_id: str
    thread_id: str
    node_name: str
    skill_name: str
    skill_version: str
    prompt_hash: str
    model_provider: str
    model_name: str
    schema_name: str
    attempt: int = Field(ge=1)
    schema_attempt: int = Field(ge=1)
    status: Literal["success", "schema_error", "error", "legacy"]
    messages: list[dict[str, str]] = Field(default_factory=list)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    raw_output: str | None = None
    parsed_output: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class LlmTraceSummary(StrictModel):
    id: str
    skill_run_id: str
    thread_id: str
    node_name: str
    skill_name: str
    skill_version: str
    model_provider: str
    model_name: str
    schema_name: str
    attempt: int
    schema_attempt: int
    status: Literal["success", "schema_error", "error", "legacy"]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: int
    created_at: datetime


class ProjectCreate(StrictModel):
    name: str = Field(min_length=2, max_length=80)
    inspiration: str = Field(min_length=2, max_length=4000)
    target_audience: str = Field(default="关注个人成长与职场表达的微信公众号读者")


class ProjectRecord(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    inspiration: str
    target_audience: str
    status: ProjectStatus = ProjectStatus.DRAFT
    active_thread_id: str | None = None
    publication: PublicationInfo | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ResumeRequest(StrictModel):
    decision: ApprovalDecision
    selected_candidate_id: str | None = None
    custom_topic: TopicCandidate | None = None
    state_patch: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class ForkRequest(StrictModel):
    checkpoint_id: str
    state_patch: dict[str, Any] = Field(default_factory=dict)


class PublishRequest(StrictModel):
    title: str
    published_at: datetime
    article_id: str | None = None
    article_url: str | None = None


class RunEvent(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    event: Literal[
        "run.started",
        "node.started",
        "token.delta",
        "artifact.ready",
        "interrupt.waiting",
        "run.completed",
        "run.failed",
    ]
    thread_id: str
    project_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ErrorResponse(StrictModel):
    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
