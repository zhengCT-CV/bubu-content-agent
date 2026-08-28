from __future__ import annotations

from app.agents.base import AgentExecution, AgentTraceContext, SkillAgent
from app.domain.models import RetroReport


class RetroAgent(SkillAgent):
    skill_name = "performance-retro"

    async def analyze(
        self,
        payload: dict,
        *,
        version: str | None = None,
        trace_context: AgentTraceContext | None = None,
    ) -> AgentExecution[RetroReport]:
        return await self.run_schema(
            RetroReport, payload, version=version, trace_context=trace_context
        )
