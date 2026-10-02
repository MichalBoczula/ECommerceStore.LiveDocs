locals {
  tags            = { project = "ECommerceStore", component = "LiveDocs", lifecycle = "persistent", managedBy = "Terraform" }
  archive_account = coalesce(var.archive_storage_account_name, "stecomld${substr(sha256("${var.subscription_id}/${var.archive_resource_group_name}"), 0, 14)}")
}

# D/2 owns these retained groups; LiveDocs does not declare or import them.
data "azurerm_resource_group" "bootstrap" { name = "rg-ecommerce-bootstrap" }
data "azurerm_resource_group" "development" { name = "rg-ecommerce-dev" }

resource "azurerm_resource_group" "archive" {
  name     = var.archive_resource_group_name
  location = var.location
  tags     = local.tags
  lifecycle { prevent_destroy = true }
}

resource "azurerm_storage_account" "archive" {
  name                            = local.archive_account
  resource_group_name             = azurerm_resource_group.archive.name
  location                        = azurerm_resource_group.archive.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  account_kind                    = "StorageV2"
  access_tier                     = "Hot"
  https_traffic_only_enabled      = true
  min_tls_version                 = "TLS1_2"
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  public_network_access           = "Enabled"
  default_to_oauth_authentication = true
  tags                            = local.tags
  blob_properties {
    versioning_enabled = true
    delete_retention_policy { days = 30 }
    container_delete_retention_policy { days = 30 }
  }
  lifecycle { prevent_destroy = true }
}

resource "azurerm_storage_container" "reports" {
  name                  = "livedocs"
  storage_account_id    = azurerm_storage_account.archive.id
  container_access_type = "private"
  lifecycle { prevent_destroy = true }
}

# Operator can validate/uploads packages; deployment CI receives read access only.
resource "azurerm_role_assignment" "operator_archive" {
  scope                = azurerm_storage_container.reports.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.operator.object_id
  lifecycle { prevent_destroy = true }
}

resource "azurerm_management_lock" "archive" {
  name       = "protect-livedocs-archive"
  scope      = azurerm_resource_group.archive.id
  lock_level = "CanNotDelete"
  notes      = "Persistent report archive; excluded from development application teardown."
  lifecycle { prevent_destroy = true }
}

resource "azurerm_user_assigned_identity" "delivery" {
  name                = "id-ecommerce-livedocs-dev"
  resource_group_name = data.azurerm_resource_group.bootstrap.name
  location            = data.azurerm_resource_group.bootstrap.location
  tags                = local.tags
  lifecycle { prevent_destroy = true }
}

resource "azurerm_federated_identity_credential" "delivery" {
  name                      = "github-livedocs-main"
  user_assigned_identity_id = azurerm_user_assigned_identity.delivery.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:MichalBoczula/ECommerceStore.LiveDocs:ref:refs/heads/main"
  lifecycle { prevent_destroy = true }
}

resource "azurerm_role_assignment" "archive_reader" {
  scope                            = azurerm_storage_container.reports.id
  role_definition_name             = "Storage Blob Data Reader"
  principal_id                     = azurerm_user_assigned_identity.delivery.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
  lifecycle { prevent_destroy = true }
}

# Delay app-scoped assignments until Infrastructure creates the target resources.
data "azurerm_container_app" "host" {
  count               = var.enable_app_deployment ? 1 : 0
  name                = var.container_app_name
  resource_group_name = data.azurerm_resource_group.development.name
}
data "azurerm_container_app_environment" "host" {
  count               = var.enable_app_deployment ? 1 : 0
  name                = var.container_apps_environment_name
  resource_group_name = data.azurerm_resource_group.development.name
}

resource "azurerm_role_definition" "delivery" {
  name              = "ECommerceStore LiveDocs Image Delivery"
  scope             = data.azurerm_resource_group.development.id
  assignable_scopes = [data.azurerm_resource_group.development.id]
  permissions {
    actions = ["Microsoft.App/containerApps/read", "Microsoft.App/containerApps/write", "Microsoft.App/managedEnvironments/read", "Microsoft.App/managedEnvironments/join/action"]
  }
  lifecycle { prevent_destroy = true }
}
resource "azurerm_role_assignment" "app_delivery" {
  count                            = var.enable_app_deployment ? 1 : 0
  scope                            = data.azurerm_container_app.host[0].id
  role_definition_id               = azurerm_role_definition.delivery.role_definition_resource_id
  principal_id                     = azurerm_user_assigned_identity.delivery.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
  # The ephemeral scope is recreated after Infrastructure destroy/reapply.
}
resource "azurerm_role_assignment" "environment_access" {
  count                            = var.enable_app_deployment ? 1 : 0
  scope                            = data.azurerm_container_app_environment.host[0].id
  role_definition_id               = azurerm_role_definition.delivery.role_definition_resource_id
  principal_id                     = azurerm_user_assigned_identity.delivery.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}
