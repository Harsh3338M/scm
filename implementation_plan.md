# NexGen Supply Chain Digital Twin — Implementation Plan

## Overview

A full-stack, event-driven anomaly detection and routing platform targeting the **Google Solution Challenge 2026**. The system ingests IoT/GPS telemetry from shipments, detects anomalies via a Vertex AI-backed intelligence engine, and surfaces real-time insights through a Next.js Control Tower and a Flutter mobile app for field operators.

---

## User Review Required

> [!IMPORTANT]
> **Google Cloud Project**: All GCP resources (Pub/Sub, AlloyDB, Cloud Run, Vertex AI, Cloud Armor, NGFW) require a real GCP project ID, region, and billing account. This plan scaffolds **all IaC (Terraform) and application code** locally. You will need to run `terraform apply` manually with valid credentials.

> [!IMPORTANT]
> **Snyk CLI**: The security-scanning step requires `snyk` to be installed globally (`npm install -g snyk`) and authenticated (`snyk auth`). The plan will scaffold the CI hook — actual scanning runs on your machine.

> [!WARNING]
> **Vertex AI SDK cold-start (40s timeout)**: The FastAPI lifespan fix is a critical deliverable. The implementation uses a `BackgroundTask` pattern to load the model asynchronously and return `200 OK` on `/health` immediately.

> [!WARNING]
> **Excalidraw / MCP Integration**: The architecture diagram will be generated as a static SVG/PNG asset using the `generate_image` tool, since no live Excalidraw MCP server is connected to this session.

---

## Open Questions

> [!IMPORTANT]
> 1. **GCP Project ID & Region** — What is your GCP project ID and preferred region (e.g., `us-central1`)? Needed to populate Terraform variables.
> 2. **AlloyDB cluster** — New cluster or existing? Primary region preference?
> 3. **Flutter target** — Android only (as stated), or should we also wire up iOS stubs?
> 4. **Gemini API Key** — Will you use Application Default Credentials (ADC) via `gcloud auth` or an explicit API key for the Dart SDK?
> 5. **Pub/Sub Push vs Pull** — The Go ingestion service is described as a *pull* subscriber (recommended). Should the FastAPI engine also pull directly, or receive via push HTTP webhook from Pub/Sub?

---

## Repository Structure

```
d:\scm\
├── .agents/
│   ├── rules/
│   │   └── WORKSPACE_RULES.md          # Tech stack constraints
│   └── skills/
│       └── deploy-vertex-xgboost/
│           └── SKILL.md                # Vertex AI deployment automation
├── infra/                              # Terraform IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── pubsub.tf
│   ├── alloydb.tf
│   ├── armor.tf
│   ├── ngfw.tf
│   └── vertex.tf
├── services/
│   ├── ingestion/                      # Go 1.22 — Pub/Sub ingestion
│   │   ├── cmd/server/main.go
│   │   ├── internal/
│   │   │   ├── handler/    (telemetry validator + DPI)
│   │   │   ├── pubsub/     (publisher + subscriber)
│   │   │   └── otel/       (OpenTelemetry setup)
│   │   ├── go.mod
│   │   └── Dockerfile
│   └── intelligence/                   # Python 3.11 — FastAPI
│       ├── app/
│       │   ├── main.py                 (lifespan + /health fix)
│       │   ├── routers/
│       │   │   ├── anomaly.py
│       │   │   └── whatif.py
│       │   ├── ml/
│       │   │   ├── vertex_client.py
│       │   │   └── training_pipeline.py (Dask + RAPIDS + XGBoost)
│       │   └── db/
│       │       └── alloydb.py
│       ├── tests/
│       ├── requirements.txt
│       └── Dockerfile
├── frontend/                           # Next.js 14 App Router
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    (Control Tower dashboard)
│   │   ├── api/
│   │   │   ├── shipments/route.ts
│   │   │   └── whatif/route.ts
│   │   └── components/
│   ├── tailwind.config.ts
│   └── package.json
├── mobile/                             # Flutter (Android)
│   ├── lib/
│   │   ├── main.dart
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── custody/               (QR/barcode scanning)
│   │   │   └── audit/                 (camera + Gemini vision)
│   │   ├── core/
│   │   │   ├── cache/                 (sqflite offline-first)
│   │   │   └── sync/                  (connectivity sync)
│   │   └── theme/
│   └── pubspec.yaml
└── README.md
```

---

## Proposed Changes

### Phase 0 — Workspace Rules & Agent Skills

#### [NEW] `.agents/rules/WORKSPACE_RULES.md`
Enforces: Next.js 14 + Tailwind v3, Go 1.22, AlloyDB PostgreSQL dialect, Python 3.11 + FastAPI, Snyk SAST gate.

#### [NEW] `.agents/skills/deploy-vertex-xgboost/SKILL.md`
Step-by-step skill for packaging an XGBoost model artifact, pushing to GCS, and deploying to a Vertex AI Endpoint via `gcloud ai endpoints deploy-model`.

---

### Phase 1 — Infrastructure (Terraform)

#### [NEW] `infra/main.tf` + `infra/variables.tf` + `infra/outputs.tf`
- Provider `google` + `google-beta`, project/region variables.

#### [NEW] `infra/pubsub.tf`
- Topic: `telemetry-raw`, `anomaly-events`
- Subscriptions: `ingestion-pull`, `intelligence-pull`
- Dead-letter topic: `telemetry-dlq`
- Message retention: 7 days, exactly-once delivery enabled.

#### [NEW] `infra/alloydb.tf`
- AlloyDB cluster (`scm-cluster`), primary instance (`scm-primary`)
- Columnar engine enabled on primary instance
- Private IP only (VPC peering)

#### [NEW] `infra/armor.tf`
- Cloud Armor security policy: rate-limit 1000 req/min per IP, OWASP CRS rules

#### [NEW] `infra/ngfw.tf`
- Cloud NGFW policy with L7 inspection on internal VPC traffic

#### [NEW] `infra/vertex.tf`
- Vertex AI Endpoint resource for XGBoost model

---

### Phase 2 — Go Ingestion Service

#### [NEW] `services/ingestion/cmd/server/main.go`
- HTTP server wiring + graceful shutdown

#### [NEW] `services/ingestion/internal/handler/telemetry.go`
- **Deep Packet Inspection**: validates IoT/GPS JSON schema (required fields: `device_id`, `lat`, `lon`, `timestamp`, `temperature`, `humidity`)
- Rejects malformed payloads with `400`

#### [NEW] `services/ingestion/internal/pubsub/publisher.go`
- Publishes validated messages to `telemetry-raw` topic
- Embeds OpenTelemetry trace context as Pub/Sub message attributes

#### [NEW] `services/ingestion/internal/otel/setup.go`
- Configures OTLP trace exporter to Google Cloud Trace

#### [NEW] `services/ingestion/go.mod`
- `google.golang.org/api`, `cloud.google.com/go/pubsub`, `go.opentelemetry.io/otel`

---

### Phase 3 — Python Intelligence Engine (FastAPI)

#### [NEW] `services/intelligence/app/main.py`
- **Critical lifespan fix**: `startup` event returns immediately; Vertex AI model loading fires as a `asyncio` background task.
- `/health` → always `200 OK` within milliseconds.

#### [NEW] `services/intelligence/app/routers/anomaly.py`
- `POST /anomaly/detect` — pulls from Pub/Sub, runs XGBoost inference via Vertex AI endpoint, publishes to `anomaly-events`.

#### [NEW] `services/intelligence/app/routers/whatif.py`
- `POST /whatif/simulate` — runs scenario simulation queries against AlloyDB columnar engine.

#### [NEW] `services/intelligence/app/ml/training_pipeline.py`
- Dask + NVIDIA RAPIDS + XGBoost pipeline reading from BigQuery.

#### [NEW] `services/intelligence/app/ml/vertex_client.py`
- Thin async wrapper around `google-cloud-aiplatform` for online prediction.

---

### Phase 4 — Next.js 14 Control Tower

#### [NEW] `frontend/app/page.tsx`
- Real-time shipment map (using `react-leaflet`)
- Live anomaly feed, What-If simulation panel
- Polls `GET /api/shipments` every 5s (SWR)

#### [NEW] `frontend/app/api/shipments/route.ts`
- Server-side Route Handler querying AlloyDB via `pg` driver

#### [NEW] `frontend/app/api/whatif/route.ts`
- Proxies to FastAPI `/whatif/simulate`

#### [NEW] `frontend/tailwind.config.ts`
- Dark mode, custom supply-chain color palette

---

### Phase 5 — Flutter Mobile App

#### [NEW] `mobile/lib/main.dart`
- App entry, MaterialApp with custom dark theme, GoRouter

#### [NEW] `mobile/lib/features/auth/`
- Firebase Auth / Google Sign-In flow

#### [NEW] `mobile/lib/features/custody/`
- `mobile_scanner` for QR/barcode scanning
- Custody transfer POST to FastAPI

#### [NEW] `mobile/lib/features/audit/`
- Camera capture → `google_generative_ai` Dart SDK → Gemini Flash vision analysis of cargo seals

#### [NEW] `mobile/lib/core/cache/`
- `sqflite` schema for offline GPS telemetry queue

#### [NEW] `mobile/lib/core/sync/`
- `connectivity_plus` listener → batch sync to FastAPI on reconnect

---

## Verification Plan

### Automated Tests
```bash
# Go unit tests
cd services/ingestion && go test ./...

# Python unit tests
cd services/intelligence && pytest tests/ -v --cov=app

# Next.js type check
cd frontend && npx tsc --noEmit

# Flutter tests
cd mobile && flutter test
```

### Security Gate
```bash
# Snyk SAST (requires snyk auth)
snyk code test services/ingestion/
snyk code test services/intelligence/
snyk test frontend/
```

### Manual Verification
1. Start ingestion service locally, POST a telemetry payload, verify Pub/Sub message appears.
2. Start FastAPI service, hit `/health` — should return `200` in < 100ms.
3. Run Next.js dev server, verify dashboard loads with mock AlloyDB data.
4. Build Flutter APK (`flutter build apk`), install on Android emulator, complete auth flow.
