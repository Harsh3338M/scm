# ─────────────────────────────────────────────
# Vertex AI Endpoint
# ─────────────────────────────────────────────

resource "google_vertex_ai_endpoint" "anomaly_detector" {
  name         = "nexgen-scm-endpoint"
  display_name = "NexGen SCM Anomaly Detection Endpoint"
  description  = "Serves the XGBoost anomaly detection model for real-time inference"
  location     = var.region
  project      = var.project_id

  labels = var.labels

  # Private service connect for secure inference (no public internet exposure)
  # Uncomment when PSC is configured:
  # network = google_compute_network.vpc.id

  depends_on = [google_project_service.apis]
}

# ─────────────────────────────────────────────
# BigQuery Dataset for Training Data
# ─────────────────────────────────────────────

resource "google_bigquery_dataset" "telemetry" {
  dataset_id                  = "nexgen_telemetry"
  friendly_name               = "NexGen Telemetry Training Data"
  description                 = "Raw and feature-engineered telemetry for XGBoost model training"
  location                    = var.region
  project                     = var.project_id
  default_table_expiration_ms = null

  labels = var.labels
}

# Raw telemetry table schema
resource "google_bigquery_table" "telemetry_raw" {
  dataset_id = google_bigquery_dataset.telemetry.dataset_id
  table_id   = "telemetry_raw"
  project    = var.project_id

  schema = jsonencode([
    { name = "device_id",              type = "STRING",    mode = "REQUIRED" },
    { name = "timestamp",              type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "lat",                    type = "FLOAT64",   mode = "REQUIRED" },
    { name = "lon",                    type = "FLOAT64",   mode = "REQUIRED" },
    { name = "temperature",            type = "FLOAT64",   mode = "NULLABLE" },
    { name = "humidity",               type = "FLOAT64",   mode = "NULLABLE" },
    { name = "speed_kmh",              type = "FLOAT64",   mode = "NULLABLE" },
    { name = "battery_pct",            type = "FLOAT64",   mode = "NULLABLE" },
    { name = "anomaly_label",          type = "INTEGER",   mode = "NULLABLE" },
    { name = "ingested_at",            type = "TIMESTAMP", mode = "NULLABLE" },
  ])

  time_partitioning {
    type  = "DAY"
    field = "timestamp"
  }

  clustering = ["device_id"]
  labels     = var.labels
}

# ─────────────────────────────────────────────
# Vertex AI Model (placeholder — populated by SKILL.md)
# ─────────────────────────────────────────────

# The model resource is managed by the deploy-vertex-xgboost skill.
# The endpoint above is pre-provisioned and waiting for a deployed model.

output "vertex_endpoint_name" {
  description = "Vertex AI Endpoint display name"
  value       = google_vertex_ai_endpoint.anomaly_detector.display_name
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset ID for telemetry training data"
  value       = google_bigquery_dataset.telemetry.dataset_id
}
