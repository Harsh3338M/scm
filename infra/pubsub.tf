# ─────────────────────────────────────────────
# Pub/Sub Topics
# ─────────────────────────────────────────────

# Dead-Letter Topic (must exist before main topics reference it)
resource "google_pubsub_topic" "telemetry_dlq" {
  name    = "telemetry-dlq"
  project = var.project_id
  labels  = var.labels

  message_retention_duration = "${var.pubsub_message_retention_days * 86400}s"
}

# Primary telemetry ingestion topic
resource "google_pubsub_topic" "telemetry_raw" {
  name    = "telemetry-raw"
  project = var.project_id
  labels  = var.labels

  message_retention_duration = "${var.pubsub_message_retention_days * 86400}s"
}

# Anomaly events output topic (written by intelligence engine)
resource "google_pubsub_topic" "anomaly_events" {
  name    = "anomaly-events"
  project = var.project_id
  labels  = var.labels

  message_retention_duration = "${var.pubsub_message_retention_days * 86400}s"
}

# ─────────────────────────────────────────────
# Pub/Sub Subscriptions
# ─────────────────────────────────────────────

# Pull subscription for the Go ingestion service
# (validates, transforms, republishes to telemetry-raw)
resource "google_pubsub_subscription" "ingestion_pull" {
  name    = "ingestion-pull"
  topic   = google_pubsub_topic.telemetry_raw.name
  project = var.project_id
  labels  = var.labels

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = false
  enable_exactly_once_delivery = true

  expiration_policy {
    ttl = "" # Never expire
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.telemetry_dlq.id
    max_delivery_attempts = 5
  }
}

# Pull subscription for the Python intelligence engine
resource "google_pubsub_subscription" "intelligence_pull" {
  name    = "intelligence-pull"
  topic   = google_pubsub_topic.telemetry_raw.name
  project = var.project_id
  labels  = var.labels

  ack_deadline_seconds         = 60
  message_retention_duration   = "604800s"
  retain_acked_messages        = false
  enable_exactly_once_delivery = true

  expiration_policy {
    ttl = ""
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.telemetry_dlq.id
    max_delivery_attempts = 5
  }
}

# Pull subscription for anomaly events (consumed by Control Tower / notifications)
resource "google_pubsub_subscription" "anomaly_events_pull" {
  name    = "anomaly-events-pull"
  topic   = google_pubsub_topic.anomaly_events.name
  project = var.project_id
  labels  = var.labels

  ack_deadline_seconds       = 30
  message_retention_duration = "86400s" # 1 day

  expiration_policy {
    ttl = ""
  }
}

# ─────────────────────────────────────────────
# IAM Bindings for Subscriptions
# ─────────────────────────────────────────────

resource "google_pubsub_subscription_iam_member" "intelligence_subscriber" {
  subscription = google_pubsub_subscription.intelligence_pull.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.intelligence_sa.email}"
  project      = var.project_id
}

resource "google_pubsub_topic_iam_member" "ingestion_publisher" {
  topic   = google_pubsub_topic.telemetry_raw.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
  project = var.project_id
}

resource "google_pubsub_topic_iam_member" "intelligence_anomaly_publisher" {
  topic   = google_pubsub_topic.anomaly_events.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.intelligence_sa.email}"
  project = var.project_id
}

# Allow DLQ subscription to receive dead letters
resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic   = google_pubsub_topic.telemetry_dlq.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
  project = var.project_id
}

data "google_project" "project" {
  project_id = var.project_id
}
