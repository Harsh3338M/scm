# ─────────────────────────────────────────────
# Cloud Armor Security Policy (Layer 7 DDoS + WAF)
# ─────────────────────────────────────────────

resource "google_compute_security_policy" "nexgen_armor" {
  name        = "nexgen-scm-armor-policy"
  description = "Cloud Armor WAF policy for NexGen SCM — DDoS, OWASP CRS, rate limiting"
  project     = var.project_id

  # ── Adaptive Protection (ML-based DDoS mitigation) ──────────────────
  adaptive_protection_config {
    layer_7_ddos_defense_config {
      enable          = true
      rule_visibility = "STANDARD"
    }
  }

  # ── Rule 1000: Block known malicious IPs (highest priority) ──────────
  rule {
    action      = "deny(403)"
    priority    = 1000
    description = "Block known bad IPs via threat intelligence"

    match {
      expr {
        expression = "evaluateThreatIntelligence('iplist-known-malicious-ips')"
      }
    }
  }

  # ── Rule 2000: OWASP Core Rule Set — SQL Injection ───────────────────
  rule {
    action      = "deny(403)"
    priority    = 2000
    description = "OWASP CRS — SQLi protection"

    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable')"
      }
    }
  }

  # ── Rule 2001: OWASP CRS — XSS ───────────────────────────────────────
  rule {
    action      = "deny(403)"
    priority    = 2001
    description = "OWASP CRS — XSS protection"

    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
  }

  # ── Rule 2002: OWASP CRS — Remote File Inclusion ─────────────────────
  rule {
    action      = "deny(403)"
    priority    = 2002
    description = "OWASP CRS — RFI protection"

    match {
      expr {
        expression = "evaluatePreconfiguredExpr('rfi-v33-stable')"
      }
    }
  }

  # ── Rule 3000: Rate Limiting per IP ──────────────────────────────────
  rule {
    action      = "throttle"
    priority    = 3000
    description = "Rate limit: ${var.armor_rate_limit_threshold} req/min per IP"

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = var.armor_rate_limit_threshold
        interval_sec = 60
      }
    }
  }

  # ── Rule 9000: Allow all (default fallback) ───────────────────────────
  rule {
    action      = "allow"
    priority    = 2147483647
    description = "Default allow rule"

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

# ─────────────────────────────────────────────
# Backend Service (attaches the Armor policy)
# ─────────────────────────────────────────────

# NOTE: The actual Load Balancer backend service that references Cloud Armor
# is configured when deploying Cloud Run services with a Global HTTPS LB.
# The security policy resource name is exported for use in the LB config:
output "armor_security_policy_self_link" {
  description = "Cloud Armor security policy self-link to attach to Load Balancer"
  value       = google_compute_security_policy.nexgen_armor.self_link
}
