# tests/test_health.py — Intelligence Engine health probe tests
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# We patch AppState before importing the app to control model_ready state
@pytest.fixture
def client_model_not_ready():
    """TestClient with model NOT ready (simulates startup)."""
    from app.main import app, app_state
    app_state.model_ready = False
    app_state.startup_time = __import__("time").time()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_model_ready():
    """TestClient with model READY."""
    from app.main import app, app_state
    app_state.model_ready = True
    app_state.startup_time = __import__("time").time()
    with TestClient(app) as c:
        yield c


class TestHealthProbe:
    """
    CRITICAL: /health must ALWAYS return 200 regardless of model state.
    This prevents the Vertex AI 40-second 503 timeout on Cloud Run startup.
    """

    def test_health_returns_200_when_model_not_ready(self, client_model_not_ready):
        """Health probe must return 200 BEFORE model is loaded."""
        response = client_model_not_ready.get("/health")
        assert response.status_code == 200, (
            "CRITICAL: /health returned non-200 while model was loading. "
            "This would cause Cloud Run to 503 during the 40s Vertex AI startup window."
        )
        data = response.json()
        assert data["status"] == "ok"
        assert data["model_ready"] is False

    def test_health_returns_200_when_model_ready(self, client_model_ready):
        """Health probe returns 200 AND model_ready=True after loading."""
        response = client_model_ready.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["model_ready"] is True

    def test_health_response_time_under_200ms(self, client_model_not_ready):
        """Health probe must respond within 200ms (Cloud Run requirement)."""
        import time
        start = time.monotonic()
        response = client_model_not_ready.get("/health")
        elapsed_ms = (time.monotonic() - start) * 1000
        assert response.status_code == 200
        assert elapsed_ms < 200, f"/health took {elapsed_ms:.1f}ms — must be < 200ms"

    def test_ready_returns_503_when_model_loading(self, client_model_not_ready):
        """/ready returns 503 while model is loading (correct Cloud Run behavior)."""
        response = client_model_not_ready.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "loading"

    def test_ready_returns_200_when_model_ready(self, client_model_ready):
        """/ready returns 200 when model is fully loaded."""
        response = client_model_ready.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_health_includes_uptime(self, client_model_ready):
        """Health response must include uptime_seconds field."""
        response = client_model_ready.get("/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
