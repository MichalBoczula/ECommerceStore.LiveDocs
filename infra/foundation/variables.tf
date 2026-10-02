variable "subscription_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.subscription_id))
    error_message = "Pass the target Azure subscription ID."
  }
}
variable "tenant_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.tenant_id))
    error_message = "Pass the target Entra tenant ID."
  }
}
variable "location" {
  type    = string
  default = "northeurope"
}
variable "archive_resource_group_name" {
  type    = string
  default = "rg-ecommerce-livedocs-archive"
  validation {
    condition     = !contains(["rg-ecommerce-dev", "rg-ecommerce-bootstrap", "rg-ecommerce-terraform-state"], lower(var.archive_resource_group_name))
    error_message = "Keep the archive outside application, identity and external state groups."
  }
}
variable "archive_storage_account_name" {
  type        = string
  default     = null
  description = "Optional globally unique name; default derives from subscription and archive group."
  validation {
    condition     = var.archive_storage_account_name == null ? true : can(regex("^[a-z0-9]{3,24}$", var.archive_storage_account_name))
    error_message = "Use a 3–24 character lowercase storage account name."
  }
}
variable "container_apps_environment_name" {
  type    = string
  default = "cae-ecommerce-dev"
}
variable "container_app_name" {
  type    = string
  default = "ca-ecommerce-livedocs-dev"
}
variable "enable_app_deployment" {
  type        = bool
  default     = false
  description = "Enable only after Infrastructure has created the environment and LiveDocs app."
}
