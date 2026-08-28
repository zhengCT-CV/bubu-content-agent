from __future__ import annotations

from app.agents.base import AgentExecution, AgentTraceContext, SkillAgent
from app.domain.models import Prediction
from app.integrations.llm import TopicCandidateList


class StrategyAgent(SkillAgent):
    skill_name = "topic-strategy"

    async def propose_topics(
        self,
        payload: dict,
        *,
        version: str | None = None,
        trace_context: AgentTraceContext | None = None,
    ) -> AgentExecution[TopicCandidateList]:
        return await self.run_schema(
            TopicCandidateList, payload, version=version, trace_context=trace_context
        )

    async def predict(
        self,
        payload: dict,
        *,
        version: str | None = None,
        trace_context: AgentTraceContext | None = None,
    ) -> AgentExecution[Prediction]:
        # 预测仍属于策略能力，复用冻结的选题策略版本。
        return await self.run_schema(
            Prediction, payload, version=version, trace_context=trace_context
        )
