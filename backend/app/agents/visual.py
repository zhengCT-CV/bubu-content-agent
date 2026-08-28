from __future__ import annotations

from app.agents.base import AgentExecution, AgentTraceContext, SkillAgent
from app.domain.models import VisualPromptPackage


class VisualAgent(SkillAgent):
    skill_name = "visual-prompt"

    async def build_prompts(
        self,
        payload: dict,
        *,
        version: str | None = None,
        trace_context: AgentTraceContext | None = None,
    ) -> AgentExecution[VisualPromptPackage]:
        return await self.run_schema(
            VisualPromptPackage, payload, version=version, trace_context=trace_context
        )
