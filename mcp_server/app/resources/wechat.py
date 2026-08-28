from __future__ import annotations

import asyncio
import json

from mcp.server.fastmcp import FastMCP

from mcp_server.app.adapters.wechat_workspace import WorkspaceAdapter


def register_resources(mcp: FastMCP, adapter: WorkspaceAdapter) -> None:
    @mcp.resource("wechat://knowledge/playbook")
    async def knowledge_playbook() -> str:
        return await asyncio.to_thread(adapter.playbook)

    @mcp.resource("wechat://reviews/recent")
    async def reviews_recent() -> str:
        data = await asyncio.to_thread(adapter.recent_reviews)
        return json.dumps(data, ensure_ascii=False)

    @mcp.resource("wechat://articles/recent")
    async def articles_recent() -> str:
        data = await asyncio.to_thread(adapter.recent_article_records)
        return json.dumps(data, ensure_ascii=False)

    @mcp.resource("wechat://articles/{article_id}/metrics")
    async def article_metrics(article_id: str) -> str:
        data = await asyncio.to_thread(adapter.hourly_curve, article_id)
        return json.dumps(data, ensure_ascii=False)

    @mcp.resource("wechat://articles/{article_id}/details")
    async def article_detail_resource(article_id: str) -> str:
        data = await asyncio.to_thread(adapter.article_details, article_id)
        return json.dumps(data, ensure_ascii=False)
