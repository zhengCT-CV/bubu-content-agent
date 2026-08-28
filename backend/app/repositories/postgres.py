from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

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
)
from app.repositories.database import Database
from app.repositories.tables import (
    ArtifactRow,
    Base,
    IdempotencyRow,
    LlmTraceRow,
    MetricsSnapshotRow,
    ProjectRow,
    PublicationRow,
    RunEventRow,
    SkillRunRow,
)


class PostgresProjectRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def setup(self) -> None:
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        # 首次增加 Trace 表时，把旧 skill_runs 变为“历史兼容记录”。旧记录没有
        # 完整 Prompt/输入，但用户仍能在新页面看到过去的节点、输出和耗时。
        async with self.database.session() as session:
            traced_skill_run_ids = set(await session.scalars(select(LlmTraceRow.skill_run_id)))
            legacy_rows = (await session.scalars(select(SkillRunRow))).all()
            for row in legacy_rows:
                if row.id in traced_skill_run_ids:
                    continue
                session.add(
                    LlmTraceRow(
                        skill_run_id=row.id,
                        project_id=row.project_id,
                        thread_id=row.thread_id,
                        node_name=row.node_name,
                        skill_name=row.skill_name,
                        skill_version=row.skill_version,
                        prompt_hash=row.prompt_hash,
                        model_provider=row.model_provider,
                        model_name=row.model_name,
                        schema_name="历史结构化输出",
                        attempt=1,
                        schema_attempt=1,
                        status="legacy",
                        messages=[],
                        input_payload={},
                        parsed_output=row.output,
                        latency_ms=row.latency_ms,
                        created_at=row.created_at,
                    )
                )

    @staticmethod
    def _to_record(row: ProjectRow, publication: PublicationRow | None = None) -> ProjectRecord:
        publication_model = None
        if publication:
            publication_model = PublicationInfo(
                article_id=publication.article_id,
                title=publication.title,
                article_url=publication.article_url,
                published_at=publication.published_at,
            )
        return ProjectRecord(
            id=str(row.id),
            name=row.name,
            inspiration=row.inspiration,
            target_audience=row.target_audience,
            status=ProjectStatus(row.status),
            active_thread_id=row.active_thread_id,
            publication=publication_model,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create_project(self, payload: ProjectCreate) -> ProjectRecord:
        row = ProjectRow(**payload.model_dump(), status=ProjectStatus.DRAFT.value)
        async with self.database.session() as session:
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return self._to_record(row)

    async def list_projects(self) -> list[ProjectRecord]:
        async with self.database.session() as session:
            rows = (await session.scalars(select(ProjectRow).order_by(ProjectRow.updated_at.desc()))).all()
            publications = {
                item.project_id: item for item in (await session.scalars(select(PublicationRow))).all()
            }
            return [self._to_record(row, publications.get(row.id)) for row in rows]

    async def get_project(self, project_id: str) -> ProjectRecord:
        async with self.database.session() as session:
            row = await session.get(ProjectRow, UUID(project_id))
            if not row:
                raise NotFoundError(f"项目不存在：{project_id}")
            publication = await session.scalar(
                select(PublicationRow).where(PublicationRow.project_id == row.id)
            )
            return self._to_record(row, publication)

    async def update_project(
        self,
        project_id: str,
        *,
        status: ProjectStatus | None = None,
        active_thread_id: str | None = None,
        publication: PublicationInfo | None = None,
        state: dict[str, Any] | None = None,
    ) -> ProjectRecord:
        async with self.database.session() as session:
            project_uuid = UUID(project_id)
            row = await session.get(ProjectRow, project_uuid)
            if not row:
                raise NotFoundError(f"项目不存在：{project_id}")
            if status is not None:
                row.status = status.value
            if active_thread_id is not None:
                row.active_thread_id = active_thread_id
            if state is not None:
                row.current_state = state
            publication_row = await session.scalar(
                select(PublicationRow).where(PublicationRow.project_id == project_uuid)
            )
            if publication is not None:
                values = publication.model_dump()
                if publication_row:
                    for key, value in values.items():
                        setattr(publication_row, key, value)
                else:
                    publication_row = PublicationRow(project_id=project_uuid, **values)
                    session.add(publication_row)
            await session.flush()
            await session.refresh(row)
            return self._to_record(row, publication_row)

    async def add_event(self, event: RunEvent) -> None:
        async with self.database.session() as session:
            session.add(
                RunEventRow(
                    id=UUID(event.id),
                    project_id=UUID(event.project_id),
                    thread_id=event.thread_id,
                    event=event.event,
                    data=event.data,
                    created_at=event.created_at,
                )
            )

    async def list_events(self, thread_id: str) -> list[RunEvent]:
        async with self.database.session() as session:
            rows = (
                await session.scalars(
                    select(RunEventRow)
                    .where(RunEventRow.thread_id == thread_id)
                    .order_by(RunEventRow.created_at)
                )
            ).all()
            return [
                RunEvent(
                    id=str(row.id),
                    project_id=str(row.project_id),
                    thread_id=row.thread_id,
                    event=row.event,
                    data=row.data,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    async def save_artifact(self, project_id: str, thread_id: str, artifact: Artifact) -> Artifact:
        """按项目和产物类型分配全局递增版本，Fork 不能复用旧路线版本号。"""

        async with self.database.session() as session:
            project_uuid = UUID(project_id)
            # 对同一项目串行分配版本，防止两个分支同时生成同类产物时竞争。
            await session.scalar(
                select(ProjectRow.id).where(ProjectRow.id == project_uuid).with_for_update()
            )
            latest = await session.scalar(
                select(func.max(ArtifactRow.version)).where(
                    ArtifactRow.project_id == project_uuid,
                    ArtifactRow.kind == artifact.kind,
                )
            )
            stored = artifact.model_copy(update={"version": int(latest or 0) + 1})
            session.add(
                ArtifactRow(
                    id=UUID(stored.id),
                    project_id=project_uuid,
                    thread_id=thread_id,
                    kind=stored.kind,
                    version=stored.version,
                    data=stored.data,
                    created_at=stored.created_at,
                )
            )
            await session.flush()
            return stored

    async def add_metrics(self, project_id: str, snapshot: MetricsSnapshot) -> bool:
        async with self.database.session() as session:
            exists = await session.scalar(
                select(MetricsSnapshotRow.id).where(
                    MetricsSnapshotRow.article_id == snapshot.article_id,
                    MetricsSnapshotRow.captured_at == snapshot.captured_at,
                )
            )
            if exists:
                return False
            session.add(MetricsSnapshotRow(project_id=UUID(project_id), **snapshot.model_dump()))
            return True

    async def list_metrics(self, project_id: str) -> list[MetricsSnapshot]:
        await self.get_project(project_id)
        async with self.database.session() as session:
            rows = (
                await session.scalars(
                    select(MetricsSnapshotRow)
                    .where(MetricsSnapshotRow.project_id == UUID(project_id))
                    .order_by(MetricsSnapshotRow.captured_at)
                )
            ).all()
            return [
                MetricsSnapshot(
                    article_id=row.article_id,
                    captured_at=row.captured_at,
                    hours_since_publish=row.hours_since_publish,
                    reads=row.reads,
                    shares=row.shares,
                    likes=row.likes,
                    favorites=row.favorites,
                    new_followers=row.new_followers,
                )
                for row in rows
            ]

    async def claim_idempotency(self, key: str, operation: str) -> bool:
        async with self.database.session() as session:
            row = await session.get(IdempotencyRow, f"{operation}:{key}")
            if row:
                return False
            session.add(IdempotencyRow(key=f"{operation}:{key}", operation=operation, result={}))
            return True

    async def record_skill_run(self, record: SkillRunRecord) -> None:
        async with self.database.session() as session:
            session.add(
                SkillRunRow(
                    id=UUID(record.id),
                    project_id=UUID(record.project_id),
                    thread_id=record.thread_id,
                    node_name=record.node_name,
                    skill_name=record.skill_name,
                    skill_version=record.skill_version,
                    prompt_hash=record.prompt_hash,
                    model_provider=record.model_provider,
                    model_name=record.model_name,
                    input_hash=record.input_hash,
                    output=record.output,
                    latency_ms=record.latency_ms,
                    created_at=record.created_at,
                )
            )

    async def list_skill_runs(self, thread_id: str) -> list[SkillRunRecord]:
        async with self.database.session() as session:
            rows = (
                await session.scalars(
                    select(SkillRunRow)
                    .where(SkillRunRow.thread_id == thread_id)
                    .order_by(SkillRunRow.created_at)
                )
            ).all()
            return [
                SkillRunRecord(
                    id=str(row.id),
                    project_id=str(row.project_id),
                    thread_id=row.thread_id,
                    node_name=row.node_name,
                    skill_name=row.skill_name,
                    skill_version=row.skill_version,
                    prompt_hash=row.prompt_hash,
                    model_provider=row.model_provider,
                    model_name=row.model_name,
                    input_hash=row.input_hash,
                    output=row.output,
                    latency_ms=row.latency_ms,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    @staticmethod
    def _to_llm_trace(row: LlmTraceRow) -> LlmTraceRecord:
        return LlmTraceRecord(
            id=str(row.id),
            skill_run_id=str(row.skill_run_id),
            project_id=str(row.project_id),
            thread_id=row.thread_id,
            node_name=row.node_name,
            skill_name=row.skill_name,
            skill_version=row.skill_version,
            prompt_hash=row.prompt_hash,
            model_provider=row.model_provider,
            model_name=row.model_name,
            schema_name=row.schema_name,
            attempt=row.attempt,
            schema_attempt=row.schema_attempt,
            status=row.status,
            messages=row.messages,
            input_payload=row.input_payload,
            raw_output=row.raw_output,
            parsed_output=row.parsed_output,
            error_type=row.error_type,
            error_message=row.error_message,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            total_tokens=row.total_tokens,
            latency_ms=row.latency_ms,
            created_at=row.created_at,
        )

    async def record_llm_trace(self, record: LlmTraceRecord) -> None:
        async with self.database.session() as session:
            session.add(
                LlmTraceRow(
                    id=UUID(record.id),
                    skill_run_id=UUID(record.skill_run_id),
                    project_id=UUID(record.project_id),
                    thread_id=record.thread_id,
                    node_name=record.node_name,
                    skill_name=record.skill_name,
                    skill_version=record.skill_version,
                    prompt_hash=record.prompt_hash,
                    model_provider=record.model_provider,
                    model_name=record.model_name,
                    schema_name=record.schema_name,
                    attempt=record.attempt,
                    schema_attempt=record.schema_attempt,
                    status=record.status,
                    messages=record.messages,
                    input_payload=record.input_payload,
                    raw_output=record.raw_output,
                    parsed_output=record.parsed_output,
                    error_type=record.error_type,
                    error_message=record.error_message,
                    prompt_tokens=record.prompt_tokens,
                    completion_tokens=record.completion_tokens,
                    total_tokens=record.total_tokens,
                    latency_ms=record.latency_ms,
                    created_at=record.created_at,
                )
            )

    async def list_llm_traces(self, thread_id: str) -> list[LlmTraceRecord]:
        async with self.database.session() as session:
            rows = (
                await session.scalars(
                    select(LlmTraceRow)
                    .where(LlmTraceRow.thread_id == thread_id)
                    .order_by(LlmTraceRow.created_at.desc())
                )
            ).all()
            return [self._to_llm_trace(row) for row in rows]

    async def get_llm_trace(self, thread_id: str, trace_id: str) -> LlmTraceRecord:
        async with self.database.session() as session:
            row = await session.get(LlmTraceRow, UUID(trace_id))
            if row is None or row.thread_id != thread_id:
                raise NotFoundError(f"LLM 调用记录不存在：{trace_id}")
            return self._to_llm_trace(row)

    async def list_project_llm_traces(self, project_id: str) -> list[LlmTraceRecord]:
        await self.get_project(project_id)
        async with self.database.session() as session:
            rows = (
                await session.scalars(
                    select(LlmTraceRow)
                    .where(LlmTraceRow.project_id == UUID(project_id))
                    .order_by(LlmTraceRow.created_at.desc())
                )
            ).all()
            return [self._to_llm_trace(row) for row in rows]

    async def get_project_llm_trace(self, project_id: str, trace_id: str) -> LlmTraceRecord:
        async with self.database.session() as session:
            row = await session.get(LlmTraceRow, UUID(trace_id))
            if row is None or row.project_id != UUID(project_id):
                raise NotFoundError(f"LLM 调用记录不存在：{trace_id}")
            return self._to_llm_trace(row)
