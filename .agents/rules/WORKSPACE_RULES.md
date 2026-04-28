# NexGen SCM Digital Twin — Workspace Rules

These rules are enforced for all agents and contributors working in this repository.
Any code that violates these constraints MUST be rejected before merge.

---

## 1. Frontend Control Tower

| Constraint | Value |
|---|---|
| Framework | **Next.js 14** — App Router ONLY (no Pages Router) |
| Styling | **Tailwind CSS v3** — no inline styles, no CSS Modules unless for micro-animations |
| State | SWR for data fetching; Zustand for global UI state |
| Language | TypeScript 5+ (strict mode enabled) |
| Node.js | ≥ 20 LTS |

## 2. Backend Ingestion Service

| Constraint | Value |
|---|---|
| Language | **Go 1.22** |
| Messaging | `cloud.google.com/go/pubsub` v1 |
| Observability | OpenTelemetry SDK (`go.opentelemetry.io/otel`) — OTLP export to Cloud Trace |
| Security | All inbound payloads MUST pass deep packet inspection in `internal/handler` |
| Database driver | `github.com/jackc/pgx/v5` (AlloyDB PostgreSQL dialect) |

## 3. Persistence Layer

| Constraint | Value |
|---|---|
| Database | **AlloyDB for PostgreSQL** — use PostgreSQL dialect ONLY |
| Connection | Private IP via VPC peering; never expose public IP |
| Query engine | Columnar engine MUST be enabled for analytical/What-If queries |
| ORM | Raw SQL via `pgx` (Go) and `asyncpg` (Python); no ORMs |

## 4. Intelligence Engine

| Constraint | Value |
|---|---|
| Language | **Python 3.11** |
| Framework | **FastAPI** (ASGI, lifespan context manager) |
| ML | XGBoost via Vertex AI Endpoint; training via Dask + NVIDIA RAPIDS |
| Deployment | Google Cloud Run (containerized) |
| Health probe | `/health` MUST return `200 OK` in < 200ms — model loading is async background task |

## 5. Security Protocol (Non-Negotiable)

- **Snyk SAST** must be run before every commit: `snyk code test <service-dir>`
- **Cloud Armor** is the perimeter; no service is exposed without it
- **Cloud NGFW** inspects all internal VPC east-west traffic
- Secrets MUST use **Google Secret Manager** — never committed to git
- All Docker images must be scanned: `snyk container test <image>`

## 6. Mobile Application

| Constraint | Value |
|---|---|
| Framework | **Flutter** (stable channel) |
| Target | Android (primary); iOS stubs allowed |
| AI | Gemini Flash via FastAPI proxy — no raw API keys in client |
| Offline | `sqflite` for GPS telemetry queue; sync on connectivity restore |
| Camera | `camera` + `google_ml_kit` for barcode scanning |
