from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.config import get_settings
from app.container import open_service_container
from app.workers.tasks import arq_poll_published_projects


async def startup(ctx: dict) -> None:
    manager = open_service_container(get_settings())
    ctx["container_manager"] = manager
    ctx["container"] = await manager.__aenter__()


async def shutdown(ctx: dict) -> None:
    await ctx["container_manager"].__aexit__(None, None, None)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [arq_poll_published_projects]
    cron_jobs = [cron(arq_poll_published_projects, minute=0)]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 300
