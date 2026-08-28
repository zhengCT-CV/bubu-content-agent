from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_container
from app.container import ServiceContainer
from app.skills.registry import SkillRegistry

router = APIRouter(prefix="/api", tags=["system"])
Container = Annotated[ServiceContainer, Depends(get_container)]


@router.get("/health")
async def health(container: Container):
    return {
        "status": "ok",
        "mode": container.settings.app_mode,
        "skills": SkillRegistry().available(),
    }
