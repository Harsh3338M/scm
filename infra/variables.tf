variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "nexgen-scm-2026"
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Primary GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Deployment environment (dev | staging | prod)"
  type        = string
  default     = "prod"
}

variable "alloydb_cluster_id" {
  description = "AlloyDB cluster identifier"
  type        = string
  default     = "nexgen-scm-cluster"
}

variable "alloydb_primary_instance_id" {
  description = "AlloyDB primary instance identifier"
  type        = string
  default     = "nexgen-scm-primary"
}

variable "alloydb_db_name" {
  description = "Name of the main application database"
  type        = string
  default     = "scm_db"
}

variable "alloydb_user" {
  description = "AlloyDB application user"
  type        = string
  default     = "scm_app"
}

variable "vpc_name" {
  description = "VPC network name"
  type        = string
  default     = "nexgen-scm-vpc"
}

variable "vpc_subnet_cidr" {
  description = "Subnet CIDR for the main VPC"
  type        = string
  default     = "10.10.0.0/24"
}

variable "gcs_model_bucket" {
  description = "GCS bucket for Vertex AI model artifacts"
  type        = string
  default     = "nexgen-scm-2026-models"
}

variable "pubsub_message_retention_days" {
  description = "Message retention duration in days"
  type        = number
  default     = 7
}

variable "armor_rate_limit_threshold" {
  description = "Cloud Armor rate limit requests per minute per IP"
  type        = number
  default     = 1000
}

variable "labels" {
  description = "Common resource labels"
  type        = map(string)
  default = {
    project     = "nexgen-scm"
    managed_by  = "terraform"
    environment = "prod"
  }
}
