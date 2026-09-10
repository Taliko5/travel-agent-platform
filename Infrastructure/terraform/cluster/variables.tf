variable "region" {
  description = <<-EOT
    Azure region for every resource in this state (design.md D12, task 5.7).
    Must match Infrastructure/terraform/platform/'s region exactly — pass
    `-var="region=$(terraform -chdir=../platform output -raw region)"` at
    apply time rather than relying on both defaults staying in sync by hand.
  EOT
  type        = string
  default     = "germanywestcentral"
}

variable "resource_group_name" {
  description = "Cluster resource group name — holds everything this state creates (design.md D10). Destroyed on every teardown."
  type        = string
  default     = "travel-agent-cluster"
}

variable "cluster_name" {
  description = "AKS cluster name."
  type        = string
  default     = "travel-agent"
}

variable "kubernetes_version" {
  description = <<-EOT
    Kubernetes minor.patch version. Left null so the provider's own default
    applies on first apply — task 8.3 queries which versions this region
    actually offers and records the version the cluster is created at
    (design.md's "not verified" note on regional version availability).
    Set explicitly on subsequent applies once 8.3 has run.
  EOT
  type        = string
  default     = null
}

variable "node_count" {
  description = "System node pool size — the documented AKS minimum node count (design.md D14). A variable so task 9.1's capacity measurement can change it without a rewrite."
  type        = number
  default     = 2
}

variable "node_vm_size" {
  description = "System node pool VM size — the documented AKS minimum system-pool SKU, 4 vCPU / 16 GiB (design.md D14). A variable for the same reason as node_count."
  type        = string
  default     = "Standard_D4as_v5"
}

variable "acr_id" {
  description = "Resource ID of the platform state's azurerm_container_registry.this (its acr_id output). Grants the cluster pull access (design.md D4, task 5.5). Required — this state never creates its own registry."
  type        = string
}

variable "ci_identity_principal_id" {
  description = "Principal (object) ID of the platform state's azurerm_user_assigned_identity.ci (its ci_identity_principal_id output). Granted AKS-scoped access here (design.md D4's extension, task 5.9)."
  type        = string
}

variable "tags" {
  description = "Common tags applied to every resource in this state."
  type        = map(string)
  default = {
    project    = "travel-agent-platform"
    managed-by = "terraform"
    state      = "cluster"
  }
}
