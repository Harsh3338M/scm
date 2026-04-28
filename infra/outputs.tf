output "vpc_network_id" {
  description = "VPC network self-link"
  value       = google_compute_network.vpc.self_link
}

output "vpc_subnet_id" {
  description = "Main subnet self-link"
  value       = google_compute_subnetwork.main.self_link
}

output "pubsub_telemetry_raw_topic" {
  description = "Pub/Sub topic for raw telemetry"
  value       = google_pubsub_topic.telemetry_raw.id
}

output "pubsub_anomaly_events_topic" {
  description = "Pub/Sub topic for anomaly events"
  value       = google_pubsub_topic.anomaly_events.id
}

output "pubsub_ingestion_pull_subscription" {
  description = "Pub/Sub pull subscription for ingestion"
  value       = google_pubsub_subscription.ingestion_pull.id
}

output "pubsub_intelligence_pull_subscription" {
  description = "Pub/Sub pull subscription for intelligence engine"
  value       = google_pubsub_subscription.intelligence_pull.id
}

output "alloydb_cluster_id" {
  description = "AlloyDB cluster resource name"
  value       = google_alloydb_cluster.primary.id
}

output "alloydb_primary_ip" {
  description = "AlloyDB primary instance private IP"
  value       = google_alloydb_instance.primary.ip_address
  sensitive   = true
}

output "vertex_endpoint_id" {
  description = "Vertex AI Endpoint resource name"
  value       = google_vertex_ai_endpoint.anomaly_detector.id
}

output "ingestion_sa_email" {
  description = "Ingestion service account email"
  value       = google_service_account.ingestion_sa.email
}

output "intelligence_sa_email" {
  description = "Intelligence engine service account email"
  value       = google_service_account.intelligence_sa.email
}

output "gcs_model_bucket" {
  description = "GCS bucket for model artifacts"
  value       = google_storage_bucket.model_artifacts.name
}
