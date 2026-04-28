# ─────────────────────────────────────────────
# Cloud Next Generation Firewall (NGFW)
# ─────────────────────────────────────────────

# Firewall Plus endpoint for L7 inspection
resource "google_network_security_firewall_endpoint" "nexgen_ngfw" {
  provider          = google-beta
  name              = "nexgen-scm-ngfw-endpoint"
  location          = var.zone
  billing_project_id = var.project_id

  labels = var.labels
}

# NGFW Policy — L7 inspection rules for VPC east-west traffic
resource "google_network_security_firewall_endpoint_association" "nexgen_ngfw_assoc" {
  provider          = google-beta
  name              = "nexgen-ngfw-assoc"
  location          = var.zone
  network           = google_compute_network.vpc.id
  firewall_endpoint = google_network_security_firewall_endpoint.nexgen_ngfw.id

  labels = var.labels
}

# ─────────────────────────────────────────────
# Hierarchical Firewall Policy
# ─────────────────────────────────────────────

resource "google_compute_network_firewall_policy" "nexgen_policy" {
  name        = "nexgen-scm-firewall-policy"
  description = "NexGen SCM VPC firewall policy with L7 inspection rules"
  project     = var.project_id
}

resource "google_compute_network_firewall_policy_association" "nexgen_policy_assoc" {
  name              = "nexgen-scm-policy-assoc"
  project           = var.project_id
  attachment_target = google_compute_network.vpc.id
  firewall_policy   = google_compute_network_firewall_policy.nexgen_policy.name
}

# Rule: Allow internal AlloyDB traffic (port 5432) only from known service CIDRs
resource "google_compute_network_firewall_policy_rule" "allow_alloydb_internal" {
  firewall_policy = google_compute_network_firewall_policy.nexgen_policy.name
  project         = var.project_id
  description     = "Allow AlloyDB PostgreSQL traffic from internal service subnet"
  priority        = 1000
  direction       = "INGRESS"
  action          = "allow"
  enable_logging  = true

  match {
    src_ip_ranges = [var.vpc_subnet_cidr]
    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["5432"]
    }
  }

  target_resources = [google_compute_network.vpc.self_link]
}

# Rule: Allow Pub/Sub API egress (HTTPS/443) from ingestion and intelligence services
resource "google_compute_network_firewall_policy_rule" "allow_pubsub_egress" {
  firewall_policy = google_compute_network_firewall_policy.nexgen_policy.name
  project         = var.project_id
  description     = "Allow HTTPS egress for Pub/Sub and Vertex AI API calls"
  priority        = 1001
  direction       = "EGRESS"
  action          = "allow"
  enable_logging  = true

  match {
    dest_ip_ranges = ["0.0.0.0/0"]
    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["443"]
    }
  }

  target_resources = [google_compute_network.vpc.self_link]
}

# Rule: Allow OTLP telemetry egress (gRPC/4317)
resource "google_compute_network_firewall_policy_rule" "allow_otlp_egress" {
  firewall_policy = google_compute_network_firewall_policy.nexgen_policy.name
  project         = var.project_id
  description     = "Allow OTLP gRPC egress to Cloud Trace"
  priority        = 1002
  direction       = "EGRESS"
  action          = "allow"
  enable_logging  = true

  match {
    dest_ip_ranges = ["0.0.0.0/0"]
    layer4_configs {
      ip_protocol = "tcp"
      ports       = ["4317", "4318"]
    }
  }

  target_resources = [google_compute_network.vpc.self_link]
}

# Rule: Block all other internal ingress (default deny)
resource "google_compute_network_firewall_policy_rule" "deny_all_internal_ingress" {
  firewall_policy = google_compute_network_firewall_policy.nexgen_policy.name
  project         = var.project_id
  description     = "Default deny all ingress — explicit allow rules above take precedence"
  priority        = 65534
  direction       = "INGRESS"
  action          = "deny"
  enable_logging  = true

  match {
    src_ip_ranges = ["0.0.0.0/0"]
    layer4_configs {
      ip_protocol = "all"
    }
  }

  target_resources = [google_compute_network.vpc.self_link]
}
