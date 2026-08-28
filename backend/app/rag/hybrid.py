from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.domain.models import EvidenceCitation
from app.integrations.embeddings import EmbeddingGateway
from app.logging import logger
from app.rag.documents import KnowledgeDocument, KnowledgeSource
from app.repositories.database import Database
from app.repositories.tables import KnowledgeChunkRow

SOURCE_WEIGHT = {"metrics": 1.0, "weekly_review": 0.95, "article_record": 0.85, "playbook": 0.8}


def _tokens(text: str) -> set[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    bigrams = {normalized[index : index + 2] for index in range(max(0, len(normalized) - 1))}
    words = set(re.findall(r"[a-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text.lower()))
    return bigrams | words


def lexical_score(query: str, content: str) -> float:
    left, right = _tokens(query), _tokens(content)
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    return min(1.0, overlap / math.sqrt(len(left) * min(len(right), 100)))


def _recency_score(published_at: datetime | None) -> float:
    if not published_at:
        return 0.6
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    days = max(0, (datetime.now(UTC) - published_at).days)
    return max(0.25, math.exp(-days / 120))


@dataclass(slots=True)
class RetrievalResult:
    evidence: list[EvidenceCitation]
    degraded: bool


class PostgresHybridIndex:
    def __init__(self, database: Database, embeddings: EmbeddingGateway) -> None:
        self.database = database
        self.embeddings = embeddings

    async def upsert(self, documents: list[KnowledgeDocument]) -> None:
        missing: list[KnowledgeDocument] = []
        async with self.database.session() as session:
            hashes = [item.content_hash for item in documents]
            existing = set(
                await session.scalars(
                    select(KnowledgeChunkRow.content_hash).where(KnowledgeChunkRow.content_hash.in_(hashes))
                )
            )
            missing = [item for item in documents if item.content_hash not in existing]
        if not missing:
            return
        vectors = await self.embeddings.embed_documents([item.content for item in missing])
        async with self.database.session() as session:
            for document, vector in zip(missing, vectors, strict=True):
                session.add(
                    KnowledgeChunkRow(
                        source_type=document.source_type,
                        source_path=document.source_path,
                        source_title=document.title,
                        content=document.content,
                        content_hash=document.content_hash,
                        published_at=document.published_at,
                        embedding=vector,
                    )
                )

    async def search(self, query: str, limit: int) -> list[tuple[KnowledgeDocument, float]]:
        query_vector = await self.embeddings.embed_query(query)
        distance = KnowledgeChunkRow.embedding.cosine_distance(query_vector)
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(KnowledgeChunkRow, distance.label("distance"))
                    .where(KnowledgeChunkRow.active.is_(True))
                    .order_by(distance)
                    .limit(limit * 3)
                )
            ).all()
        return [
            (
                KnowledgeDocument(
                    source_type=row.source_type,
                    source_path=row.source_path,
                    title=row.source_title,
                    content=row.content,
                    published_at=row.published_at,
                ),
                max(0.0, 1.0 - float(distance_value)),
            )
            for row, distance_value in rows
        ]


class HybridRagService:
    """local 使用 pgvector + 全文分，失败时用内存全文检索并明确降级。"""

    def __init__(
        self,
        source: KnowledgeSource,
        *,
        index: PostgresHybridIndex | None = None,
        limit: int = 8,
    ) -> None:
        self.source = source
        self.index = index
        self.limit = limit

    def _rerank(
        self,
        query: str,
        scored_documents: list[tuple[KnowledgeDocument, float]],
        mode: str,
    ) -> list[EvidenceCitation]:
        best: dict[str, EvidenceCitation] = {}
        for document, semantic in scored_documents:
            lexical = lexical_score(query, document.content)
            score = (
                0.5 * semantic
                + 0.25 * lexical
                + 0.15 * SOURCE_WEIGHT.get(document.source_type, 0.7)
                + 0.1 * _recency_score(document.published_at)
            )
            citation = EvidenceCitation(
                source_type=document.source_type,
                title=document.title,
                source_path=document.source_path,
                excerpt=document.content[:500],
                score=max(0, min(1, score)),
                published_at=document.published_at,
                retrieval_mode=mode,
            )
            current = best.get(document.source_path)
            if current is None or citation.score > current.score:
                best[document.source_path] = citation
        return sorted(best.values(), key=lambda item: item.score, reverse=True)[: self.limit]

    async def retrieve(self, query: str) -> RetrievalResult:
        documents = await self.source.load()
        if self.index is not None:
            try:
                await self.index.upsert(documents)
                semantic = await self.index.search(query, self.limit)
                # 把语义候选和全文候选合并后统一重排。
                lexical = sorted(
                    ((item, lexical_score(query, item.content)) for item in documents),
                    key=lambda pair: pair[1],
                    reverse=True,
                )[: self.limit]
                return RetrievalResult(
                    evidence=self._rerank(query, semantic + lexical, "hybrid"),
                    degraded=False,
                )
            except Exception as exc:
                logger.warning("rag.embedding_degraded", error_type=type(exc).__name__)
        lexical_only = sorted(
            ((item, lexical_score(query, item.content)) for item in documents),
            key=lambda pair: pair[1],
            reverse=True,
        )[: self.limit * 2]
        return RetrievalResult(evidence=self._rerank(query, lexical_only, "fulltext"), degraded=True)
