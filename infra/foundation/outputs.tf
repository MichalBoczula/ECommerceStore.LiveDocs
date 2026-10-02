output "github_variables" {
  value = {
    AZURE_SUBSCRIPTION_ID            = var.subscription_id
    AZURE_TENANT_ID                  = var.tenant_id
    AZURE_CLIENT_ID                  = azurerm_user_assigned_identity.delivery.client_id
    AZURE_RESOURCE_GROUP             = data.azurerm_resource_group.development.name
    AZURE_CONTAINER_APPS_ENVIRONMENT = var.container_apps_environment_name
    AZURE_CONTAINER_APP_NAME         = var.container_app_name
    AZURE_ARCHIVE_STORAGE_ACCOUNT    = azurerm_storage_account.archive.name
    AZURE_ARCHIVE_CONTAINER          = azurerm_storage_container.reports.name
    AZURE_APP_DEPLOYMENT_READY       = tostring(var.enable_app_deployment)
    AZURE_DEPLOY_ENABLED             = "false"
  }
}
