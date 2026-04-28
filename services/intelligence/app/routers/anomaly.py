# app/routers/anomaly.py — Anomaly detection router
from __future__ import annotations

import json
import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from google.cloud import pubsub_v1
from pydantic import BaseModel, Field

logger = logging.getLogger("nexgen.anomaly")

router = APIRouter()

# Pub/Sub clients (initialized once at module level)
_subscriber: pubsub_v1.SubscriberClient | None = None
_publisher: pubsub_v1.PublisherClient | None = None

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "nexgen-scm-2026")
PULL_SUBSCRIPTION = os.getenv("PUBSUB_INTELLIGENCE_SUB", "intelligence-pull")
ANOMALY_TOPIC = os.getenv("PUBSUB_ANOMALY_TOPIC", "anomaly-events")
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.75"))
MAX_MESSAGES = int(os.getenv("PUBSUB_MAX_MESSAGES", "50"))


def _get_subscriber() -> pubsub_v1.SubscriberClient:
    global _subscriber
    if _subscriber is None:
        _subscriber = pubsub_v1.SubscriberClient()
    return _subscriber


def _get_publisher() -> pubsub_v1.PublisherClient:
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


# ─────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────

class TelemetryFeatures(BaseModel):
    """Feature vector expected by the XGBoost model."""
    device_id: str
    shipment_id: str
    temperature: float | None = None
    humidity: float | None = None
    lat: float
    lon: float
    speed_kmh: float | None = None
    battery_pct: float | None = None
    hours_since_last_checkpoint: float | None = None


class AnomalyResult(BaseModel):
    device_id: str
    shipment_id: str
    anomaly_score: float
    is_anomaly: bool
    threshold: float
    message_id: str | None = None


class BatchDetectRequest(BaseModel):
    """Pull from Pub/Sub and run inference on up to max_messages messages."""
    max_messages: int = Field(default=50, ge=1, le=200)


class DirectDetectRequest(BaseModel):
    """Run inference directly on provided feature vector (for testing/mobile)."""
    features: TelemetryFeatures


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@router.post(
    "/detect/batch",
    response_model=list[AnomalyResult],
    summary="Pull from Pub/Sub and run anomaly detection",
)
async def detect_batch(request: Request, body: BatchDetectRequest) -> list[AnomalyResult]:
    """
    Pulls up to `max_messages` telemetry messages from the Pub/Sub pull
    subscription, runs XGBoost inference via Vertex AI, acks the messages,
    and publishes anomalies to the anomaly-events topic.
    """
    app_state = request.state.app_state
    if not app_state.model_ready:
        raise HTTPException(
            status_code=503,
            detail="Vertex AI model is still loading. Retry in a few seconds.",
        )

    subscriber = _get_subscriber()
    publisher = _get_publisher()
    subscription_path = subscriber.subscription_path(PROJECT_ID, PULL_SUBSCRIPTION)
    topic_path = publisher.topic_path(PROJECT_ID, ANOMALY_TOPIC)

    # Pull messages
    try:
        response = subscriber.pull(
            request={"subscription": subscription_path, "max_messages": body.max_messages},
            timeout=10.0,
        )
    except Exception as exc:
        logger.error(f"Pub/Sub pull failed: {exc}")
        raise HTTPException(status_code=502, detail=f"Failed to pull from Pub/Sub: {exc}")

    if not response.received_messages:
        return []

    results: list[AnomalyResult] = []
    ack_ids: list[str] = []

    for received_msg in response.received_messages:
        ack_ids.append(received_msg.ack_id)
        try:
            payload = json.loads(received_msg.message.data.decode("utf-8"))
            features = TelemetryFeatures(**payload)
        except Exception as exc:
            logger.warning(f"Skipping malformed message: {exc}")
            continue

        # Run inference
        feature_vector = _build_feature_vector(features)
        try:
            score = await app_state.vertex_client.predict(feature_vector)
        except Exception as exc:
            logger.error(f"Vertex AI prediction failed for device {features.device_id}: {exc}")
            score = 0.0  # Degrade gracefully

        is_anomaly = score >= ANOMALY_THRESHOLD
        result = AnomalyResult(
            device_id=features.device_id,
            shipment_id=features.shipment_id,
            anomaly_score=score,
            is_anomaly=is_anomaly,
            threshold=ANOMALY_THRESHOLD,
            message_id=received_msg.message.message_id,
        )
        results.append(result)

        # Publish anomaly events for high-score predictions
        if is_anomaly:
            try:
                anomaly_payload = result.model_dump_json().encode("utf-8")
                publisher.publish(
                    topic_path,
                    data=anomaly_payload,
                    device_id=features.device_id,
                    shipment_id=features.shipment_id,
                    anomaly_score=str(score),
                )
                logger.warning(
                    f"🚨 Anomaly detected: device={features.device_id} "
                    f"shipment={features.shipment_id} score={score:.3f}"
                )
            except Exception as exc:
                logger.error(f"Failed to publish anomaly event: {exc}")

    # Acknowledge all processed messages
    if ack_ids:
        subscriber.acknowledge(
            request={"subscription": subscription_path, "ack_ids": ack_ids}
        )

    return results


@router.post(
    "/detect/direct",
    response_model=AnomalyResult,
    summary="Run anomaly detection on a single feature vector",
)
async def detect_direct(request: Request, body: DirectDetectRequest) -> AnomalyResult:
    """
    Synchronous inference endpoint for mobile app and testing.
    Does NOT interact with Pub/Sub.
    """
    app_state = request.state.app_state
    if not app_state.model_ready:
        raise HTTPException(status_code=503, detail="Model not ready. Retry shortly.")

    feature_vector = _build_feature_vector(body.features)
    try:
        score = await app_state.vertex_client.predict(feature_vector)
    except Exception as exc:
        logger.error(f"Prediction error: {exc}")
        raise HTTPException(status_code=502, detail=f"Vertex AI prediction failed: {exc}")

    return AnomalyResult(
        device_id=body.features.device_id,
        shipment_id=body.features.shipment_id,
        anomaly_score=score,
        is_anomaly=score >= ANOMALY_THRESHOLD,
        threshold=ANOMALY_THRESHOLD,
    )


def _build_feature_vector(features: TelemetryFeatures) -> list[float]:
    """Converts TelemetryFeatures to the numeric vector expected by XGBoost."""
    return [
        features.temperature or 0.0,
        features.humidity or 0.0,
        features.lat,
        features.lon,
        features.speed_kmh or 0.0,
        features.battery_pct or 100.0,
        features.hours_since_last_checkpoint or 0.0,
    ]
