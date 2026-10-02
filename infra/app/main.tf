variable "resource_group_name" { type = string }
variable "environment_id" { type = string }
variable "name" {
  type    = string
  default = "ca-ecommerce-livedocs-dev"
}
variable "initial_image" {
  type        = string
  description = "Published immutable LiveDocs digest used when creating/recreating the app."
  validation {
    condition     = can(regex("^(docker.io/)?mb0101/ecommerce-store-livedocs@sha256:[0-9a-f]{64}$", var.initial_image))
    error_message = "Use an immutable LiveDocs image digest, never latest."
  }
}

# Called from Infrastructure application state: its Destroy owns this app.
resource "azurerm_container_app" "host" {
  name                         = var.name
  container_app_environment_id = var.environment_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  max_inactive_revisions       = 5
  tags                         = { project = "ECommerceStore", component = "LiveDocs", managedBy = "Terraform" }
  ingress {
    external_enabled           = true
    allow_insecure_connections = false
    target_port                = 8080
    transport                  = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
  template {
    min_replicas = 0
    max_replicas = 1
    http_scale_rule {
      name                = "http"
      concurrent_requests = 10
    }
    container {
      name   = "livedocs"
      image  = var.initial_image
      cpu    = 0.25
      memory = "0.5Gi"
      startup_probe {
        transport               = "HTTP"
        path                    = "/health/ready"
        port                    = 8080
        initial_delay           = 1
        interval_seconds        = 2
        timeout                 = 2
        failure_count_threshold = 30
      }
      readiness_probe {
        transport               = "HTTP"
        path                    = "/health/ready"
        port                    = 8080
        initial_delay           = 3
        interval_seconds        = 5
        timeout                 = 2
        failure_count_threshold = 3
        success_count_threshold = 1
      }
      liveness_probe {
        transport               = "HTTP"
        path                    = "/health/live"
        port                    = 8080
        initial_delay           = 10
        interval_seconds        = 10
        timeout                 = 2
        failure_count_threshold = 3
      }
    }
  }
  lifecycle {
    # CI changes exactly these fields; Terraform owns all remaining configuration.
    ignore_changes = [template[0].container[0].image, template[0].revision_suffix]
  }
}
output "app_id" { value = azurerm_container_app.host.id }
output "portal_url" { value = "https://${azurerm_container_app.host.ingress[0].fqdn}/livedoc/" }
