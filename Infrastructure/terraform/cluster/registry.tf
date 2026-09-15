# Grants the cluster's own pull identity access to the platform state's ACR
# (design.md D4, task 5.5). This is the counterpart to platform's
# azurerm_role_assignment.ci_acr_push: CI pushes, the cluster's kubelet
# identity pulls. `az aks update --attach-acr` does exactly this role
# assignment under the hood — this is its Terraform equivalent.
resource "azurerm_role_assignment" "kubelet_acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}
