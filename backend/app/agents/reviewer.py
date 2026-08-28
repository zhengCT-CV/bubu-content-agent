from __future__ import annotations

from app.agents.base import AgentExecution, AgentTraceContext, SkillAgent
from app.domain.models import ReviewResult


class ReviewerAgent(SkillAgent):
    skill_name = "content-review"

    async def review(
        self,
        artifact_type: str,
        artifact: dict,
        evidence: list[dict],
        *,
        context: dict | None = None,
        validation_issues: list[dict] | None = None,
        version: str | None = None,
        trace_context: AgentTraceContext | None = None,
    ) -> AgentExecution[ReviewResult]:
        return await self.run_schema(
            ReviewResult,
            {
                "artifact_type": artifact_type,
                "artifact": artifact,
                "evidence": evidence,
                "context": context or {},
                "validation_issues": validation_issues or [],
            },
            version=version,
            trace_context=trace_context,
        )
