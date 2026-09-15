# The vault only — deliberately no azurerm_key_vault_secret resource here.
# design.md D5: "the secret *value* is set out-of-band with `az keyvault
# secret set` and never enters Terraform state or the repository." Any
# azurerm_key_vault_secret resource stores its value in state regardless of
# how it's populated, so managing the secret *object* in Terraform — even
# with a placeholder value — would put something in state D5 says must
# never be there, and would fight the out-of-band write on every future
# `terraform plan`. The vault is the only thing this state owns; the secret
# object named var.key_vault_secret_object_name is created by the operator
# via `az keyvault secret set`, documented in README.md.
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

# Lets the operator run `az keyvault secret set` (D5's out-of-band step)
# without needing a role assignment created by hand first. Optional: if
# var.operator_object_id is null, nobody gets this grant from Terraform and
# the operator authorizes themselves separately.
resource "azurerm_role_assignment" "operator_secrets_officer" {
  count                = var.operator_object_id == null ? 0 : 1
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.operator_object_id
}
