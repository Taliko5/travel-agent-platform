# Terraform equivalent of `az aks update --attach-acr` (design.md D4, task 5.5).
resource "azurerm_role_assignment" "kubelet_acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
  # Avoids a PrincipalNotFound race against Entra replication — design.md D4.
  skip_service_principal_aad_check = true
}
