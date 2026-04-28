# ─────────────────────────────────────────────
# AlloyDB Cluster & Primary Instance
# ─────────────────────────────────────────────

resource "google_alloydb_cluster" "primary" {
  provider   = google-beta
  cluster_id = var.alloydb_cluster_id
  location   = var.region
  project    = var.project_id

  network_config {
    network = google_compute_network.vpc.id
  }

  initial_user {
    user     = var.alloydb_user
    password = data.google_secret_manager_secret_version.alloydb_password.secret_data
  }

  automated_backup_policy {
    enabled = true
    weekly_schedule {
      days_of_week = ["SUNDAY"]
      start_times {
        hours   = 2
        minutes = 0
      }
    }
    backup_window = "3600s"
    quantity_based_retention {
      count = 7
    }
    location = var.region
  }

  labels = var.labels

  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.apis,
  ]
}

resource "google_alloydb_instance" "primary" {
  provider      = google-beta
  cluster       = google_alloydb_cluster.primary.name
  instance_id   = var.alloydb_primary_instance_id
  instance_type = "PRIMARY"

  machine_config {
    cpu_count = 4
  }

  # Enable the columnar engine for analytical / What-If queries
  query_insights_config {
    query_string_length     = 1024
    record_application_tags = true
    record_client_address   = true
  }

  database_flags = {
    "google_columnar_engine.enabled"    = "on"
    "google_columnar_engine.memory_size_in_mb" = "2048"
    "max_connections"                   = "500"
    "log_min_duration_statement"        = "1000"
  }

  labels = var.labels
}

# ─────────────────────────────────────────────
# AlloyDB Password (stored in Secret Manager)
# ─────────────────────────────────────────────

resource "google_secret_manager_secret" "alloydb_password" {
  secret_id = "nexgen-alloydb-password"
  project   = var.project_id

  replication {
    auto {}
  }
}

# NOTE: The actual password value must be stored manually via:
#   gcloud secrets versions add nexgen-alloydb-password --data-file=<(echo -n "YOUR_PASSWORD")
# After the first apply, import:
#   terraform import google_secret_manager_secret_version.alloydb_password_version ...

data "google_secret_manager_secret_version" "alloydb_password" {
  secret  = google_secret_manager_secret.alloydb_password.id
  project = var.project_id
}

# ─────────────────────────────────────────────
# AlloyDB Database & Tables (via null_resource)
# ─────────────────────────────────────────────

# The schema migration is handled by the intelligence service on startup.
# See services/intelligence/app/db/alloydb.py for schema definition.

# ─────────────────────────────────────────────
# IAM for AlloyDB Access
# ─────────────────────────────────────────────

resource "google_project_iam_member" "alloydb_client_intelligence" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.intelligence_sa.email}"
}

resource "google_project_iam_member" "alloydb_client_ingestion" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}
