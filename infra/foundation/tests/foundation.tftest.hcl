mock_provider "azurerm" {
  override_during = plan
  mock_resource "azurerm_resource_group" {
    defaults = { id = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-livedocs-archive" }
  }
  mock_resource "azurerm_storage_account" {
    defaults = { id = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-livedocs-archive/providers/Microsoft.Storage/storageAccounts/testarchive" }
  }
  mock_resource "azurerm_storage_container" {
    defaults = { id = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-livedocs-archive/providers/Microsoft.Storage/storageAccounts/testarchive/blobServices/default/containers/livedocs" }
  }
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-bootstrap/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-ecommerce-livedocs-dev"
      principal_id = "33333333-3333-3333-3333-333333333333"
      client_id    = "44444444-4444-4444-4444-444444444444"
    }
  }
  mock_resource "azurerm_role_definition" {
    defaults = { role_definition_resource_id = "/subscriptions/11111111-1111-1111-1111-111111111111/providers/Microsoft.Authorization/roleDefinitions/55555555-5555-5555-5555-555555555555" }
  }
}
override_data {
  target = data.azurerm_resource_group.bootstrap
  values = { id = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-bootstrap", name = "rg-ecommerce-bootstrap", location = "northeurope" }
}
override_data {
  target = data.azurerm_resource_group.development
  values = { id = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-dev", name = "rg-ecommerce-dev", location = "northeurope" }
}
override_data {
  target = data.azurerm_client_config.operator
  values = { object_id = "66666666-6666-6666-6666-666666666666" }
}
variables {
  subscription_id = "11111111-1111-1111-1111-111111111111"
  tenant_id       = "22222222-2222-2222-2222-222222222222"
}

run "archive_before_ACA_exists" {
  command = plan
  assert {
    condition     = length(data.azurerm_container_app.host) == 0 && length(azurerm_role_assignment.app_delivery) == 0
    error_message = "Fresh setup must not require or assign permissions to an absent ACA app."
  }
  assert {
    condition     = azurerm_resource_group.archive.name != data.azurerm_resource_group.development.name && azurerm_management_lock.archive.lock_level == "CanNotDelete"
    error_message = "Keep the archive outside disposable application infrastructure and protect its group."
  }
  assert {
    condition     = !azurerm_storage_account.archive.shared_access_key_enabled && !azurerm_storage_account.archive.allow_nested_items_to_be_public && azurerm_storage_container.reports.container_access_type == "private"
    error_message = "Archives must require Entra authentication."
  }
  assert {
    condition     = azurerm_storage_account.archive.blob_properties[0].versioning_enabled && azurerm_storage_account.archive.blob_properties[0].delete_retention_policy[0].days == 30
    error_message = "Preserve versions and deleted report recovery."
  }
  assert {
    condition     = azurerm_role_assignment.archive_reader.role_definition_name == "Storage Blob Data Reader" && azurerm_role_assignment.archive_reader.scope == azurerm_storage_container.reports.id
    error_message = "CI archive access must be read-only and container scoped."
  }
  assert {
    condition     = azurerm_federated_identity_credential.delivery.subject == "repo:MichalBoczula/ECommerceStore.LiveDocs:ref:refs/heads/main"
    error_message = "Federation must not authorize PR or feature branch identities."
  }
  assert {
    condition     = output.github_variables.AZURE_DEPLOY_ENABLED == "false" && output.github_variables.AZURE_APP_DEPLOYMENT_READY == "false"
    error_message = "Fresh foundation must not enable deployment automatically."
  }
}

run "app_permissions_after_infrastructure" {
  command = plan
  variables { enable_app_deployment = true }
  override_data {
    target = data.azurerm_container_app.host[0]
    values = { id = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-dev/providers/Microsoft.App/containerApps/ca-ecommerce-livedocs-dev" }
  }
  override_data {
    target = data.azurerm_container_app_environment.host[0]
    values = { id = "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-ecommerce-dev/providers/Microsoft.App/managedEnvironments/cae-ecommerce-dev" }
  }
  assert {
    condition     = azurerm_role_assignment.app_delivery[0].scope == data.azurerm_container_app.host[0].id && azurerm_role_assignment.environment_access[0].scope == data.azurerm_container_app_environment.host[0].id
    error_message = "Never grant delivery access at subscription/resource-group scope."
  }
  assert {
    condition     = !contains(one(azurerm_role_definition.delivery.permissions).actions, "*") && !contains(one(azurerm_role_definition.delivery.permissions).actions, "Microsoft.App/managedEnvironments/write") && !contains(one(azurerm_role_definition.delivery.permissions).actions, "Microsoft.App/containerApps/delete")
    error_message = "Delivery cannot create/delete environments, delete apps or manage access."
  }
}
