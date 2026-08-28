from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_container
from app.container import ServiceContainer
from app.domain.content_data import ContentDataUnavailableError

router = APIRouter(prefix="/api/data-center", tags=["data-center"])
Container = Annotated[ServiceContainer, Depends(get_container)]


@router.get("/overview")
async def get_data_center_overview(
    container: Container,
    refresh: bool = Query(default=False),
):
    try:
        return await container.content_data.overview(force=refresh)
    except ContentDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/articles/{article_id}")
async def get_article_data(article_id: str, container: Container):
    try:
        result = await container.content_data.article_detail(article_id)
    except ContentDataUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="没有找到这篇作品的数据")
    return result
