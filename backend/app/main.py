from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.data_center import router as data_center_router
from app.api.errors import register_error_handlers
from app.api.projects import router as projects_router
from app.api.runs import router as runs_router
from app.api.system import router as system_router
from app.config import get_settings
from app.container import open_service_container
from app.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with open_service_container(settings) as container:
        app.state.container = container
        yield


app = FastAPI(
    title="Bubu ContentOps Agent",
    version="0.1.0",
    description="微信公众号条漫选题、分镜、视觉 Prompt 和数据复盘工作台",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(system_router)
app.include_router(data_center_router)
app.include_router(projects_router)
app.include_router(runs_router)
register_error_handlers(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=True)
