# app/ml/vertex_client.py — Async Vertex AI prediction client
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from google.cloud import aiplatform
from google.cloud.aiplatform.gapic import PredictionServiceAsyncClient
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

logger = logging.getLogger("nexgen.vertex_client")


class VertexAIClient:
    """
    Async thin wrapper around the Vertex AI Prediction Service.

    Designed to be initialized in a background task (see main.py lifespan)
    so the FastAPI server can serve /health before this client is ready.
    """

    def __init__(self, project_id: str, location: str, endpoint_id: str):
        self.project_id = project_id
        self.location = location
        self.endpoint_id = endpoint_id
        self._client: PredictionServiceAsyncClient | None = None
        self._endpoint_path: str = ""

    async def initialize(self) -> None:
        """
        Initialize the Vertex AI async client.
        This is called from the background task in lifespan — NOT in startup.
        """
        logger.info(
            f"Connecting to Vertex AI endpoint: {self.endpoint_id} "
            f"(project={self.project_id}, location={self.location})"
        )
        api_endpoint = f"{self.location}-aiplatform.googleapis.com"

        # Create async client
        self._client = PredictionServiceAsyncClient(
            client_options={"api_endpoint": api_endpoint}
        )

        self._endpoint_path = (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/endpoints/{self.endpoint_id}"
        )

        # Warm up: send a dummy request to pre-load the model on the serving node
        await self._warmup()
        logger.info("Vertex AI client initialized and warmed up")

    async def _warmup(self) -> None:
        """Send a zero-vector prediction to warm up the serving container."""
        try:
            dummy_features = [0.0] * 7
            await self.predict(dummy_features)
            logger.info("Vertex AI warmup prediction succeeded")
        except Exception as exc:
            # Warmup failure is non-fatal
            logger.warning(f"Vertex AI warmup prediction failed (non-fatal): {exc}")

    async def predict(self, feature_vector: list[float]) -> float:
        """
        Run a single prediction against the Vertex AI endpoint.

        Args:
            feature_vector: Numeric feature vector matching the XGBoost model schema:
                [temperature, humidity, lat, lon, speed_kmh, battery_pct,
                 hours_since_last_checkpoint]

        Returns:
            Anomaly score in [0.0, 1.0].
        """
        if self._client is None:
            raise RuntimeError("VertexAIClient not initialized — call initialize() first")

        # Build the prediction instance
        instance = json_format.ParseDict(
            {"values": feature_vector, "key_name": "instances"},
            Value(),
        )

        try:
            response = await self._client.predict(
                endpoint=self._endpoint_path,
                instances=[instance],
                timeout=10.0,
            )
            # XGBoost binary classifier returns probability in [0, 1]
            score = float(response.predictions[0])
            return max(0.0, min(1.0, score))  # Clamp to valid range
        except Exception as exc:
            logger.error(f"Vertex AI predict call failed: {exc}")
            raise

    async def predict_batch(self, feature_vectors: list[list[float]]) -> list[float]:
        """Run inference on multiple feature vectors in a single API call."""
        if self._client is None:
            raise RuntimeError("VertexAIClient not initialized")

        instances = [
            json_format.ParseDict({"values": fv, "key_name": "instances"}, Value())
            for fv in feature_vectors
        ]

        response = await self._client.predict(
            endpoint=self._endpoint_path,
            instances=instances,
            timeout=30.0,
        )
        return [max(0.0, min(1.0, float(p))) for p in response.predictions]

    async def close(self) -> None:
        """Gracefully close the gRPC channel."""
        if self._client:
            await self._client.transport.close()
            logger.info("Vertex AI client closed")
