FROM python:3.11-slim AS base

# Security: run as non-root
RUN groupadd --gid 1001 nexgen && \
    useradd --uid 1001 --gid nexgen --shell /bin/bash --create-home nexgen

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────
# Dependencies layer (cached separately)
# ─────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────
# Application layer
# ─────────────────────────────────────────────
FROM deps AS app

COPY --chown=nexgen:nexgen . .

USER nexgen

ENV GCP_PROJECT_ID="nexgen-scm-2026" \
    VERTEX_LOCATION="us-central1" \
    VERTEX_ENDPOINT_ID="nexgen-scm-endpoint" \
    PUBSUB_INTELLIGENCE_SUB="intelligence-pull" \
    PUBSUB_ANOMALY_TOPIC="anomaly-events" \
    PORT="8080" \
    WORKERS="1"

EXPOSE 8080

# Health check: /health must respond in < 5s
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1", \
     "--log-level", "info"]
