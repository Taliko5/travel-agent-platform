# Separate from the platform resource group by design — design.md D10.
resource "azurerm_resource_group" "cluster" {
  name     = var.resource_group_name
  location = var.region
  tags     = var.tags
}
