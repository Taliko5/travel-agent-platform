# Every value here is an identifier or a URL — resource IDs, names,
# client IDs, a tenant ID, a login server hostname. None is the vault
# secret's value: this state never reads it, so it cannot output it
# (task 4.6). Infrastructure/terraform/cluster/ (Section 5) reads these
# to attach the registry, enable the Key Vault add-on, and — once its own
# OIDC issuer exists — feed var.aks_oidc_issuer_url back into a second
# apply of this state.

output "resource_group_name" {
  value = azurerm_resource_group.platform.name
}

output "region" {
  value = azurerm_resource_group.platform.location
}

output "acr_id" {
  value = azurerm_container_registry.this.id
}

output "acr_login_server" {
  value = azurerm_container_registry.this.login_server
}

output "key_vault_id" {
  value = azurerm_key_vault.this.id
}

output "key_vault_name" {
  value = azurerm_key_vault.this.name
}

output "key_vault_tenant_id" {
  value = azurerm_key_vault.this.tenant_id
}

output "key_vault_secret_object_name" {
  value = var.key_vault_secret_object_name
}

output "ci_identity_client_id" {
  value = azurerm_user_assigned_identity.ci.client_id
}

output "ci_identity_principal_id" {
  value = azurerm_user_assigned_identity.ci.principal_id
}

output "backend_identity_client_id" {
  value = azurerm_user_assigned_identity.backend.client_id
}

output "backend_identity_principal_id" {
  value = azurerm_user_assigned_identity.backend.principal_id
}

output "backend_federated_credential_configured" {
  description = "False until var.aks_oidc_issuer_url has been supplied and this state re-applied (see README.md)."
  value       = length(azurerm_federated_identity_credential.backend_serviceaccount) > 0
}
