from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from app.domain.errors import ConflictError, NotFoundError
from app.domain.models import (
    ForkRequest,
    ProjectRecord,
    ProjectStatus,
    PublicationInfo,
    ResumeRequest,
    RunStage,
)
from app.graphs.events import EventBroker
from app.logging import logger
from app.repositories.base import ProjectRepository

STAGE_STATUS = {
    RunStage.TOPIC_APPROVAL.value: ProjectStatus.WAITING_APPROVAL,
    RunStage.STORYBOARD_APPROVAL.value: ProjectStatus.WAITING_APPROVAL,
    RunStage.PROMPT_APPROVAL.value: ProjectStatus.WAITING_APPROVAL,
    RunStage.READY_TO_PUBLISH.value: ProjectStatus.READY_TO_PUBLISH,
    RunStage.WAITING_METRICS.value: ProjectStatus.WAITING_METRICS,
    RunStage.KNOWLEDGE_APPROVAL.value: ProjectStatus.WAITING_APPROVAL,
    RunStage.COMPLETED.value: ProjectStatus.COMPLETED,
    RunStage.FAILED.value: ProjectStatus.FAILED,
}


class WorkflowService:
    def __init__(self, graph: Any, repository: ProjectRepository, events: EventBroker) -> None:
        self.graph = graph
        self.repository = repository
        self.events = events
        self._tasks: set[asyncio.Task] = set()

    @staticmethod
    def config(thread_id: str, checkpoint_id: str | None = None) -> dict:
        configurable = {"thread_id": thread_id}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id
        return {"configurable": configurable, "recursion_limit": 80}

    def _spawn(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @classmethod
    def _effective_snapshot(cls, snapshot: Any) -> Any:
        """进入当前活跃子图，返回用户真正看到的状态。"""

        current = snapshot
        while True:
            nested = next(
                (task.state for task in current.tasks if hasattr(task.state, "values") and task.state.values),
                None,
            )
            if nested is None:
                return current
            current = nested

    @classmethod
    def _interrupts(cls, snapshot: Any) -> list[Any]:
        """递归提取子图 interrupt，并按 LangGraph interrupt id 去重。"""

        found: list[Any] = []
        seen: set[str] = set()

        def visit(current: Any) -> None:
            for task in current.tasks:
                for item in task.interrupts:
                    key = str(getattr(item, "id", repr(getattr(item, "value", item))))
                    if key not in seen:
                        seen.add(key)
                        found.append(item)
                if hasattr(task.state, "tasks"):
                    visit(task.state)

        visit(snapshot)
        return found

    async def start(self, project: ProjectRecord) -> str:
        if project.active_thread_id and project.status == ProjectStatus.RUNNING:
            raise ConflictError("该项目已有运行中的工作流")
        thread_id = str(uuid4())
        initial = {
            "project_id": project.id,
            "thread_id": thread_id,
            "project_name": project.name,
            "inspiration": project.inspiration,
            "target_audience": project.target_audience,
            "stage": RunStage.INITIALIZE.value,
            "metrics": [],
            "skill_plan": {},
            "skill_versions": {},
            "artifact_versions": {},
            "rework_counts": {},
        }
        await self.repository.update_project(
            project.id,
            status=ProjectStatus.RUNNING,
            active_thread_id=thread_id,
            state=initial,
        )
        await self.events.emit("run.started", thread_id, project.id)
        self._spawn(self._drive(thread_id, project.id, initial))
        return thread_id

    async def _drive(self, thread_id: str, project_id: str, input_value: Any) -> None:
        try:
            await self.graph.ainvoke(input_value, self.config(thread_id))
            snapshot = await self.get_snapshot(thread_id)
            effective = self._effective_snapshot(snapshot)
            values = dict(effective.values)
            stage = values.get("stage", RunStage.FAILED.value)
            status = STAGE_STATUS.get(stage, ProjectStatus.RUNNING)
            await self.repository.update_project(
                project_id, status=status, active_thread_id=thread_id, state=values
            )
            interrupts = self._interrupts(snapshot)
            if interrupts:
                payloads = [getattr(item, "value", item) for item in interrupts]
                await self.events.emit(
                    "interrupt.waiting",
                    thread_id,
                    project_id,
                    stage=stage,
                    interrupts=payloads,
                )
            elif not effective.next and not snapshot.next:
                await self.events.emit("run.completed", thread_id, project_id, stage=stage)
        except Exception as exc:
            logger.exception(
                "run.failed",
                project_id=project_id,
                thread_id=thread_id,
                error_type=type(exc).__name__,
            )
            await self.repository.update_project(
                project_id,
                status=ProjectStatus.FAILED,
                active_thread_id=thread_id,
            )
            await self.events.emit(
                "run.failed",
                thread_id,
                project_id,
                error_type=type(exc).__name__,
                message=str(exc),
            )

    async def resume(self, thread_id: str, request: ResumeRequest) -> None:
        snapshot = await self.get_snapshot(thread_id)
        effective = self._effective_snapshot(snapshot)
        project_id = effective.values["project_id"]
        if not self._interrupts(snapshot):
            raise ConflictError("当前工作流没有等待中的人工审批")
        payload = request.model_dump(mode="json", exclude_none=True)
        self._spawn(self._drive(thread_id, project_id, Command(resume=payload)))

    async def publish(self, thread_id: str, publication: PublicationInfo) -> None:
        snapshot = await self.get_snapshot(thread_id)
        effective = self._effective_snapshot(snapshot)
        if effective.values.get("stage") != RunStage.READY_TO_PUBLISH.value:
            raise ConflictError("当前工作流尚未等待发布登记")
        project_id = effective.values["project_id"]
        await self.repository.update_project(
            project_id,
            status=ProjectStatus.PUBLISHED,
            publication=publication,
        )
        self._spawn(
            self._drive(
                thread_id,
                project_id,
                Command(resume={"publication": publication.model_dump(mode="json")}),
            )
        )

    async def resume_metrics(self, thread_id: str, metrics: list[dict]) -> None:
        snapshot = await self.get_snapshot(thread_id)
        effective = self._effective_snapshot(snapshot)
        if effective.values.get("stage") != RunStage.WAITING_METRICS.value:
            raise ConflictError("当前工作流未等待指标")
        project_id = effective.values["project_id"]
        self._spawn(self._drive(thread_id, project_id, Command(resume={"metrics": metrics})))

    async def get_snapshot(self, thread_id: str):
        snapshot = await self.graph.aget_state(self.config(thread_id), subgraphs=True)
        if not snapshot.values:
            raise NotFoundError(f"运行不存在：{thread_id}")
        return snapshot

    async def state(self, thread_id: str) -> dict[str, Any]:
        snapshot = await self.get_snapshot(thread_id)
        effective = self._effective_snapshot(snapshot)
        return {
            "values": effective.values,
            "next": list(effective.next),
            "checkpoint_id": snapshot.config.get("configurable", {}).get("checkpoint_id"),
            "interrupts": [getattr(item, "value", item) for item in self._interrupts(snapshot)],
        }

    async def history(self, thread_id: str) -> list[dict[str, Any]]:
        result = []
        async for snapshot in self.graph.aget_state_history(self.config(thread_id)):
            result.append(
                {
                    "checkpoint_id": snapshot.config.get("configurable", {}).get("checkpoint_id"),
                    "created_at": snapshot.created_at,
                    "next": list(snapshot.next),
                    "stage": snapshot.values.get("stage"),
                    "metadata": snapshot.metadata,
                }
            )
        return result

    async def fork(self, thread_id: str, request: ForkRequest) -> str:
        source = await self.graph.aget_state(self.config(thread_id, request.checkpoint_id), subgraphs=True)
        if not source.values:
            raise NotFoundError(f"checkpoint 不存在：{request.checkpoint_id}")
        new_thread_id = str(uuid4())
        effective = self._effective_snapshot(source)
        state = dict(effective.values)
        state.update(request.state_patch)
        state["thread_id"] = new_thread_id
        # 新 thread 从旧 checkpoint 的下一节点进入；原 thread/checkpoint 不会被覆盖。
        state["resume_node"] = source.next[0] if source.next else "finalize"
        project_id = state["project_id"]
        await self.repository.update_project(
            project_id,
            status=ProjectStatus.RUNNING,
            active_thread_id=new_thread_id,
            state=state,
        )
        await self.events.emit(
            "run.started",
            new_thread_id,
            project_id,
            forked_from={"thread_id": thread_id, "checkpoint_id": request.checkpoint_id},
        )
        self._spawn(self._drive(new_thread_id, project_id, state))
        return new_thread_id
