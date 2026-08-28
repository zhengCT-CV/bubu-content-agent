from __future__ import annotations

import asyncio
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from mcp_server.app.adapters.wechat_workspace import WorkspaceAdapter


def register_tools(mcp: FastMCP, adapter: WorkspaceAdapter) -> None:
    @mcp.tool()
    async def query_recent_performance(limit: int = 10) -> list[dict]:
        """查询最近文章的精确表现；结构化指标不进入向量计算。"""

        return await asyncio.to_thread(adapter.recent_performance, limit)

    @mcp.tool()
    async def get_hourly_curve(article_id: str) -> list[dict]:
        return await asyncio.to_thread(adapter.hourly_curve, article_id)

    @mcp.tool()
    async def search_similar_articles(query: str, limit: int = 8) -> list[dict]:
        return await asyncio.to_thread(adapter.search_similar, query, limit)

    @mcp.tool()
    async def get_article_details(article_id: str) -> dict:
        return await asyncio.to_thread(adapter.article_details, article_id)

    @mcp.tool()
    async def match_published_article(
        title: str, published_at_iso: str | None = None, window_hours: int = 12
    ) -> list[dict]:
        published_at = datetime.fromisoformat(published_at_iso) if published_at_iso else None
        return await asyncio.to_thread(adapter.match_articles, title, published_at, window_hours)

    async def write_markdown(
        operation: str,
        relative_path: str,
        heading: str,
        markdown: str,
        idempotency_key: str,
        approved: bool,
        approval_secret: str,
        create_if_missing: bool = False,
    ) -> dict:
        return await asyncio.to_thread(
            adapter.approved_markdown_write,
            operation=operation,
            relative_path=relative_path,
            heading=heading,
            markdown=markdown,
            idempotency_key=idempotency_key,
            approved=approved,
            approval_secret=approval_secret,
            create_if_missing=create_if_missing,
        )

    @mcp.tool()
    async def create_article_record(
        relative_path: str,
        markdown: str,
        idempotency_key: str,
        approved: bool,
        approval_secret: str,
    ) -> dict:
        return await write_markdown(
            "create_article_record",
            relative_path,
            "Agent 初始化",
            markdown,
            idempotency_key,
            approved,
            approval_secret,
            create_if_missing=True,
        )

    @mcp.tool()
    async def append_prediction(
        relative_path: str,
        markdown: str,
        idempotency_key: str,
        approved: bool,
        approval_secret: str,
    ) -> dict:
        return await write_markdown(
            "append_prediction",
            relative_path,
            "发布前预测",
            markdown,
            idempotency_key,
            approved,
            approval_secret,
        )

    @mcp.tool()
    async def append_retro(
        relative_path: str,
        markdown: str,
        idempotency_key: str,
        approved: bool,
        approval_secret: str,
    ) -> dict:
        return await write_markdown(
            "append_retro",
            relative_path,
            "Agent 复盘",
            markdown,
            idempotency_key,
            approved,
            approval_secret,
        )

    @mcp.tool()
    async def apply_approved_knowledge_update(
        relative_path: str,
        heading: str,
        markdown: str,
        idempotency_key: str,
        approved: bool,
        approval_secret: str,
    ) -> dict:
        return await write_markdown(
            "apply_approved_knowledge_update",
            relative_path,
            heading,
            markdown,
            idempotency_key,
            approved,
            approval_secret,
        )
