from __future__ import annotations

from app.agents.base import AgentExecution, AgentTraceContext, SkillAgent
from app.domain.models import Storyboard


class StoryboardAgent(SkillAgent):
    skill_name = "storyboard-design"

    async def design(
        self,
        payload: dict,
        *,
        version: str | None = None,
        trace_context: AgentTraceContext | None = None,
    ) -> AgentExecution[Storyboard]:
        return await self.run_schema(
            Storyboard, payload, version=version, trace_context=trace_context
        )
