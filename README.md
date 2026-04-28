# NexGen Supply Chain Digital Twin
**Google Solution Challenge 2026**

A production-grade, event-driven anomaly detection and intelligent routing platform for supply chain operations.

![Architecture](https://img.shields.io/badge/Architecture-Google%20Cloud-4285F4?style=flat&logo=google-cloud)
![Go](https://img.shields.io/badge/Ingestion-Go%201.22-00ADD8?style=flat&logo=go)
![Python](https://img.shields.io/badge/Intelligence-Python%203.11-3776AB?style=flat&logo=python)
![Next.js](https://img.shields.io/badge/Control%20Tower-Next.js%2014-000000?style=flat&logo=next.js)
![Flutter](https://img.shields.io/badge/Mobile-Flutter-02569B?style=flat&logo=flutter)

---

## Architecture

```
Field Layer        Ingestion Layer      Persistence        Intelligence       Control Tower
─────────────      ───────────────      ───────────        ────────────       ─────────────
Flutter App   →→  Go 1.22 Service  →→  AlloyDB       →→  FastAPI + Vertex   Next.js 14
IoT Sensors        Pub/Sub Topics       (Columnar)         XGBoost Model      Real-time Map
                   Cloud Armor                             Cloud Run          What-If Sim
                   Cloud NGFW
                   OTel Tracing
```

## Monorepo Structure

```
scm/
├── .agents/
│   ├── rules/WORKSPACE_RULES.md       # Technology constraints
│   └── skills/deploy-vertex-xgboost/  # Vertex AI deployment automation
├── infra/                             # Terraform IaC (GCP)
├── services/
│   ├── ingestion/                     # Go 1.22 — Pub/Sub + DPI + OTel
│   └── intelligence/                  # Python 3.11 — FastAPI + Vertex AI
├── frontend/                          # Next.js 14 Control Tower
└── mobile/                            # Flutter Android App
```

## Quick Start

### Prerequisites
- Go 1.22+, Python 3.11+, Node.js 20+, Flutter 3.19+
- `gcloud` CLI authenticated with a GCP project
- Terraform >= 1.7.0
- Snyk CLI: `npm install -g snyk && snyk auth`

### 1. Provision Infrastructure
```bash
cd infra
terraform init
terraform plan -var="project_id=YOUR_PROJECT_ID"
terraform apply
```

### 2. Run Ingestion Service (Go)
```bash
cd services/ingestion
export GCP_PROJECT_ID=your-project-id
export PUBSUB_TOPIC_ID=telemetry-raw
go run ./cmd/server

# Test with curl
curl -X POST http://localhost:8080/ingest/telemetry \
  -H "Content-Type: application/json" \
  -d '{"device_id":"dev-001","shipment_id":"shp-123","timestamp":"2026-04-28T12:00:00Z","lat":28.61,"lon":77.20}'
```

### 3. Run Intelligence Engine (Python)
```bash
cd services/intelligence
pip install -r requirements.txt
export GCP_PROJECT_ID=your-project-id
export ALLOYDB_DSN=postgresql://scm_app:password@/scm_db?host=/path/to/socket

uvicorn app.main:app --host 0.0.0.0 --port 8080

# Health check (always 200)
curl http://localhost:8080/health
```

### 4. Run Control Tower (Next.js)
```bash
cd frontend
npm install
export ALLOYDB_DSN=postgresql://scm_app:password@localhost:5432/scm_db
npm run dev
# Open http://localhost:3000
```

### 5. Build Flutter App
```bash
cd mobile
flutter pub get
flutter run  # Android emulator or physical device
```

## Running Tests
```bash
# Go unit tests
cd services/ingestion && go test ./... -v

# Python tests
cd services/intelligence && pytest tests/ -v --cov=app

# Next.js type check
cd frontend && npx tsc --noEmit

# Flutter tests
cd mobile && flutter test
```

## Security Scans (Snyk SAST)
```bash
snyk code test services/ingestion/
snyk code test services/intelligence/
snyk test frontend/ --file=package.json
snyk container test nexgen-ingestion:latest
snyk container test nexgen-intelligence:latest
```

## Deploy XGBoost Model to Vertex AI
See `.agents/skills/deploy-vertex-xgboost/SKILL.md` for the full step-by-step skill.

```bash
# Train locally
cd services/intelligence
python -m app.ml.training_pipeline --mode cpu

# Deploy to Vertex AI (follow SKILL.md steps)
```

## Key Features

| Feature | Implementation |
|---|---|
| Real-time telemetry ingestion | Go 1.22 + Pub/Sub (100k+ msg/s) |
| Deep Packet Inspection | Schema validation + GPS bounds + replay prevention |
| Distributed tracing | OpenTelemetry → Google Cloud Trace |
| Anomaly detection | XGBoost on Vertex AI (< 150ms p99) |
| What-If simulation | AlloyDB Columnar Engine (analytical queries) |
| Perimeter security | Cloud Armor WAF + adaptive DDoS |
| Internal security | Cloud NGFW L7 inspection |
| Mobile offline-first | sqflite + connectivity-triggered sync |
| Cargo seal AI inspection | Gemini 2.0 Flash multimodal vision |
| FastAPI cold-start fix | Async background model loading (< 200ms /health) |

## Environment Variables

### Ingestion Service (Go)
| Variable | Default | Description |
|---|---|---|
| `GCP_PROJECT_ID` | `nexgen-scm-2026` | GCP Project ID |
| `PUBSUB_TOPIC_ID` | `telemetry-raw` | Pub/Sub topic |
| `OTLP_ENDPOINT` | `localhost:4317` | OTel collector endpoint |
| `PORT` | `8080` | HTTP server port |

### Intelligence Engine (Python)
| Variable | Default | Description |
|---|---|---|
| `GCP_PROJECT_ID` | `nexgen-scm-2026` | GCP Project ID |
| `VERTEX_ENDPOINT_ID` | `nexgen-scm-endpoint` | Vertex AI Endpoint |
| `ALLOYDB_DSN` | `postgresql://...` | AlloyDB connection string |
| `PUBSUB_INTELLIGENCE_SUB` | `intelligence-pull` | Pull subscription |
| `ANOMALY_THRESHOLD` | `0.75` | Anomaly score threshold |

### Control Tower (Next.js)
| Variable | Description |
|---|---|
| `ALLOYDB_DSN` | AlloyDB connection string |
| `INTELLIGENCE_ENGINE_URL` | FastAPI service URL |

---

*Built for Google Solution Challenge 2026 — NexGen SCM Team*