from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies import get_container
from app.container import ServiceContainer
from app.domain.models import ForkRequest, LlmTraceSummary, ResumeRequest

router = APIRouter(prefix="/api/runs", tags=["runs"])
Container = Annotated[ServiceContainer, Depends(get_container)]


@router.get("/{thread_id}/events")
async def stream_events(thread_id: str, container: Container):
    async def event_generator():
        async for item in container.events.subscribe(thread_id):
            yield {
                "event": item.event,
                "id": item.id,
                "data": json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
            }

    return EventSourceResponse(event_generator(), ping=15)


@router.post("/{thread_id}/resume", status_code=202)
async def resume_run(thread_id: str, payload: ResumeRequest, container: Container):
    await container.workflow.resume(thread_id, payload)
    return {"thread_id": thread_id, "status": "accepted"}


@router.get("/{thread_id}/state")
async def get_run_state(thread_id: str, container: Container):
    return await container.workflow.state(thread_id)


@router.get("/{thread_id}/history")
async def get_run_history(thread_id: str, container: Container):
    return await container.workflow.history(thread_id)


@router.get("/{thread_id}/llm-traces", response_model=list[LlmTraceSummary])
async def list_llm_traces(thread_id: str, container: Container):
    records = await container.repository.list_llm_traces(thread_id)
    summary_fields = set(LlmTraceSummary.model_fields)
    return [
        LlmTraceSummary.model_validate(record.model_dump(include=summary_fields))
        for record in records
    ]


@router.get("/{thread_id}/llm-traces/{trace_id}")
async def get_llm_trace(thread_id: str, trace_id: str, container: Container):
    return await container.repository.get_llm_trace(thread_id, trace_id)


@router.post("/{thread_id}/fork", status_code=202)
async def fork_run(thread_id: str, payload: ForkRequest, container: Container):
    new_thread_id = await container.workflow.fork(thread_id, payload)
    return {
        "thread_id": new_thread_id,
        "forked_from": {"thread_id": thread_id, "checkpoint_id": payload.checkpoint_id},
        "status": "accepted",
    }
