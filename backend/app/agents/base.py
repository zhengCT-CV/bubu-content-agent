from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from app.domain.models import LlmTraceContext, SkillSnapshot
from app.integrations.llm import ModelGateway
from app.skills.registry import SkillPackage, SkillRegistry

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class AgentExecution(Generic[T]):
    id: str
    output: T
    skill: SkillSnapshot
    provider: str
    model_name: str
    input_hash: str
    latency_ms: int


@dataclass(frozen=True, slots=True)
class AgentTraceContext:
    project_id: str
    thread_id: str
    node_name: str


class SkillAgent:
    skill_name: str

    def __init__(self, gateway: ModelGateway, skills: SkillRegistry) -> None:
        self.gateway = gateway
        self.skills = skills

    def package(self, version: str | None = None) -> SkillPackage:
        return self.skills.load(self.skill_name, version)

    async def run_schema(
        self,
        schema: type[T],
        payload: dict,
        *,
        version: str | None = None,
        trace_context: AgentTraceContext | None = None,
    ) -> AgentExecution[T]:
        package = self.package(version)
        execution_id = str(uuid4())
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        input_hash = hashlib.sha256(serialized.encode()).hexdigest()
        system_prompt = (
            package.instructions
            + "\n\n# 当前版本模型 Prompt\n"
            + package.prompt
            + "\n\n# 当前版本确定性规则\n"
            + json.dumps(package.rules, ensure_ascii=False)
        )
        start = time.perf_counter()
        llm_trace_context = None
        if trace_context is not None:
            llm_trace_context = LlmTraceContext(
                skill_run_id=execution_id,
                project_id=trace_context.project_id,
                thread_id=trace_context.thread_id,
                node_name=trace_context.node_name,
                skill_name=package.name,
                skill_version=package.version,
                prompt_hash=package.prompt_hash,
            )
        output = await self.gateway.generate_structured(
            schema,
            system_prompt,
            payload,
            trace_context=llm_trace_context,
        )
        return AgentExecution(
            id=execution_id,
            output=output,
            skill=package.snapshot,
            provider=self.gateway.provider,
            model_name=self.gateway.model_name,
            input_hash=input_hash,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
