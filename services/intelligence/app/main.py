# app/main.py — FastAPI Intelligence Engine
# CRITICAL: Lifespan context returns 200 immediately; Vertex AI loads in background.

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import anomaly, whatif
from app.ml.vertex_client import VertexAIClient

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("nexgen.intelligence")

# ─────────────────────────────────────────────
# Application State (shared across request handlers)
# ─────────────────────────────────────────────
class AppState:
    vertex_client: VertexAIClient | None = None
    model_ready: bool = False
    startup_time: float = 0.0

app_state = AppState()


async def _load_vertex_model_background() -> None:
    """
    Background coroutine that loads the Vertex AI model.

    CRITICAL DESIGN: This runs AFTER the server is already serving requests.
    /health returns 200 OK immediately, preventing the 40-second Vertex AI
    503 timeout failure during Cloud Run startup health checks.
    """
    logger.info("Background: Starting Vertex AI model load...")
    start = time.monotonic()
    try:
        client = VertexAIClient(
            project_id=os.getenv("GCP_PROJECT_ID", "nexgen-scm-2026"),
            location=os.getenv("VERTEX_LOCATION", "us-central1"),
            endpoint_id=os.getenv("VERTEX_ENDPOINT_ID", "nexgen-scm-endpoint"),
        )
        await client.initialize()
        app_state.vertex_client = client
        app_state.model_ready = True
        elapsed = time.monotonic() - start
        logger.info(f"Background: Vertex AI client ready in {elapsed:.2f}s")
    except Exception as exc:
        logger.error(f"Background: Failed to initialize Vertex AI client: {exc}", exc_info=True)
        # Don't crash — service degrades gracefully; anomaly detection returns 503
        # until model is available, but health probe stays green.


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ASGI lifespan context manager.

    Startup:
      1. Records startup time (< 1ms).
      2. Fires model loading as a background task (non-blocking).
      3. Yields immediately — server is NOW serving requests including /health.

    Shutdown:
      - Graceful cleanup of Vertex AI connections.
    """
    app_state.startup_time = time.time()
    logger.info("NexGen Intelligence Engine: startup initiated")

    # Fire model loading in background — does NOT block server startup
    asyncio.create_task(_load_vertex_model_background())

    logger.info("NexGen Intelligence Engine: server ready (model loading in background)")
    yield  # <-- server begins serving HERE, before model is loaded

    # Shutdown
    logger.info("NexGen Intelligence Engine: shutting down")
    if app_state.vertex_client:
        await app_state.vertex_client.close()


# ─────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────
app = FastAPI(
    title="NexGen Intelligence Engine",
    description="Anomaly detection and What-If simulation for the SCM Digital Twin",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — restrict to Control Tower and mobile API gateway in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Health & Readiness Probes
# ─────────────────────────────────────────────

@app.get(
    "/health",
    summary="Liveness probe",
    tags=["observability"],
    response_description="Always 200 OK — service is alive",
)
async def health() -> dict[str, Any]:
    """
    Liveness probe for Cloud Run.

    ALWAYS returns 200 OK immediately, even before the Vertex AI model
    has finished loading. This prevents the 40-second startup timeout.
    """
    return {
        "status": "ok",
        "service": "nexgen-intelligence",
        "model_ready": app_state.model_ready,
        "uptime_seconds": round(time.time() - app_state.startup_time, 2),
    }


@app.get(
    "/ready",
    summary="Readiness probe",
    tags=["observability"],
)
async def ready(response: Response) -> dict[str, Any]:
    """
    Readiness probe — returns 503 until the Vertex AI model is loaded.
    Cloud Run will stop sending traffic until this returns 200.
    """
    if app_state.model_ready:
        return {"status": "ready", "model_ready": True}

    response.status_code = 503
    return {
        "status": "loading",
        "model_ready": False,
        "message": "Vertex AI model is loading in background",
    }


# ─────────────────────────────────────────────
# Request Timing Middleware
# ─────────────────────────────────────────────

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


# ─────────────────────────────────────────────
# Inject app_state into request state (for routers)
# ─────────────────────────────────────────────

@app.middleware("http")
async def inject_app_state(request: Request, call_next):
    request.state.app_state = app_state
    return await call_next(request)


# ─────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────
app.include_router(anomaly.router, prefix="/anomaly", tags=["anomaly-detection"])
app.include_router(whatif.router, prefix="/whatif", tags=["what-if-simulation"])


# ─────────────────────────────────────────────
# Root
# ─────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return {"service": "nexgen-intelligence", "version": "1.0.0", "docs": "/docs"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        log_level="info",
        workers=1,  # Single worker for async; scale via Cloud Run instances
    )
