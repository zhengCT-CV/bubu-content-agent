from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.models import MetricsSnapshot, PublicationInfo
from app.integrations.mcp_client import OperationsGateway


class MetricsService:
    def __init__(self, operations: OperationsGateway) -> None:
        self.operations = operations

    async def find_publication_matches(self, publication: PublicationInfo) -> list[dict[str, Any]]:
        return await self.operations.call_tool(
            "match_published_article",
            {
                "title": publication.title,
                "published_at_iso": publication.published_at.isoformat(),
                "window_hours": 12,
            },
        )

    async def sync(self, publication: PublicationInfo) -> tuple[list[MetricsSnapshot], list[dict[str, Any]]]:
        article_id = publication.article_id
        matches: list[dict[str, Any]] = []
        if not article_id:
            matches = await self.find_publication_matches(publication)
            if len(matches) != 1:
                return [], matches
            article_id = matches[0]["article_id"]
        curve = await self.operations.call_tool("get_hourly_curve", {"article_id": article_id})
        snapshots = []
        for item in curve or []:
            captured = item.get("captured_at")
            if not captured:
                continue
            snapshots.append(
                MetricsSnapshot(
                    article_id=str(article_id),
                    captured_at=datetime.fromisoformat(captured),
                    hours_since_publish=float(item.get("hours_since_publish") or 0),
                    reads=int(item.get("reads") or 0),
                    shares=int(item.get("shares") or 0),
                    likes=int(item.get("likes") or 0),
                    favorites=int(item.get("favorites") or 0),
                    new_followers=int(item.get("new_followers") or 0),
                )
            )
        return snapshots, matches
