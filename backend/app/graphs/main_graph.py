from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agents.base import AgentTraceContext
from app.agents.retro import RetroAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.storyboard import StoryboardAgent
from app.agents.strategy import StrategyAgent
from app.agents.visual import VisualAgent
from app.config import Settings
from app.domain.models import (
    ApprovalDecision,
    Artifact,
    KnowledgeProposal,
    PublicationInfo,
    ReviewResult,
    RunStage,
    SkillRunRecord,
    Storyboard,
    TopicCandidate,
    VisualPromptPackage,
)
from app.domain.state import AgentState
from app.domain.visual_rules import (
    merge_review_results,
    normalize_storyboard_handoff,
    validate_storyboard_for_visual,
)
from app.domain.writeback import ApprovedWritebackService
from app.graphs.events import EventBroker
from app.graphs.prompt_graph import build_prompt_subgraph
from app.graphs.retro_graph import build_retro_subgraph
from app.graphs.storyboard_graph import build_storyboard_subgraph
from app.graphs.topic_graph import build_topic_subgraph
from app.rag.hybrid import HybridRagService
from app.repositories.base import ProjectRepository


@dataclass(slots=True)
class GraphDependencies:
    settings: Settings
    repository: ProjectRepository
    events: EventBroker
    rag: HybridRagService
    operations: Any
    strategy: StrategyAgent
    storyboard: StoryboardAgent
    reviewer: ReviewerAgent
    visual: VisualAgent
    retro: RetroAgent
    writeback: ApprovedWritebackService


def build_content_graph(deps: GraphDependencies, checkpointer: Any):
    skill_registry = deps.strategy.skills

    def current_skill_plan() -> dict[str, str]:
        return {
            name: skill_registry.load(name).version
            for name in skill_registry.available()
        }

    def frozen_skill_version(state: AgentState, name: str) -> str | None:
        """新运行读取冻结计划；旧 checkpoint 优先沿用已记录的 1.0 代际。"""

        normalized = skill_registry.normalize_name(name)
        planned = state.get("skill_plan", {}).get(normalized)
        if planned:
            return planned
        recorded = state.get("skill_versions", {}).get(normalized, {}).get("version")
        if recorded:
            return recorded
        recorded_versions = {
            item.get("version") for item in state.get("skill_versions", {}).values()
        }
        available = skill_registry.available().get(normalized, [])
        if "1.0.0" in recorded_versions and "1.0.0" in available:
            return "1.0.0"
        return None

    def uses_v11(state: AgentState, name: str) -> bool:
        version = frozen_skill_version(state, name)
        return bool(version and tuple(int(part) for part in version.split(".")) >= (1, 1, 0))

    async def node_started(state: AgentState, name: str) -> None:
        await deps.events.emit("node.started", state["thread_id"], state["project_id"], node_name=name)

    async def artifact_ready(state: AgentState, kind: str, data: dict[str, Any]) -> dict[str, int]:
        versions = dict(state.get("artifact_versions", {}))
        suggested_version = versions.get(kind, 0) + 1
        artifact = Artifact(kind=kind, version=suggested_version, data=data)
        # Repository 以项目为范围原子分配最终版本；Fork 分支不能与旧路线撞版本。
        artifact = await deps.repository.save_artifact(
            state["project_id"], state["thread_id"], artifact
        )
        versions[kind] = artifact.version
        await deps.events.emit(
            "artifact.ready",
            state["thread_id"],
            state["project_id"],
            artifact=artifact.model_dump(mode="json"),
        )
        return versions

    def skill_versions(state: AgentState, execution: Any) -> dict[str, dict[str, str]]:
        versions = dict(state.get("skill_versions", {}))
        versions[execution.skill.name] = execution.skill.model_dump()
        return versions

    async def record_execution(state: AgentState, node_name: str, execution: Any) -> None:
        await deps.repository.record_skill_run(
            SkillRunRecord(
                id=execution.id,
                project_id=state["project_id"],
                thread_id=state["thread_id"],
                node_name=node_name,
                skill_name=execution.skill.name,
                skill_version=execution.skill.version,
                prompt_hash=execution.skill.prompt_hash,
                model_provider=execution.provider,
                model_name=execution.model_name,
                input_hash=execution.input_hash,
                output=execution.output.model_dump(mode="json"),
                latency_ms=execution.latency_ms,
            )
        )

    def trace_context(state: AgentState, node_name: str) -> AgentTraceContext:
        return AgentTraceContext(
            project_id=state["project_id"],
            thread_id=state["thread_id"],
            node_name=node_name,
        )

    async def entry(state: AgentState) -> dict:
        return {}

    def route_entry(state: AgentState) -> str:
        return state.get("resume_node") or "initialize"

    async def initialize(state: AgentState) -> dict:
        await node_started(state, "initialize")
        return {
            "stage": RunStage.INITIALIZE.value,
            "evidence": state.get("evidence", []),
            "retrieval_degraded": False,
            "topic_candidates": [],
            "selected_topic": None,
            "storyboard": None,
            "visual_prompts": None,
            "prompt_review": None,
            "metrics": state.get("metrics", []),
            "skill_plan": state.get("skill_plan") or current_skill_plan(),
            "skill_versions": state.get("skill_versions", {}),
            "artifact_versions": state.get("artifact_versions", {}),
            "rework_counts": state.get("rework_counts", {}),
            "resume_node": None,
        }

    async def load_context(state: AgentState) -> dict:
        await node_started(state, "load_context")
        rag_task = deps.rag.retrieve(state["inspiration"])
        performance_task = deps.operations.call_tool("query_recent_performance", {"limit": 10})
        similar_task = deps.operations.call_tool(
            "search_similar_articles", {"query": state["inspiration"], "limit": 6}
        )
        rag_result, performance, similar = await asyncio.gather(rag_task, performance_task, similar_task)
        evidence = [item.model_dump(mode="json") for item in rag_result.evidence]
        evidence.append(
            {
                "id": "exact-recent-performance",
                "source_type": "metrics",
                "title": "最近文章精确指标",
                "source_path": "wechat://metrics/recent",
                "excerpt": json.dumps(performance, ensure_ascii=False)[:1000],
                "score": 1.0,
                "published_at": None,
                "retrieval_mode": "exact",
            }
        )
        return {
            "evidence": evidence,
            "similar_articles": similar,
            "retrieval_degraded": rag_result.degraded,
            "stage": RunStage.TOPIC.value,
        }

    async def generate_topics(state: AgentState) -> dict:
        await node_started(state, "generate_topics")
        execution = await deps.strategy.propose_topics(
            {
                "inspiration": state["inspiration"],
                "target_audience": state["target_audience"],
                "evidence": state.get("evidence", []),
                "similar_articles": state.get("similar_articles", []),
                "review_instruction": state.get("last_error"),
            },
            version=frozen_skill_version(state, "topic-strategy"),
            trace_context=trace_context(state, "generate_topics"),
        )
        await record_execution(state, "generate_topics", execution)
        candidates = execution.output.candidates
        if len(candidates) != 3:
            raise ValueError("Strategy Agent 必须输出恰好三个候选")
        data = {"candidates": [item.model_dump() for item in candidates]}
        versions = await artifact_ready(state, "topics", data)
        return {
            "topic_candidates": data["candidates"],
            "artifact_versions": versions,
            "skill_versions": skill_versions(state, execution),
            "stage": RunStage.TOPIC_APPROVAL.value,
            "approval": None,
        }

    async def topic_approval(state: AgentState) -> dict:
        await node_started(state, "topic_approval")
        response = interrupt(
            {
                "kind": "topic",
                "message": "请选择、修改或自定义一个选题",
                "candidates": state["topic_candidates"],
            }
        )
        decision = ApprovalDecision(response["decision"])
        if decision in {ApprovalDecision.REGENERATE, ApprovalDecision.REJECT}:
            return {"approval": response, "stage": RunStage.TOPIC.value}
        if decision == ApprovalDecision.CUSTOM:
            selected = TopicCandidate.model_validate(response["custom_topic"])
        else:
            candidate_id = response.get("selected_candidate_id")
            selected_raw = next(
                (item for item in state["topic_candidates"] if item["id"] == candidate_id),
                None,
            )
            if selected_raw is None:
                raise ValueError("请选择一个存在的候选选题")
            selected_raw = {**selected_raw, **response.get("state_patch", {}).get("topic", {})}
            selected = TopicCandidate.model_validate(selected_raw)
        return {
            "approval": response,
            "selected_topic": selected.model_dump(),
            "stage": RunStage.STORYBOARD.value,
        }

    def route_topic_approval(state: AgentState) -> str:
        decision = (state.get("approval") or {}).get("decision")
        return "generate_topics" if decision in {"regenerate", "reject"} else "generate_storyboard"

    async def generate_storyboard(state: AgentState) -> dict:
        await node_started(state, "generate_storyboard")
        execution = await deps.storyboard.design(
            {
                "selected_topic": state["selected_topic"],
                "target_audience": state["target_audience"],
                "evidence": state.get("evidence", []),
                "review_instruction": (state.get("storyboard_review") or {}).get("rewrite_instruction"),
            },
            version=frozen_skill_version(state, "storyboard-design"),
            trace_context=trace_context(state, "generate_storyboard"),
        )
        await record_execution(state, "generate_storyboard", execution)
        storyboard_model = execution.output
        if uses_v11(state, "storyboard-design"):
            storyboard_model = normalize_storyboard_handoff(
                storyboard_model,
                (state.get("selected_topic") or {}).get("narrative_mechanism", ""),
            )
        storyboard = storyboard_model.model_dump()
        versions = await artifact_ready(state, "storyboard", storyboard)
        return {
            "storyboard": storyboard,
            "artifact_versions": versions,
            "skill_versions": skill_versions(state, execution),
            "stage": RunStage.STORYBOARD.value,
        }

    async def review_storyboard(state: AgentState) -> dict:
        await node_started(state, "review_storyboard")
        deterministic = []
        if uses_v11(state, "storyboard-design"):
            deterministic = validate_storyboard_for_visual(
                Storyboard.model_validate(state["storyboard"])
            )
        execution = await deps.reviewer.review(
            "storyboard",
            state["storyboard"],
            state.get("evidence", []),
            context={"selected_topic": state.get("selected_topic")},
            validation_issues=[item.model_dump() for item in deterministic],
            version=frozen_skill_version(state, "content-review"),
            trace_context=trace_context(state, "review_storyboard"),
        )
        await record_execution(state, "review_storyboard", execution)
        review = merge_review_results(execution.output, deterministic) if deterministic else execution.output
        counts = dict(state.get("rework_counts", {}))
        if not review.passed:
            counts["storyboard"] = counts.get("storyboard", 0) + 1
        return {
            "storyboard_review": review.model_dump(),
            "rework_counts": counts,
            "skill_versions": skill_versions(state, execution),
            "stage": RunStage.STORYBOARD_APPROVAL.value,
        }

    def route_storyboard_review(state: AgentState) -> str:
        review = state["storyboard_review"]
        if review["passed"]:
            return "storyboard_approval"
        if state["rework_counts"].get("storyboard", 0) <= deps.settings.reviewer_max_reworks:
            return "generate_storyboard"
        return "storyboard_approval"

    async def storyboard_approval(state: AgentState) -> dict:
        await node_started(state, "storyboard_approval")
        response = interrupt(
            {
                "kind": "storyboard",
                "message": "编辑并批准分镜；人工确认后直接生成绘图 Prompt，审核意见仅供参考",
                "storyboard": state["storyboard"],
                "review": state["storyboard_review"],
            }
        )
        decision = ApprovalDecision(response["decision"])
        if decision in {ApprovalDecision.REGENERATE, ApprovalDecision.REJECT}:
            return {"approval": response, "stage": RunStage.STORYBOARD.value}
        patched = response.get("state_patch", {}).get("storyboard", state["storyboard"])
        storyboard = Storyboard.model_validate(patched)
        review = ReviewResult.model_validate(state["storyboard_review"])
        if uses_v11(state, "storyboard-design"):
            storyboard = normalize_storyboard_handoff(
                storyboard,
                (state.get("selected_topic") or {}).get("narrative_mechanism", ""),
            )
            deterministic = validate_storyboard_for_visual(storyboard)
            # 上一轮确定性问题可能已被用户修复；只保留 LLM 问题后重新校验，
            # 避免旧 blocking issue 永远把审批锁在原地。
            llm_issues = [issue for issue in review.issues if issue.source == "llm"]
            llm_blocking = any(issue.severity == "blocking" for issue in llm_issues)
            review = merge_review_results(
                review.model_copy(
                    update={
                        "passed": not llm_blocking,
                        "score": review.score if llm_blocking else max(review.score, 80),
                        "issues": llm_issues,
                    }
                ),
                deterministic,
            )
        return {
            "approval": response,
            "storyboard": storyboard.model_dump(),
            "storyboard_review": review.model_dump(),
            # 用户已经在人工审批点明确确认。校验结果继续保存在
            # storyboard_review 中供后续追踪，但不再覆盖人的最终决定。
            "stage": RunStage.VISUAL_PROMPT.value,
        }

    def route_storyboard_approval(state: AgentState) -> str:
        decision = (state.get("approval") or {}).get("decision")
        if decision in {"regenerate", "reject"}:
            return "generate_storyboard"
        # edit / approve 都代表用户已确认当前分镜，直接进入 Prompt 生成。
        return "generate_prompts"

    async def generate_prompts(state: AgentState) -> dict:
        await node_started(state, "generate_prompts")
        panel_index = (state.get("approval") or {}).get("state_patch", {}).get("panel_index")
        execution = await deps.visual.build_prompts(
            {
                "storyboard": state["storyboard"],
                "selected_topic": state.get("selected_topic"),
                "target_panel_index": panel_index,
                "previous_visual_prompts": state.get("visual_prompts") if panel_index else None,
            },
            version=frozen_skill_version(state, "visual-prompt"),
            trace_context=trace_context(state, "generate_prompts"),
        )
        await record_execution(state, "generate_prompts", execution)
        prompts = execution.output.model_dump()
        if panel_index and state.get("visual_prompts"):
            previous = VisualPromptPackage.model_validate(state["visual_prompts"])
            replacement = next(item for item in execution.output.panels if item.panel_index == panel_index)
            merged = [replacement if item.panel_index == panel_index else item for item in previous.panels]
            prompts = previous.model_copy(update={"panels": merged}).model_dump()
        versions = await artifact_ready(state, "visual_prompts", prompts)
        return {
            "visual_prompts": prompts,
            "artifact_versions": versions,
            "skill_versions": skill_versions(state, execution),
            # Prompt 生成后不再调用 Reviewer，也不再自动返工，直接交给用户确认。
            "prompt_review": None,
            "stage": RunStage.PROMPT_APPROVAL.value,
        }

    async def prompt_approval(state: AgentState) -> dict:
        await node_started(state, "prompt_approval")
        response = interrupt(
            {
                "kind": "visual_prompt",
                "message": "批准全部 Prompt，或指定 panel_index 单格重生成",
                "visual_prompts": state["visual_prompts"],
            }
        )
        decision = ApprovalDecision(response["decision"])
        if decision in {ApprovalDecision.REGENERATE, ApprovalDecision.REJECT}:
            return {"approval": response, "stage": RunStage.VISUAL_PROMPT.value}
        patched = response.get("state_patch", {}).get("visual_prompts", state["visual_prompts"])
        prompts = VisualPromptPackage.model_validate(patched)
        return {
            "approval": response,
            "visual_prompts": prompts.model_dump(),
            "stage": RunStage.READY_TO_PUBLISH.value,
        }

    def route_prompt_approval(state: AgentState) -> str:
        decision = (state.get("approval") or {}).get("decision")
        return "generate_prompts" if decision in {"regenerate", "reject"} else "create_prediction"

    async def create_prediction(state: AgentState) -> dict:
        await node_started(state, "create_prediction")
        execution = await deps.strategy.predict(
            {
                "selected_topic": state["selected_topic"],
                "storyboard": state["storyboard"],
                "evidence": state.get("evidence", []),
            },
            version=frozen_skill_version(state, "topic-strategy"),
            trace_context=trace_context(state, "create_prediction"),
        )
        await record_execution(state, "create_prediction", execution)
        data = execution.output.model_dump()
        versions = await artifact_ready(state, "prediction", data)
        return {
            "prediction": data,
            "artifact_versions": versions,
            "skill_versions": skill_versions(state, execution),
            "stage": RunStage.READY_TO_PUBLISH.value,
        }

    async def publication_wait(state: AgentState) -> dict:
        await node_started(state, "publication_wait")
        response = interrupt(
            {
                "kind": "publication",
                "message": "产物已就绪。公众号发布后请登记标题和发布时间。",
                "prediction": state["prediction"],
            }
        )
        publication = PublicationInfo.model_validate(response["publication"])
        return {
            "publication": publication.model_dump(mode="json"),
            "stage": RunStage.WAITING_METRICS.value,
        }

    async def metrics_wait(state: AgentState) -> dict:
        await node_started(state, "metrics_wait")
        existing_hours = max(
            (float(item.get("hours_since_publish", 0)) for item in state.get("metrics", [])),
            default=0,
        )
        target = 24 if existing_hours < 24 else 48
        response = interrupt(
            {
                "kind": "metrics",
                "message": f"等待发布后 {target}h 指标；可由 Worker 或“立即同步”恢复",
                "target_hours": target,
            }
        )
        metrics = response.get("metrics", [])
        if not metrics:
            return {"stage": RunStage.WAITING_METRICS.value}
        return {"metrics": metrics, "stage": RunStage.RETRO.value}

    async def generate_retro(state: AgentState) -> dict:
        await node_started(state, "generate_retro")
        execution = await deps.retro.analyze(
            {
                "prediction": state["prediction"],
                "metrics": state["metrics"],
                "selected_topic": state["selected_topic"],
                "storyboard": state["storyboard"],
                "evidence": state.get("evidence", []),
            },
            version=frozen_skill_version(state, "performance-retro"),
            trace_context=trace_context(state, "generate_retro"),
        )
        await record_execution(state, "generate_retro", execution)
        data = execution.output.model_dump()
        versions = await artifact_ready(state, "retro", data)
        latest_hours = max(
            (float(item.get("hours_since_publish", 0)) for item in state["metrics"]),
            default=0,
        )
        return {
            "retro": data,
            "retro_milestone": 48 if latest_hours >= 48 else 24,
            "artifact_versions": versions,
            "skill_versions": skill_versions(state, execution),
            "stage": RunStage.KNOWLEDGE_APPROVAL.value,
        }

    async def knowledge_approval(state: AgentState) -> dict:
        await node_started(state, "knowledge_approval")
        response = interrupt(
            {
                "kind": "knowledge",
                "message": "批准复盘写回；可只批准部分 proposal_indexes",
                "milestone": state.get("retro_milestone"),
                "retro": state["retro"],
            }
        )
        return {"approval": response}

    async def apply_knowledge(state: AgentState) -> dict:
        await node_started(state, "apply_knowledge")
        response = state.get("approval") or {}
        results: list[dict[str, Any]] = []
        if response.get("decision") == ApprovalDecision.APPROVE.value:
            publication = PublicationInfo.model_validate(state["publication"])
            proposals = [
                KnowledgeProposal.model_validate(item) for item in state["retro"]["knowledge_proposals"]
            ]
            results = await deps.writeback.apply(
                project_id=state["project_id"],
                thread_id=state["thread_id"],
                publication=publication,
                proposals=proposals,
                approval_patch=response.get("state_patch", {}),
            )
        latest_hours = max(
            (float(item.get("hours_since_publish", 0)) for item in state.get("metrics", [])),
            default=0,
        )
        update: dict[str, Any] = {"writeback_results": results}
        # interrupt 发生前节点不会提交新的返回值。先在这里写入等待阶段，
        # 前端和 Worker 才能在第二轮 metrics_wait 暂停时看到正确状态。
        if latest_hours < 48:
            update["stage"] = RunStage.WAITING_METRICS.value
        return update

    def route_after_knowledge(state: AgentState) -> str:
        latest_hours = max(
            (float(item.get("hours_since_publish", 0)) for item in state.get("metrics", [])),
            default=0,
        )
        return "finalize" if latest_hours >= 48 else "metrics_wait"

    async def finalize(state: AgentState) -> dict:
        await node_started(state, "finalize")
        return {"stage": RunStage.COMPLETED.value}

    topic_subgraph = build_topic_subgraph(generate_topics, topic_approval, route_topic_approval)
    storyboard_subgraph = build_storyboard_subgraph(
        generate_storyboard,
        review_storyboard,
        storyboard_approval,
        route_storyboard_review,
        route_storyboard_approval,
    )
    prompt_subgraph = build_prompt_subgraph(
        generate_prompts,
        prompt_approval,
        route_prompt_approval,
    )
    retro_subgraph = build_retro_subgraph(
        metrics_wait,
        generate_retro,
        knowledge_approval,
        apply_knowledge,
        route_after_knowledge,
    )

    graph = StateGraph(AgentState)
    nodes = {
        "entry": entry,
        "initialize": initialize,
        "load_context": load_context,
        "topic_flow": topic_subgraph,
        "storyboard_flow": storyboard_subgraph,
        "prompt_flow": prompt_subgraph,
        "create_prediction": create_prediction,
        "publication_wait": publication_wait,
        "retro_flow": retro_subgraph,
        "finalize": finalize,
    }
    for name, function in nodes.items():
        graph.add_node(name, function)
    graph.add_edge(START, "entry")
    graph.add_conditional_edges("entry", route_entry, {name: name for name in nodes if name != "entry"})
    graph.add_edge("initialize", "load_context")
    graph.add_edge("load_context", "topic_flow")
    graph.add_edge("topic_flow", "storyboard_flow")
    graph.add_edge("storyboard_flow", "prompt_flow")
    graph.add_edge("prompt_flow", "create_prediction")
    graph.add_edge("create_prediction", "publication_wait")
    graph.add_edge("publication_wait", "retro_flow")
    graph.add_edge("retro_flow", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
