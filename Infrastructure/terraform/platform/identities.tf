# CI: GitHub Actions -> ACR (design.md D4, item 12).
resource "azurerm_user_assigned_identity" "ci" {
  name                = "travel-agent-ci"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "ci" {
  name                      = "github-actions-${var.ci_deploy_branch}"
  user_assigned_identity_id = azurerm_user_assigned_identity.ci.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:${var.github_repository}:ref:refs/heads/${var.ci_deploy_branch}"
}

# Pushes images built by the `push` job (D4). Pulling them into the
# cluster is a separate grant (tasks.md 5.5, AcrPull on AKS's own
# kubelet identity) and lives in cluster state.
resource "azurerm_role_assignment" "ci_acr_push" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.ci.principal_id
}

# Backend ServiceAccount -> Key Vault, via Workload ID (design.md D5, item 13).
resource "azurerm_user_assigned_identity" "backend" {
  name                = "travel-agent-backend"
  resource_group_name = azurerm_resource_group.platform.name
  location            = azurerm_resource_group.platform.location
  tags                = var.tags
}

# Grants read access to the vault secret regardless of whether the
# federated credential below exists yet — the role assignment authorizes
# the identity itself, not any particular federation to it.
resource "azurerm_role_assignment" "backend_keyvault_secrets_user" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.backend.principal_id
}

# Deferred until var.aks_oidc_issuer_url is supplied on a second apply — design.md D5.
resource "azurerm_federated_identity_credential" "backend_serviceaccount" {
  count                     = var.aks_oidc_issuer_url == "" ? 0 : 1
  name                      = "travel-agent-backend-sa"
  user_assigned_identity_id = azurerm_user_assigned_identity.backend.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = var.aks_oidc_issuer_url
  subject                   = "system:serviceaccount:${var.backend_namespace}:${var.backend_service_account_name}"
}
