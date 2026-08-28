from __future__ import annotations

from typing import Any, Protocol

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
)


class ProjectRepository(Protocol):
    async def create_project(self, payload: ProjectCreate) -> ProjectRecord: ...

    async def list_projects(self) -> list[ProjectRecord]: ...

    async def get_project(self, project_id: str) -> ProjectRecord: ...

    async def update_project(
        self,
        project_id: str,
        *,
        status: ProjectStatus | None = None,
        active_thread_id: str | None = None,
        publication: PublicationInfo | None = None,
        state: dict[str, Any] | None = None,
    ) -> ProjectRecord: ...

    async def add_event(self, event: RunEvent) -> None: ...

    async def list_events(self, thread_id: str) -> list[RunEvent]: ...

    async def save_artifact(self, project_id: str, thread_id: str, artifact: Artifact) -> Artifact: ...

    async def add_metrics(self, project_id: str, snapshot: MetricsSnapshot) -> bool: ...

    async def list_metrics(self, project_id: str) -> list[MetricsSnapshot]: ...

    async def claim_idempotency(self, key: str, operation: str) -> bool: ...

    async def record_skill_run(self, record: SkillRunRecord) -> None: ...

    async def list_skill_runs(self, thread_id: str) -> list[SkillRunRecord]: ...

    async def record_llm_trace(self, record: LlmTraceRecord) -> None: ...

    async def list_llm_traces(self, thread_id: str) -> list[LlmTraceRecord]: ...

    async def get_llm_trace(self, thread_id: str, trace_id: str) -> LlmTraceRecord: ...

    async def list_project_llm_traces(self, project_id: str) -> list[LlmTraceRecord]: ...

    async def get_project_llm_trace(self, project_id: str, trace_id: str) -> LlmTraceRecord: ...
