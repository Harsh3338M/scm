# tests/test_anomaly.py — Anomaly detection router tests
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_vertex_client():
    """Mock VertexAIClient that returns a predictable anomaly score."""
    mock = AsyncMock()
    mock.predict = AsyncMock(return_value=0.9)  # High anomaly score
    mock.predict_batch = AsyncMock(return_value=[0.9, 0.1, 0.85])
    return mock


@pytest.fixture
def client_with_model(mock_vertex_client):
    """TestClient with a mock model ready."""
    from app.main import app, app_state
    app_state.model_ready = True
    app_state.vertex_client = mock_vertex_client
    app_state.startup_time = __import__("time").time()
    with TestClient(app) as c:
        yield c


VALID_FEATURE_PAYLOAD = {
    "features": {
        "device_id": "device-001",
        "shipment_id": "ship-abc-123",
        "temperature": 32.5,
        "humidity": 78.2,
        "lat": 28.6139,
        "lon": 77.2090,
        "speed_kmh": 0.0,
        "battery_pct": 45.0,
        "hours_since_last_checkpoint": 6.5,
    }
}


class TestDirectDetect:
    def test_direct_detect_high_anomaly_score(self, client_with_model):
        """Anomaly score >= threshold (0.75) flags as anomaly."""
        response = client_with_model.post("/anomaly/detect/direct", json=VALID_FEATURE_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["is_anomaly"] is True
        assert data["anomaly_score"] == pytest.approx(0.9, abs=0.01)
        assert data["device_id"] == "device-001"
        assert data["shipment_id"] == "ship-abc-123"

    def test_direct_detect_low_score_not_anomaly(self, client_with_model, mock_vertex_client):
        """Anomaly score < threshold (0.75) does NOT flag as anomaly."""
        mock_vertex_client.predict = AsyncMock(return_value=0.3)
        response = client_with_model.post("/anomaly/detect/direct", json=VALID_FEATURE_PAYLOAD)
        assert response.status_code == 200
        data = response.json()
        assert data["is_anomaly"] is False
        assert data["anomaly_score"] == pytest.approx(0.3, abs=0.01)

    def test_direct_detect_503_when_model_not_ready(self):
        """Returns 503 when Vertex AI model is not yet loaded."""
        from app.main import app, app_state
        app_state.model_ready = False
        with TestClient(app) as client:
            response = client.post("/anomaly/detect/direct", json=VALID_FEATURE_PAYLOAD)
        assert response.status_code == 503

    def test_direct_detect_missing_required_fields(self, client_with_model):
        """Returns 422 for missing required fields."""
        response = client_with_model.post(
            "/anomaly/detect/direct",
            json={"features": {"device_id": "d-001"}},  # Missing lat, lon
        )
        assert response.status_code == 422

    def test_threshold_boundary(self, client_with_model, mock_vertex_client):
        """Score exactly at threshold (0.75) is classified as anomaly."""
        mock_vertex_client.predict = AsyncMock(return_value=0.75)
        response = client_with_model.post("/anomaly/detect/direct", json=VALID_FEATURE_PAYLOAD)
        assert response.status_code == 200
        assert response.json()["is_anomaly"] is True
