# Every value here is an identifier or a URL, matching platform/outputs.tf's
# convention. oidc_issuer_url feeds the platform state's second apply
# (Infrastructure/terraform/platform/README.md's three-step sequence).

output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "resource_group_name" {
  value = azurerm_resource_group.cluster.name
}

output "oidc_issuer_url" {
  value = azurerm_kubernetes_cluster.this.oidc_issuer_url
}

output "kubelet_identity_object_id" {
  value = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}

output "monitor_workspace_id" {
  value = azurerm_monitor_workspace.this.id
}
