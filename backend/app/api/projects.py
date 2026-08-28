from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_container
from app.container import ServiceContainer
from app.domain.models import LlmTraceSummary, ProjectCreate, PublicationInfo, PublishRequest

router = APIRouter(prefix="/api/projects", tags=["projects"])
Container = Annotated[ServiceContainer, Depends(get_container)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, container: Container):
    return await container.repository.create_project(payload)


@router.get("")
async def list_projects(container: Container):
    return await container.repository.list_projects()


@router.get("/{project_id}")
async def get_project(project_id: str, container: Container):
    return await container.repository.get_project(project_id)


@router.get("/{project_id}/llm-traces", response_model=list[LlmTraceSummary])
async def list_project_llm_traces(project_id: str, container: Container):
    records = await container.repository.list_project_llm_traces(project_id)
    summary_fields = set(LlmTraceSummary.model_fields)
    return [
        LlmTraceSummary.model_validate(record.model_dump(include=summary_fields))
        for record in records
    ]


@router.get("/{project_id}/llm-traces/{trace_id}")
async def get_project_llm_trace(project_id: str, trace_id: str, container: Container):
    return await container.repository.get_project_llm_trace(project_id, trace_id)


@router.post("/{project_id}/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_run(project_id: str, container: Container):
    project = await container.repository.get_project(project_id)
    thread_id = await container.workflow.start(project)
    return {"project_id": project_id, "thread_id": thread_id, "status": "accepted"}


@router.post("/{project_id}/publish", status_code=status.HTTP_202_ACCEPTED)
async def register_publish(project_id: str, payload: PublishRequest, container: Container):
    project = await container.repository.get_project(project_id)
    publication = PublicationInfo.model_validate(payload.model_dump())
    await container.workflow.publish(project.active_thread_id or "", publication)
    return {"project_id": project_id, "status": "registered"}


@router.post("/{project_id}/sync-metrics", status_code=status.HTTP_202_ACCEPTED)
async def sync_metrics(project_id: str, container: Container):
    project = await container.repository.get_project(project_id)
    if not project.publication:
        from app.domain.errors import ConflictError

        raise ConflictError("请先登记发布信息")
    snapshots, matches = await container.metrics.sync(project.publication)
    if not snapshots and len(matches) != 1:
        return {
            "status": "match_required" if len(matches) > 1 else "waiting",
            "matches": matches,
            "synced": 0,
        }
    inserted = 0
    for snapshot in snapshots:
        inserted += int(await container.repository.add_metrics(project_id, snapshot))
    all_metrics = await container.repository.list_metrics(project_id)
    latest_hours = max((item.hours_since_publish for item in all_metrics), default=0)
    state = await container.workflow.state(project.active_thread_id or "")
    target_hours = (
        48
        if max(
            (float(item.get("hours_since_publish", 0)) for item in state["values"].get("metrics", [])),
            default=0,
        )
        >= 24
        else 24
    )
    resumed = False
    if state["values"].get("stage") == "waiting_metrics" and latest_hours >= target_hours:
        await container.workflow.resume_metrics(
            project.active_thread_id or "",
            [item.model_dump(mode="json") for item in all_metrics],
        )
        resumed = True
    return {
        "status": "synced",
        "synced": inserted,
        "latest_hours": latest_hours,
        "target_hours": target_hours,
        "workflow_resumed": resumed,
    }


@router.get("/{project_id}/metrics")
async def get_metrics(project_id: str, container: Container):
    return await container.repository.list_metrics(project_id)
