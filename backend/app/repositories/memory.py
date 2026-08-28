from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from app.domain.errors import NotFoundError
from app.domain.models import (
    Artifact,
    LlmTraceRecord,
    MetricsSnapshot,
    ProjectCreate,
    ProjectRecord,
    ProjectStatus,
    PublicationInfo,
    RunEvent,
    SkillRunRecord,
    utc_now,
)


class InMemoryProjectRepository:
    """演示和单元测试仓储；接口与 PostgreSQL 版本一致。"""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectRecord] = {}
        self._states: dict[str, dict[str, Any]] = {}
        self._events: dict[str, list[RunEvent]] = defaultdict(list)
        self._artifacts: dict[str, list[Artifact]] = defaultdict(list)
        self._metrics: dict[str, list[MetricsSnapshot]] = defaultdict(list)
        self._idempotency: set[str] = set()
        self._skill_runs: dict[str, list[SkillRunRecord]] = defaultdict(list)
        self._llm_traces: dict[str, list[LlmTraceRecord]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def create_project(self, payload: ProjectCreate) -> ProjectRecord:
        project = ProjectRecord(**payload.model_dump())
        async with self._lock:
            self._projects[project.id] = project
        return project

    async def list_projects(self) -> list[ProjectRecord]:
        return sorted(self._projects.values(), key=lambda item: item.updated_at, reverse=True)

    async def get_project(self, project_id: str) -> ProjectRecord:
        try:
            return self._projects[project_id]
        except KeyError as exc:
            raise NotFoundError(f"项目不存在：{project_id}") from exc

    async def update_project(
        self,
        project_id: str,
        *,
        status: ProjectStatus | None = None,
        active_thread_id: str | None = None,
        publication: PublicationInfo | None = None,
        state: dict[str, Any] | None = None,
    ) -> ProjectRecord:
        current = await self.get_project(project_id)
        update: dict[str, Any] = {"updated_at": utc_now()}
        if status is not None:
            update["status"] = status
        if active_thread_id is not None:
            update["active_thread_id"] = active_thread_id
        if publication is not None:
            update["publication"] = publication
        async with self._lock:
            project = current.model_copy(update=update)
            self._projects[project_id] = project
            if state is not None:
                self._states[project_id] = state
        return project

    async def add_event(self, event: RunEvent) -> None:
        async with self._lock:
            self._events[event.thread_id].append(event)

    async def list_events(self, thread_id: str) -> list[RunEvent]:
        return list(self._events[thread_id])

    async def save_artifact(self, project_id: str, thread_id: str, artifact: Artifact) -> Artifact:
        async with self._lock:
            latest = max(
                (item.version for item in self._artifacts[project_id] if item.kind == artifact.kind),
                default=0,
            )
            stored = artifact.model_copy(update={"version": latest + 1})
            self._artifacts[project_id].append(stored)
            return stored

    async def add_metrics(self, project_id: str, snapshot: MetricsSnapshot) -> bool:
        key = (snapshot.article_id, snapshot.captured_at.isoformat())
        async with self._lock:
            if any(
                (item.article_id, item.captured_at.isoformat()) == key for item in self._metrics[project_id]
            ):
                return False
            self._metrics[project_id].append(snapshot)
        return True

    async def list_metrics(self, project_id: str) -> list[MetricsSnapshot]:
        await self.get_project(project_id)
        return sorted(self._metrics[project_id], key=lambda item: item.captured_at)

    async def claim_idempotency(self, key: str, operation: str) -> bool:
        namespaced = f"{operation}:{key}"
        async with self._lock:
            if namespaced in self._idempotency:
                return False
            self._idempotency.add(namespaced)
        return True

    async def record_skill_run(self, record: SkillRunRecord) -> None:
        async with self._lock:
            self._skill_runs[record.thread_id].append(record)

    async def list_skill_runs(self, thread_id: str) -> list[SkillRunRecord]:
        return list(self._skill_runs[thread_id])

    async def record_llm_trace(self, record: LlmTraceRecord) -> None:
        async with self._lock:
            self._llm_traces[record.thread_id].append(record)

    async def list_llm_traces(self, thread_id: str) -> list[LlmTraceRecord]:
        return sorted(self._llm_traces[thread_id], key=lambda item: item.created_at, reverse=True)

    async def get_llm_trace(self, thread_id: str, trace_id: str) -> LlmTraceRecord:
        trace = next((item for item in self._llm_traces[thread_id] if item.id == trace_id), None)
        if trace is None:
            raise NotFoundError(f"LLM 调用记录不存在：{trace_id}")
        return trace

    async def list_project_llm_traces(self, project_id: str) -> list[LlmTraceRecord]:
        await self.get_project(project_id)
        traces = [
            trace
            for thread_traces in self._llm_traces.values()
            for trace in thread_traces
            if trace.project_id == project_id
        ]
        return sorted(traces, key=lambda item: item.created_at, reverse=True)

    async def get_project_llm_trace(self, project_id: str, trace_id: str) -> LlmTraceRecord:
        traces = await self.list_project_llm_traces(project_id)
        trace = next((item for item in traces if item.id == trace_id), None)
        if trace is None:
            raise NotFoundError(f"LLM 调用记录不存在：{trace_id}")
        return trace
