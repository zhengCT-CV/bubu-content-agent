from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from app.config import Settings
from app.domain.errors import ExternalServiceError
from app.integrations.retry import external_retry


class OperationsGateway(ABC):
    @abstractmethod
    async def read_resource(self, uri: str) -> str: ...

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class HttpMcpOperationsGateway(OperationsGateway):
    """每次调用使用短连接，适合本地单用户；避免保存失效 Session。"""

    def __init__(self, url: str) -> None:
        self.url = url

    @external_retry
    async def read_resource(self, uri: str) -> str:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(self.url) as streams:
                read_stream, write_stream = streams[0], streams[1]
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.read_resource(uri)
                    return "\n".join(item.text for item in result.contents if hasattr(item, "text"))
        except Exception as exc:
            raise ExternalServiceError(
                "MCP Resource 读取失败",
                detail={"uri": uri, "type": type(exc).__name__},
            ) from exc

    @external_retry
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(self.url) as streams:
                read_stream, write_stream = streams[0], streams[1]
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    structured = getattr(result, "structuredContent", None)
                    if structured is not None:
                        return structured.get("result", structured)
                    texts = [item.text for item in result.content if hasattr(item, "text")]
                    if not texts:
                        return None
                    try:
                        return json.loads("\n".join(texts))
                    except json.JSONDecodeError:
                        return "\n".join(texts)
        except Exception as exc:
            raise ExternalServiceError(
                "MCP Tool 调用失败",
                detail={"tool": name, "type": type(exc).__name__},
            ) from exc


class DirectOperationsGateway(OperationsGateway):
    """demo/测试使用同一适配器逻辑，但不需要先启动 MCP 进程。"""

    def __init__(self, settings: Settings) -> None:
        from mcp_server.app.adapters.wechat_workspace import WorkspaceAdapter

        state_path = (
            settings.wechat_workspace_path.parent / ".bubu-content-agent-runtime" / "mcp-idempotency.sqlite3"
        )
        self.adapter = WorkspaceAdapter(
            settings.wechat_workspace_path,
            settings.writeback_approval_secret,
            state_path,
        )

    async def read_resource(self, uri: str) -> str:
        import asyncio

        if uri == "wechat://knowledge/playbook":
            return await asyncio.to_thread(self.adapter.playbook)
        if uri == "wechat://reviews/recent":
            return json.dumps(await asyncio.to_thread(self.adapter.recent_reviews), ensure_ascii=False)
        if uri == "wechat://articles/recent":
            return json.dumps(
                await asyncio.to_thread(self.adapter.recent_article_records),
                ensure_ascii=False,
            )
        if uri.startswith("wechat://articles/"):
            article_id, kind = uri.removeprefix("wechat://articles/").split("/", 1)
            if kind == "metrics":
                return json.dumps(
                    await asyncio.to_thread(self.adapter.hourly_curve, article_id),
                    ensure_ascii=False,
                )
            if kind == "details":
                return json.dumps(
                    await asyncio.to_thread(self.adapter.article_details, article_id),
                    ensure_ascii=False,
                )
        raise ExternalServiceError(f"未知 MCP Resource：{uri}")

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        import asyncio

        read_tools = {
            "query_recent_performance": self.adapter.recent_performance,
            "get_hourly_curve": self.adapter.hourly_curve,
            "search_similar_articles": self.adapter.search_similar,
            "get_article_details": self.adapter.article_details,
            "match_published_article": self.adapter.match_articles,
        }
        if name in read_tools:
            if name == "query_recent_performance":
                return await asyncio.to_thread(read_tools[name], arguments.get("limit", 10))
            if name == "get_hourly_curve" or name == "get_article_details":
                return await asyncio.to_thread(read_tools[name], arguments["article_id"])
            if name == "search_similar_articles":
                return await asyncio.to_thread(
                    read_tools[name], arguments["query"], arguments.get("limit", 8)
                )
            if name == "match_published_article":
                from datetime import datetime

                published = arguments.get("published_at_iso")
                return await asyncio.to_thread(
                    read_tools[name],
                    arguments["title"],
                    datetime.fromisoformat(published) if published else None,
                    arguments.get("window_hours", 12),
                )

        write_headings = {
            "create_article_record": "Agent 初始化",
            "append_prediction": "发布前预测",
            "append_retro": "Agent 复盘",
        }
        if name in write_headings or name == "apply_approved_knowledge_update":
            return await asyncio.to_thread(
                self.adapter.approved_markdown_write,
                operation=name,
                relative_path=arguments["relative_path"],
                heading=arguments.get("heading", write_headings.get(name, "知识更新")),
                markdown=arguments["markdown"],
                idempotency_key=arguments["idempotency_key"],
                approved=arguments["approved"],
                approval_secret=arguments["approval_secret"],
                create_if_missing=name == "create_article_record",
            )
        raise ExternalServiceError(f"未知 MCP Tool：{name}")


def build_operations_gateway(settings: Settings) -> OperationsGateway:
    if settings.app_mode == "demo":
        return DirectOperationsGateway(settings)
    return HttpMcpOperationsGateway(settings.mcp_server_url)
