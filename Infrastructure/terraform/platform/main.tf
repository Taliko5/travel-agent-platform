# Separate from the cluster resource group by design — design.md D10.
resource "azurerm_resource_group" "platform" {
  name     = var.resource_group_name
  location = var.region
  tags     = var.tags
}

resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}
