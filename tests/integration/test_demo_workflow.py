from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from app.config import Settings
from app.container import open_service_container
from app.domain.models import (
    ApprovalDecision,
    ForkRequest,
    MetricsSnapshot,
    ProjectCreate,
    PublicationInfo,
    ResumeRequest,
)

from tests.helpers import build_wechat_fixture


async def wait_for_stage(workflow, thread_id: str, stage: str, attempts: int = 120):
    for _ in range(attempts):
        try:
            state = await workflow.state(thread_id)
            if state["values"].get("stage") == stage and state["interrupts"]:
                return state
        except Exception:
            pass
        await asyncio.sleep(0.05)
    raise AssertionError(f"没有等到阶段：{stage}")


@pytest.mark.asyncio
async def test_full_demo_flow_interrupt_resume_and_48h_loop(tmp_path) -> None:
    workspace = build_wechat_fixture(tmp_path / "ops")
    settings = Settings(
        app_mode="demo",
        text_model_provider="demo",
        wechat_workspace_path=workspace,
        writeback_approval_secret="test-secret",
    )
    async with open_service_container(settings) as container:
        project = await container.repository.create_project(
            ProjectCreate(name="测试作品", inspiration="总替同事收拾烂摊子")
        )
        thread_id = await container.workflow.start(project)

        topic_state = await wait_for_stage(container.workflow, thread_id, "topic_approval")
        assert topic_state["values"]["skill_plan"]["storyboard-design"] == "1.1.0"
        assert topic_state["values"]["skill_plan"]["visual-prompt"] == "1.1.0"
        branch_id = await container.workflow.fork(
            thread_id,
            ForkRequest(checkpoint_id=topic_state["checkpoint_id"]),
        )
        branch_state = await wait_for_stage(container.workflow, branch_id, "topic_approval")
        assert branch_state["values"]["thread_id"] == branch_id
        assert branch_state["values"]["topic_candidates"] == topic_state["values"]["topic_candidates"]
        candidate_id = topic_state["values"]["topic_candidates"][0]["id"]
        await container.workflow.resume(
            thread_id,
            ResumeRequest(
                decision=ApprovalDecision.APPROVE,
                selected_candidate_id=candidate_id,
            ),
        )
        original_storyboard = await wait_for_stage(
            container.workflow, thread_id, "storyboard_approval"
        )
        assert original_storyboard["values"]["artifact_versions"]["storyboard"] == 1

        # 分支从较早 checkpoint 继续时，分支状态里还没有 storyboard 版本；
        # Repository 仍必须读取项目全局最大值，分配 v2 而不是再次写 v1。
        await container.workflow.resume(
            branch_id,
            ResumeRequest(
                decision=ApprovalDecision.APPROVE,
                selected_candidate_id=candidate_id,
            ),
        )
        branch_storyboard = await wait_for_stage(
            container.workflow, branch_id, "storyboard_approval"
        )
        assert branch_storyboard["values"]["artifact_versions"]["storyboard"] == 2

        await container.workflow.resume(thread_id, ResumeRequest(decision=ApprovalDecision.APPROVE))
        prompt_state = await wait_for_stage(container.workflow, thread_id, "prompt_approval")
        assert prompt_state["values"]["visual_prompts"]["reference_reminders"][0] == "角色定妆表"
        assert "exact Chinese text" in prompt_state["values"]["visual_prompts"]["panels"][0]["prompt_en"]
        assert "centered 2.35:1 crop" in prompt_state["values"]["visual_prompts"]["cover_prompt_en"]
        await container.workflow.resume(thread_id, ResumeRequest(decision=ApprovalDecision.APPROVE))
        await wait_for_stage(container.workflow, thread_id, "ready_to_publish")

        publication = PublicationInfo(
            title="测试发布",
            published_at=datetime.now(UTC),
            article_id="demo-article",
        )
        await container.workflow.publish(thread_id, publication)
        await wait_for_stage(container.workflow, thread_id, "waiting_metrics")

        metric_24 = MetricsSnapshot(
            article_id="demo-article",
            captured_at=datetime.now(UTC),
            hours_since_publish=24,
            reads=1000,
            shares=30,
            likes=20,
            favorites=5,
            new_followers=2,
        )
        await container.workflow.resume_metrics(thread_id, [metric_24.model_dump(mode="json")])
        await wait_for_stage(container.workflow, thread_id, "knowledge_approval")
        await container.workflow.resume(thread_id, ResumeRequest(decision=ApprovalDecision.REJECT))
        await wait_for_stage(container.workflow, thread_id, "waiting_metrics")

        metric_48 = metric_24.model_copy(update={"hours_since_publish": 48, "reads": 1400})
        await container.workflow.resume_metrics(
            thread_id,
            [metric_24.model_dump(mode="json"), metric_48.model_dump(mode="json")],
        )
        await wait_for_stage(container.workflow, thread_id, "knowledge_approval")
        await container.workflow.resume(thread_id, ResumeRequest(decision=ApprovalDecision.REJECT))

        for _ in range(100):
            final = await container.workflow.state(thread_id)
            if final["values"].get("stage") == "completed":
                break
            await asyncio.sleep(0.05)
        assert final["values"]["stage"] == "completed"
        assert len(final["values"]["storyboard"]["panels"]) == 6
        assert len(final["values"]["visual_prompts"]["panels"]) == 6
        assert len(await container.workflow.history(thread_id)) >= 10
        skill_runs = await container.repository.list_skill_runs(thread_id)
        assert "review_prompts" not in {item.node_name for item in skill_runs}
        assert {item.skill_name for item in skill_runs} == {
            "topic-strategy",
            "storyboard-design",
            "content-review",
            "visual-prompt",
            "performance-retro",
        }
        assert all(item.prompt_hash and item.input_hash for item in skill_runs)
        traces = await container.repository.list_llm_traces(thread_id)
        assert len(traces) == len(skill_runs)
        assert all(item.status == "success" for item in traces)
        assert all(item.messages and item.input_payload for item in traces)
        assert all(item.parsed_output for item in traces)


@pytest.mark.asyncio
async def test_human_approval_overrides_storyboard_blocking_review(tmp_path) -> None:
    workspace = build_wechat_fixture(tmp_path / "ops")
    settings = Settings(
        app_mode="demo",
        text_model_provider="demo",
        wechat_workspace_path=workspace,
        writeback_approval_secret="test-secret",
    )
    async with open_service_container(settings) as container:
        project = await container.repository.create_project(
            ProjectCreate(name="品牌冲突", inspiration="有人替你问服务员")
        )
        thread_id = await container.workflow.start(project)
        topic_state = await wait_for_stage(container.workflow, thread_id, "topic_approval")
        await container.workflow.resume(
            thread_id,
            ResumeRequest(
                decision=ApprovalDecision.APPROVE,
                selected_candidate_id=topic_state["values"]["topic_candidates"][0]["id"],
            ),
        )
        storyboard_state = await wait_for_stage(
            container.workflow,
            thread_id,
            "storyboard_approval",
        )
        broken = deepcopy(storyboard_state["values"]["storyboard"])
        broken["characters"][0]["visual_anchor"] = "a young human with short hair and glasses"
        await container.workflow.resume(
            thread_id,
            ResumeRequest(
                decision=ApprovalDecision.EDIT,
                state_patch={"storyboard": broken},
            ),
        )

        state = await wait_for_stage(container.workflow, thread_id, "prompt_approval")
        issues = state["values"].get("storyboard_review", {}).get("issues", [])
        assert any(issue.get("code") == "brand-character-broken" for issue in issues)
        assert state["values"].get("visual_prompts") is not None
