from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import Settings
from app.domain.errors import ExternalServiceError
from app.integrations.retry import external_retry

DASHSCOPE_MAX_BATCH_SIZE = 10
DASHSCOPE_MAX_CONCURRENCY = 3


def _dashscope_http_error(response: httpx.Response) -> dict[str, Any]:
    """提取可诊断但不包含密钥或请求正文的 DashScope 错误。"""

    try:
        error = response.json().get("error", {})
    except (ValueError, AttributeError):
        error = {}
    return {
        "status_code": response.status_code,
        "code": error.get("code"),
        "param": error.get("param"),
        "message": str(error.get("message") or "")[:500],
    }


class EmbeddingGateway(ABC):
    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]


class DashScopeEmbeddingGateway(EmbeddingGateway):
    """调用 DashScope 的 OpenAI 兼容 Embeddings API。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.dashscope_api_key:
            raise ExternalServiceError("local 模式缺少 DASHSCOPE_API_KEY")
        self.model = settings.dashscope_embedding_model
        self._client = httpx.AsyncClient(
            base_url=settings.dashscope_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
            timeout=30,
        )

    @external_retry
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """发送一个合法批次；重试只重发失败批次，避免重复计费其他成功批次。"""

        try:
            response = await self._client.post("/embeddings", json={"model": self.model, "input": texts})
            response.raise_for_status()
            items = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in items]
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(
                "DashScope Embedding 调用失败",
                detail=_dashscope_http_error(exc.response),
            ) from exc
        except Exception as exc:
            raise ExternalServiceError(
                "DashScope Embedding 调用失败", detail={"type": type(exc).__name__}
            ) from exc
        if len(vectors) != len(texts):
            raise ExternalServiceError(
                "DashScope Embedding 返回数量不一致",
                detail={"expected": len(texts), "actual": len(vectors)},
            )
        return vectors

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """按 DashScope 的最多 10 条限制分批，并保持最终向量与输入顺序一致。"""

        if not texts:
            return []
        batches = [texts[start : start + DASHSCOPE_MAX_BATCH_SIZE] for start in range(0, len(texts), 10)]
        semaphore = asyncio.Semaphore(DASHSCOPE_MAX_CONCURRENCY)

        async def run_batch(index: int, batch: list[str]) -> tuple[int, list[list[float]]]:
            async with semaphore:
                return index, await self._embed_batch(batch)

        completed = await asyncio.gather(
            *(run_batch(index, batch) for index, batch in enumerate(batches))
        )
        ordered = sorted(completed, key=lambda item: item[0])
        return [vector for _, vectors in ordered for vector in vectors]

    async def close(self) -> None:
        await self._client.aclose()


class DisabledEmbeddingGateway(EmbeddingGateway):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise ExternalServiceError("Embedding 在 demo 模式关闭，将使用全文检索")


def build_embedding_gateway(settings: Settings) -> EmbeddingGateway:
    if settings.app_mode == "demo":
        return DisabledEmbeddingGateway()
    return DashScopeEmbeddingGateway(settings)
