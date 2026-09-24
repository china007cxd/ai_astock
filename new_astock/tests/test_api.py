# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient

from app.main import app


def test_health_and_settings() -> None:
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True
        settings = client.get("/api/v1/settings")
        assert settings.status_code == 200
        assert "ui.theme" in settings.json()["data"]


def test_invalid_stock_code_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/stocks/not-a-code")
        assert response.status_code == 400
