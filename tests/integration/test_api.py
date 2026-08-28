from __future__ import annotations

import time

from app.main import app
from fastapi.testclient import TestClient


def test_health_and_project_creation() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["mode"] == "demo"
        created = client.post(
            "/api/projects",
            json={
                "name": "API 测试",
                "inspiration": "一个真实灵感",
                "target_audience": "测试读者",
            },
        )
        assert created.status_code == 201
        assert client.get("/api/projects").json()[0]["id"] == created.json()["id"]
        started = client.post(f"/api/projects/{created.json()['id']}/runs")
        assert started.status_code == 202
        thread_id = started.json()["thread_id"]
        traces = []
        for _ in range(100):
            response = client.get(f"/api/runs/{thread_id}/llm-traces")
            assert response.status_code == 200
            traces = response.json()
            if traces:
                break
            time.sleep(0.02)
        assert traces
        detail = client.get(f"/api/runs/{thread_id}/llm-traces/{traces[0]['id']}")
        assert detail.status_code == 200
        assert detail.json()["messages"][0]["role"] == "system"
        assert detail.json()["input_payload"]
