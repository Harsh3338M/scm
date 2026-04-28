terraform {
  required_version = ">= 1.7.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.25"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.25"
    }
  }

  # Use GCS backend in production; comment out for local development
  # backend "gcs" {
  #   bucket = "nexgen-scm-2026-tfstate"
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ─────────────────────────────────────────────
# Enable Required APIs
# ─────────────────────────────────────────────
locals {
  required_apis = [
    "compute.googleapis.com",
    "alloydb.googleapis.com",
    "pubsub.googleapis.com",
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "bigquery.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "servicenetworking.googleapis.com",
    "networksecurity.googleapis.com",
    "compute.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.required_apis)
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ─────────────────────────────────────────────
# VPC Network
# ─────────────────────────────────────────────
resource "google_compute_network" "vpc" {
  name                    = var.vpc_name
  auto_create_subnetworks = false
  project                 = var.project_id
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "main" {
  name          = "${var.vpc_name}-subnet"
  ip_cidr_range = var.vpc_subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
  project       = var.project_id

  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Private Service Connection for AlloyDB
resource "google_compute_global_address" "private_ip_range" {
  name          = "nexgen-private-ip-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
  project       = var.project_id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
  depends_on              = [google_project_service.apis]
}

# ─────────────────────────────────────────────
# GCS Bucket for Model Artifacts
# ─────────────────────────────────────────────
resource "google_storage_bucket" "model_artifacts" {
  name          = var.gcs_model_bucket
  location      = var.region
  force_destroy = false
  project       = var.project_id

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = var.labels
}

# ─────────────────────────────────────────────
# Service Account for Ingestion Service
# ─────────────────────────────────────────────
resource "google_service_account" "ingestion_sa" {
  account_id   = "nexgen-ingestion-sa"
  display_name = "NexGen Ingestion Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "ingestion_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

resource "google_project_iam_member" "ingestion_trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.ingestion_sa.email}"
}

# ─────────────────────────────────────────────
# Service Account for Intelligence Engine
# ─────────────────────────────────────────────
resource "google_service_account" "intelligence_sa" {
  account_id   = "nexgen-intelligence-sa"
  display_name = "NexGen Intelligence Engine Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "intelligence_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.intelligence_sa.email}"
}

resource "google_project_iam_member" "intelligence_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.intelligence_sa.email}"
}

resource "google_project_iam_member" "intelligence_alloydb_client" {
  project = var.project_id
  role    = "roles/alloydb.client"
  member  = "serviceAccount:${google_service_account.intelligence_sa.email}"
}
