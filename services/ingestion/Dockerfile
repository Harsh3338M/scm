FROM golang:1.22-alpine AS builder

WORKDIR /app

# Install dependencies
COPY go.mod go.sum ./
RUN go mod download

# Build binary
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s -X main.Version=$(git describe --tags --always --dirty 2>/dev/null || echo 'dev')" \
    -o /nexgen-ingestion \
    ./cmd/server

# ─────────────────────────────────────────────
# Production image (distroless for minimal attack surface)
# ─────────────────────────────────────────────
FROM gcr.io/distroless/static-debian12

COPY --from=builder /nexgen-ingestion /nexgen-ingestion

USER nonroot:nonroot

EXPOSE 8080

ENV GCP_PROJECT_ID="nexgen-scm-2026" \
    PUBSUB_TOPIC_ID="telemetry-raw" \
    PORT="8080" \
    LOG_FORMAT="json"

ENTRYPOINT ["/nexgen-ingestion"]
