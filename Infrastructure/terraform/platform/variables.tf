variable "region" {
  description = "Azure region for every resource in this state. design.md D12."
  type        = string
  default     = "germanywestcentral"
}

variable "resource_group_name" {
  description = "Platform resource group name — holds everything this state creates (design.md D10)."
  type        = string
  default     = "travel-agent-platform"
}

variable "acr_base_name" {
  description = "Base name for the container registry; a random suffix is appended for global uniqueness. ACR names must be 5-50 alphanumeric characters, no hyphens."
  type        = string
  default     = "travelagentacr"
}

variable "key_vault_base_name" {
  description = "Base name for the Key Vault; a random suffix is appended for global uniqueness. Vault names must be 3-24 characters, alphanumeric and hyphens."
  type        = string
  default     = "travel-agent-kv"
}

variable "key_vault_secret_object_name" {
  description = "Name of the GOOGLE_API_KEY secret object in the vault. Matches the k8s Secret key name so nothing downstream has to translate between them (design.md D5)."
  type        = string
  default     = "google-api-key"
}

variable "github_repository" {
  description = "owner/repo GitHub Actions federates against (design.md D4)."
  type        = string
  default     = "Taliko5/travel-agent-platform"
}

variable "ci_deploy_branch" {
  description = "Branch the CI federated credential trusts — must match the push job's gate (design.md D4: github.ref == 'refs/heads/main')."
  type        = string
  default     = "main"
}

variable "backend_namespace" {
  description = "Kubernetes namespace the backend ServiceAccount is federated for. The chart's templates carry no namespace, so this must match whatever `helm install -n` (or its default) actually targets."
  type        = string
  default     = "default"
}

variable "backend_service_account_name" {
  description = "Must match Infrastructure/helm/travel-agent/values.yaml's serviceAccount.name."
  type        = string
  default     = "travel-agent-backend"
}

variable "aks_oidc_issuer_url" {
  description = <<-EOT
    The AKS cluster's OIDC issuer URL, an output of Infrastructure/terraform/cluster/
    (design.md D5). Empty by default because this state is applied before the
    cluster exists (D10's platform-before-cluster sequencing) — the backend's
    federated identity credential is not created until this is supplied on a
    second apply, after Section 5 stands the cluster up. See README.md.
  EOT
  type        = string
  default     = ""
}

variable "operator_object_id" {
  description = <<-EOT
    Entra object ID of the human who will run `az keyvault secret set` to
    supply GOOGLE_API_KEY's value out-of-band (design.md D5 — the value never
    enters Terraform). Optional: leave null and grant access separately if
    the operator prefers `az role assignment create` by hand.
  EOT
  type        = string
  default     = null
}

variable "tags" {
  description = "Common tags applied to every resource in this state."
  type        = map(string)
  default = {
    project    = "travel-agent-platform"
    managed-by = "terraform"
    state      = "platform"
  }
}
