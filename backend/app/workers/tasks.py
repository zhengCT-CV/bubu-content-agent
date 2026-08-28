from __future__ import annotations

from app.container import ServiceContainer
from app.domain.models import ProjectStatus


async def poll_published_projects(container: ServiceContainer) -> dict[str, int]:
    """每小时找等待指标的项目；只有达到 24h/48h 才恢复 Graph。"""

    checked = synced = resumed = 0
    for project in await container.repository.list_projects():
        if project.status != ProjectStatus.WAITING_METRICS or not project.publication:
            continue
        checked += 1
        snapshots, matches = await container.metrics.sync(project.publication)
        if not snapshots or (not project.publication.article_id and len(matches) != 1):
            continue
        for snapshot in snapshots:
            synced += int(await container.repository.add_metrics(project.id, snapshot))
        all_metrics = await container.repository.list_metrics(project.id)
        state = await container.workflow.state(project.active_thread_id or "")
        previous = max(
            (float(item.get("hours_since_publish", 0)) for item in state["values"].get("metrics", [])),
            default=0,
        )
        target = 48 if previous >= 24 else 24
        latest = max((item.hours_since_publish for item in all_metrics), default=0)
        if latest >= target and state["values"].get("stage") == "waiting_metrics":
            await container.workflow.resume_metrics(
                project.active_thread_id or "",
                [item.model_dump(mode="json") for item in all_metrics],
            )
            resumed += 1
    return {"checked": checked, "synced": synced, "resumed": resumed}


async def arq_poll_published_projects(ctx: dict) -> dict[str, int]:
    return await poll_published_projects(ctx["container"])
