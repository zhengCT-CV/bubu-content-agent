from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from app.integrations.mcp_client import OperationsGateway


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    source_type: str
    source_path: str
    title: str
    content: str
    published_at: datetime | None = None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(f"{self.source_type}:{self.source_path}:{self.content}".encode()).hexdigest()


def chunk_markdown(document: KnowledgeDocument, max_chars: int = 1200) -> list[KnowledgeDocument]:
    """按 Markdown 标题切块；超长段再按字符窗口切，保留来源路径。"""

    sections = re.split(r"(?=^#{1,4}\s+)", document.content, flags=re.MULTILINE)
    chunks: list[KnowledgeDocument] = []
    index = 0
    for section in sections:
        clean = section.strip()
        if not clean:
            continue
        for start in range(0, len(clean), max_chars):
            text = clean[start : start + max_chars]
            index += 1
            chunks.append(
                KnowledgeDocument(
                    source_type=document.source_type,
                    source_path=f"{document.source_path}#chunk-{index}",
                    title=document.title,
                    content=text,
                    published_at=document.published_at,
                )
            )
    return chunks


class KnowledgeSource:
    def __init__(self, operations: OperationsGateway) -> None:
        self.operations = operations

    async def load(self) -> list[KnowledgeDocument]:
        documents = [
            KnowledgeDocument(
                source_type="playbook",
                source_path="knowledge/content_playbook.md",
                title="长期内容打法",
                content=await self.operations.read_resource("wechat://knowledge/playbook"),
            )
        ]
        reviews = json.loads(await self.operations.read_resource("wechat://reviews/recent") or "[]")
        for item in reviews:
            documents.append(
                KnowledgeDocument(
                    source_type="weekly_review",
                    source_path=item["path"],
                    title=f"近期周复盘：{item['path']}",
                    content=item["content"],
                )
            )
        articles = json.loads(await self.operations.read_resource("wechat://articles/recent") or "[]")
        for item in articles:
            documents.append(
                KnowledgeDocument(
                    source_type="article_record",
                    source_path=item["path"],
                    title=f"历史案例：{item['article_id']}",
                    content=item["content"],
                )
            )
        return [chunk for document in documents for chunk in chunk_markdown(document)]
