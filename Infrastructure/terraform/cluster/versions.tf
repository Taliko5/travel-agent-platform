terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    # New dependency, not used anywhere else in this repository. Exists
    # solely to patch the one property azurerm has no attribute for: the
    # app-routing add-on's Gateway API/Istio mode on azurerm_kubernetes_cluster.this
    # (design.md D2's mechanism update, cluster.tf's azapi_update_resource).
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
  }

  # No remote backend, matching Infrastructure/terraform/platform/versions.tf —
  # this design doesn't create a storage account to hold one. State is local;
  # the repository's top-level .gitignore keeps *.tfstate*, .terraform/ and
  # *.tfvars out of the repository.
}

provider "azurerm" {
  features {}
}

# No configuration needed — authenticates the same way azurerm does (Azure
# CLI / environment / OIDC federation), reusing whatever session applied the
# rest of this state.
provider "azapi" {}
