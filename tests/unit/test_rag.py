from __future__ import annotations

import json

import pytest
from app.integrations.mcp_client import OperationsGateway
from app.rag.documents import KnowledgeSource
from app.rag.hybrid import HybridRagService


class FakeOperations(OperationsGateway):
    async def read_resource(self, uri: str) -> str:
        if uri.endswith("playbook"):
            return "# 长期打法\n具体动作钩子优于抽象说理"
        if uri.endswith("reviews/recent"):
            return json.dumps(
                [{"path": "5.1/weekly_review.md", "content": "身份冲突近期分享更好"}],
                ensure_ascii=False,
            )
        return json.dumps(
            [
                {
                    "article_id": "a",
                    "path": "drafts/a/article_record.md",
                    "content": "职场拒绝的具体场景",
                }
            ],
            ensure_ascii=False,
        )

    async def call_tool(self, name: str, arguments: dict):
        return []


@pytest.mark.asyncio
async def test_rag_returns_citations_and_marks_fulltext_fallback() -> None:
    service = HybridRagService(KnowledgeSource(FakeOperations()), limit=3)
    result = await service.retrieve("职场拒绝的具体动作")
    assert result.degraded is True
    assert result.evidence
    assert all(item.retrieval_mode == "fulltext" for item in result.evidence)
