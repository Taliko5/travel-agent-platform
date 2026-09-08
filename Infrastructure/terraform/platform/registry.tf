# ACR Basic (design.md D4). admin_enabled stays false — the whole point of
# D4's identity/federation setup is that no stored registry credential
# exists; turning on the admin account would put one back.
resource "azurerm_container_registry" "this" {
  name                = "${var.acr_base_name}${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}
