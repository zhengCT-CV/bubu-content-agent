from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.agents.retro import RetroAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.storyboard import StoryboardAgent
from app.agents.strategy import StrategyAgent
from app.agents.visual import VisualAgent
from app.config import Settings, get_settings
from app.domain.content_data import ContentDataService
from app.domain.metrics import MetricsService
from app.domain.writeback import ApprovedWritebackService
from app.graphs.events import EventBroker
from app.graphs.main_graph import GraphDependencies, build_content_graph
from app.graphs.service import WorkflowService
from app.integrations.embeddings import build_embedding_gateway
from app.integrations.llm import build_model_gateway
from app.integrations.mcp_client import build_operations_gateway
from app.rag.documents import KnowledgeSource
from app.rag.hybrid import HybridRagService, PostgresHybridIndex
from app.repositories.base import ProjectRepository
from app.repositories.database import Database
from app.repositories.memory import InMemoryProjectRepository
from app.repositories.postgres import PostgresProjectRepository
from app.skills.registry import SkillRegistry


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    repository: ProjectRepository
    workflow: WorkflowService
    events: EventBroker
    metrics: MetricsService
    content_data: ContentDataService
    operations: Any
    graph: Any


def _build_container(
    settings: Settings,
    repository: ProjectRepository,
    checkpointer: Any,
    database: Database | None,
) -> ServiceContainer:
    skills = SkillRegistry()
    model = build_model_gateway(settings, repository)
    operations = build_operations_gateway(settings)
    embeddings = build_embedding_gateway(settings)
    rag_index = PostgresHybridIndex(database, embeddings) if database else None
    rag = HybridRagService(KnowledgeSource(operations), index=rag_index, limit=settings.retrieval_limit)
    events = EventBroker(repository)
    dependencies = GraphDependencies(
        settings=settings,
        repository=repository,
        events=events,
        rag=rag,
        operations=operations,
        strategy=StrategyAgent(model, skills),
        storyboard=StoryboardAgent(model, skills),
        reviewer=ReviewerAgent(model, skills),
        visual=VisualAgent(model, skills),
        retro=RetroAgent(model, skills),
        writeback=ApprovedWritebackService(operations, settings),
    )
    graph = build_content_graph(dependencies, checkpointer)
    return ServiceContainer(
        settings=settings,
        repository=repository,
        workflow=WorkflowService(graph, repository, events),
        events=events,
        metrics=MetricsService(operations),
        content_data=ContentDataService(settings.wechat_workspace_path),
        operations=operations,
        graph=graph,
    )


@asynccontextmanager
async def open_service_container(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.app_mode == "demo":
        yield _build_container(
            settings,
            InMemoryProjectRepository(),
            MemorySaver(),
            None,
        )
        return

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    database = Database(settings.database_url)
    repository = PostgresProjectRepository(database)
    await repository.setup()
    async with AsyncPostgresSaver.from_conn_string(settings.checkpoint_database_url) as checkpointer:
        await checkpointer.setup()
        try:
            yield _build_container(settings, repository, checkpointer, database)
        finally:
            await database.dispose()
