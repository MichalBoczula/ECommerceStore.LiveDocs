mock_provider "azurerm" {}
variables {
  resource_group_name = "rg-ecommerce-dev"
  environment_id      = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-dev/providers/Microsoft.App/managedEnvironments/cae-ecommerce-dev"
  initial_image       = "mb0101/ecommerce-store-livedocs@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
run "host_contract" {
  command = plan
  assert {
    condition     = azurerm_container_app.host.revision_mode == "Single" && azurerm_container_app.host.ingress[0].target_port == 8080 && !azurerm_container_app.host.ingress[0].allow_insecure_connections
    error_message = "Require HTTPS, port 8080 and single revision mode."
  }
  assert {
    condition     = azurerm_container_app.host.template[0].min_replicas == 0 && azurerm_container_app.host.template[0].max_replicas == 1 && azurerm_container_app.host.template[0].container[0].cpu == 0.25
    error_message = "Preserve the small scale-to-zero allocation."
  }
  assert {
    condition     = azurerm_container_app.host.template[0].container[0].startup_probe[0].path == "/health/ready" && azurerm_container_app.host.template[0].container[0].readiness_probe[0].path == "/health/ready" && azurerm_container_app.host.template[0].container[0].liveness_probe[0].path == "/health/live"
    error_message = "Use explicit startup, readiness and liveness probes."
  }
}
run "mutable_image_rejected" {
  command = plan
  variables { initial_image = "mb0101/ecommerce-store-livedocs:latest" }
  expect_failures = [var.initial_image]
}
