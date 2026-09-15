# design.md D4's extension, task 5.9. Grants the CI identity
# (azurerm_user_assigned_identity.ci, defined in the platform state) what it
# needs to authenticate against this cluster for `az aks get-credentials`
# (tasks.md 6.4) and the `helm upgrade --install` that follows it. Both
# assignments are scoped to the cluster resource, not a namespace — nothing
# in this design restricts the deploy step to one namespace.
#
# Deliberately not "Azure Kubernetes Service Cluster Admin Role": that grants
# every verb in every namespace, more than a single CI job's deploy step
# needs. Deliberately not a local-accounts kubeconfig: that reintroduces the
# kind of standing bearer credential D4's OIDC federation exists to avoid.

# Lets CI fetch kubeconfig via `az aks get-credentials`.
resource "azurerm_role_assignment" "ci_aks_cluster_user" {
  scope                = azurerm_kubernetes_cluster.this.id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = var.ci_identity_principal_id
}

# Lets CI's `helm upgrade --install` create and update the chart's objects.
# Only takes effect because azurerm_kubernetes_cluster.this has Azure RBAC
# for Kubernetes Authorization enabled (cluster.tf) — without that, this
# role assignment exists but nothing inside the API server evaluates it.
resource "azurerm_role_assignment" "ci_aks_rbac_writer" {
  scope                = azurerm_kubernetes_cluster.this.id
  role_definition_name = "Azure Kubernetes Service RBAC Writer"
  principal_id         = var.ci_identity_principal_id
}
