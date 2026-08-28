from __future__ import annotations

import pytest
from app.agents.strategy import StrategyAgent
from app.integrations.llm import DemoModelGateway
from app.skills.registry import SkillRegistry


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inspiration",
    [
        "总替同事收拾烂摊子",
        "回家后一句话也不想说",
        "三十岁还不敢辞职",
        "朋友越来越少",
        "不敢拒绝家人的安排",
        "努力却不想被看见",
        "习惯把情绪留到深夜",
        "收到前同事的婚礼邀请",
        "开始讨厌周末聚会",
        "第一次把工作消息设为免打扰",
    ],
)
async def test_ten_historical_style_topics_keep_schema(inspiration: str) -> None:
    execution = await StrategyAgent(DemoModelGateway(), SkillRegistry()).propose_topics(
        {"inspiration": inspiration, "target_audience": "公众号读者", "evidence": []}
    )
    assert len(execution.output.candidates) == 3
    assert len({item.narrative_mechanism for item in execution.output.candidates}) == 3
    assert all(item.duplicate_risk < 80 for item in execution.output.candidates)
