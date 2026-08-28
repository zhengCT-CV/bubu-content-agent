from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.config import Settings
from app.domain.models import LlmTraceContext, ProjectCreate, TopicCandidate
from app.integrations.embeddings import DashScopeEmbeddingGateway
from app.integrations.llm import DeepSeekGateway, DemoModelGateway, TopicCandidateList
from app.repositories.memory import InMemoryProjectRepository


@pytest.mark.asyncio
async def test_dashscope_embeddings_split_batches_and_preserve_order() -> None:
    request_batches: list[list[str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        texts = payload["input"]
        request_batches.append(texts)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [float(text.removeprefix("text-"))]}
                    for index, text in enumerate(texts)
                ]
            },
        )

    gateway = DashScopeEmbeddingGateway(
        Settings(app_mode="local", dashscope_api_key="test-key")
    )
    await gateway._client.aclose()
    gateway._client = httpx.AsyncClient(
        base_url="https://dashscope.test/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        vectors = await gateway.embed_documents([f"text-{index}" for index in range(23)])
    finally:
        await gateway.close()

    assert sorted(map(len, request_batches)) == [3, 10, 10]
    assert [vector[0] for vector in vectors] == list(map(float, range(23)))


@dataclass
class FakeRawMessage:
    content: str


class FakeStructuredRunnable:
    def __init__(self) -> None:
        self.messages: list[list[tuple[str, str]]] = []

    async def ainvoke(self, messages: list[tuple[str, str]]) -> dict[str, Any]:
        self.messages.append(list(messages))
        if len(self.messages) == 1:
            return {
                "raw": FakeRawMessage('{"candidates":[{"conflict":"字段名错误"}]}'),
                "parsed": None,
                "parsing_error": ValueError("core_conflict field required"),
            }
        candidate = TopicCandidate(
            title="一个符合结构的候选选题",
            core_conflict="外部期待与真实感受之间的冲突",
            narrative_mechanism="认知反转",
            audience_value="帮助读者识别情绪来源",
            hook="他第七次删掉了同一句话。",
            predicted_strength=80,
            duplicate_risk=20,
        )
        return {
            "raw": FakeRawMessage("{}"),
            "parsed": TopicCandidateList(candidates=[candidate]),
            "parsing_error": None,
        }


class FakeDeepSeekClient:
    def __init__(self, runnable: FakeStructuredRunnable) -> None:
        self.runnable = runnable

    def with_structured_output(self, schema: type, **kwargs: Any) -> FakeStructuredRunnable:
        assert schema is TopicCandidateList
        assert kwargs == {"method": "json_mode", "include_raw": True}
        return self.runnable


@pytest.mark.asyncio
async def test_deepseek_injects_schema_and_repairs_invalid_output() -> None:
    runnable = FakeStructuredRunnable()
    gateway = object.__new__(DeepSeekGateway)
    gateway.model_name = "deepseek-chat"
    gateway._client = FakeDeepSeekClient(runnable)

    result = await gateway.generate_structured(
        TopicCandidateList,
        "生成三个候选",
        {"inspiration": "内耗"},
    )

    assert result.candidates[0].core_conflict == "外部期待与真实感受之间的冲突"
    assert '"core_conflict"' in runnable.messages[0][0][1]
    assert "上一次输出未通过 JSON Schema 校验" in runnable.messages[1][-1][1]
    assert "core_conflict field required" in runnable.messages[1][-1][1]


@pytest.mark.asyncio
async def test_llm_trace_redacts_secrets_from_payload_and_message_text() -> None:
    repository = InMemoryProjectRepository()
    project = await repository.create_project(ProjectCreate(name="脱敏测试", inspiration="测试灵感"))
    context = LlmTraceContext(
        skill_run_id=str(uuid4()),
        project_id=project.id,
        thread_id="trace-thread",
        node_name="generate_topics",
        skill_name="topic-strategy",
        skill_version="1.0.0",
        prompt_hash="a" * 64,
    )
    await DemoModelGateway(repository).generate_structured(
        TopicCandidateList,
        "生成三个候选",
        {"inspiration": "内耗", "api_key": "never-store-this-secret"},
        trace_context=context,
    )

    trace = (await repository.list_llm_traces("trace-thread"))[0]
    serialized = json.dumps(trace.model_dump(mode="json"), ensure_ascii=False)
    assert "never-store-this-secret" not in serialized
    assert "***REDACTED***" in serialized
