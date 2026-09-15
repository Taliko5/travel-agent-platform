data "azurerm_client_config" "current" {}

# CI's cluster-scoped access — design.md D4's extension, task 5.9.
# Lets CI fetch kubeconfig via `az aks get-credentials`.
resource "azurerm_role_assignment" "ci_aks_cluster_user" {
  scope                = azurerm_kubernetes_cluster.this.id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = var.ci_identity_principal_id
}

# Lets CI's `helm upgrade --install` create and update the chart's objects — design.md D4.
resource "azurerm_role_assignment" "ci_aks_rbac_writer" {
  scope                = azurerm_kubernetes_cluster.this.id
  role_definition_name = "Azure Kubernetes Service RBAC Writer"
  principal_id         = var.ci_identity_principal_id
}

# Lets the operator running `terraform apply` actually use kubectl — design.md D4.
resource "azurerm_role_assignment" "operator_aks_rbac_cluster_admin" {
  scope                = azurerm_kubernetes_cluster.this.id
  role_definition_name = "Azure Kubernetes Service RBAC Cluster Admin"
  principal_id         = data.azurerm_client_config.current.object_id
}
