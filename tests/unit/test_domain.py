from __future__ import annotations

from datetime import UTC

import pytest
from app.domain.models import Storyboard, StoryboardPanel
from pydantic import ValidationError


def panel(index: int) -> StoryboardPanel:
    return StoryboardPanel(
        index=index,
        purpose="beat",
        scene="office",
        action="wait",
        emotion="nervous",
        camera="medium",
        time_of_day="night",
    )


def test_storyboard_requires_six_to_ten_sequential_panels() -> None:
    with pytest.raises(ValidationError):
        Storyboard(
            title="测试标题",
            summary="摘要",
            interaction_question="你会怎么做？",
            characters=[],
            cover_brief="封面",
            panels=[panel(index) for index in range(1, 6)],
            ending="结尾",
        )


def test_metrics_share_rate_handles_zero_reads() -> None:
    from datetime import datetime

    from app.domain.models import MetricsSnapshot

    metrics = MetricsSnapshot(
        article_id="x",
        captured_at=datetime.now(UTC),
        hours_since_publish=24,
        reads=0,
        shares=2,
        likes=0,
        favorites=0,
        new_followers=0,
    )
    assert metrics.share_rate == 0
