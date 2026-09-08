# Holds everything this state creates (items 9-13 in design.md's inventory).
# Separate from the cluster resource group by design (D10): one `terraform
# destroy` against the cluster state must never be able to reach this one.
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
