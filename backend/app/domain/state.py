from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """LangGraph 中唯一流转的可序列化状态。

    这里故意使用 dict/list 等 JSON 友好类型，避免 checkpoint 绑定具体
    Pydantic 版本；进入节点时再做 Schema 校验。
    """

    project_id: str
    thread_id: str
    project_name: str
    inspiration: str
    target_audience: str
    stage: str
    evidence: list[dict[str, Any]]
    retrieval_degraded: bool
    topic_candidates: list[dict[str, Any]]
    selected_topic: dict[str, Any] | None
    storyboard: dict[str, Any] | None
    storyboard_review: dict[str, Any] | None
    visual_prompts: dict[str, Any] | None
    prompt_review: dict[str, Any] | None
    prediction: dict[str, Any] | None
    publication: dict[str, Any] | None
    metrics: list[dict[str, Any]]
    retro: dict[str, Any] | None
    approval: dict[str, Any] | None
    skill_plan: dict[str, str]
    skill_versions: dict[str, dict[str, str]]
    artifact_versions: dict[str, int]
    rework_counts: dict[str, int]
    last_error: dict[str, Any] | None
    similar_articles: list[dict[str, Any]]
    retro_milestone: int
    writeback_results: list[dict[str, Any]]
    resume_node: str | None
