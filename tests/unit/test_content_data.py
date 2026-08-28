from __future__ import annotations

from datetime import datetime

import pytest
from app.domain.content_data import ContentDataService
from openpyxl import load_workbook

from tests.helpers import build_wechat_fixture


@pytest.mark.asyncio
async def test_content_data_builds_overview_and_article_detail(tmp_path) -> None:
    workspace = build_wechat_fixture(tmp_path)
    workbook_path = workspace / "data" / "wechat_realtime_metrics.xlsx"
    workbook = load_workbook(workbook_path)
    workbook["文章"].append(
        [
            "article-1",
            "测试作品",
            datetime(2026, 8, 24, 21, 20),
            "https://example.com/article-1",
            "追踪中",
            10_000,
            1_200,
            datetime(2026, 8, 25, 10, 20),
            datetime(2026, 8, 24, 22, 20),
            None,
        ]
    )
    workbook["采样明细"].append(
        [
            "sample-1",
            "article-1",
            "测试作品",
            datetime(2026, 8, 24, 21, 20),
            datetime(2026, 8, 25, 10, 20),
            13,
            1_200,
            60,
            30,
            5,
            3,
            "{}",
        ]
    )
    workbook["里程碑"].append(["里程碑ID", "文章ID"])
    workbook["里程碑"].append(["article-1|13h", "article-1"])
    workbook["运行日志"].append(["运行ID", "开始时间", "结束时间", "状态", "发现文章数", "写入采样数"])
    workbook["运行日志"].append(
        ["run-1", datetime(2026, 8, 25, 10, 20), datetime(2026, 8, 25, 10, 21), "success", 1, 1]
    )
    workbook.save(workbook_path)
    (workspace / "data" / "wechat_article_details" / "2026-08-24_测试作品_demo.csv").write_text(
        ",测试作品,,,\n"
        ",,,,\n"
        ",数据概况,,,\n"
        ",数据指标,数值,,\n"
        ",阅读(人),1200,,\n"
        ",完读率,90%,,\n"
        ",,,,\n"
        ",性别分布,,,\n"
        ",性别,占比,,\n"
        ",女,60%,,\n"
        ",男,40%,,\n",
        encoding="utf-8-sig",
    )

    service = ContentDataService(workspace)
    overview = await service.overview()

    assert overview["summary"]["tracked_articles"] == 1
    assert overview["summary"]["total_reads"] == 1_200
    assert overview["summary"]["collector_success_rate"] == 1
    assert overview["articles"][0]["share_rate"] == 0.05
    assert overview["articles"][0]["has_details"] is True

    detail = await service.article_detail("article-1")
    assert detail is not None
    assert detail["curve"][0]["hours_since_publish"] == 13
    assert detail["exported_detail"]["overview"]["完读率"] == 0.9
    assert detail["exported_detail"]["gender"][0] == {"label": "女", "ratio": 0.6}

    cached = await service.overview()
    assert cached["source"]["cached"] is True
