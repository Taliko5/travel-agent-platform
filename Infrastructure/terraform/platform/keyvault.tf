# The vault only — no azurerm_key_vault_secret resource here — design.md D5.
resource "azurerm_key_vault" "this" {
  name                = "${var.key_vault_base_name}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  enable_rbac_authorization = true

  # D10: not verified beyond the default. Explicit rather than left to
  # whatever the provider happens to default to, per the same task that
  # settled the retention-period question in design.md D10.
  soft_delete_retention_days = 90

  tags = var.tags
}

data "azurerm_client_config" "current" {}

# Lets the operator run `az keyvault secret set` (D5's out-of-band step) — design.md D5.
resource "azurerm_role_assignment" "operator_secrets_officer" {
  count                = var.operator_object_id == null ? 0 : 1
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.operator_object_id
}
