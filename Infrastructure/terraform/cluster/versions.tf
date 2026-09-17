terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    # New dependency, used only by cluster.tf's azapi_update_resource — design.md D2.
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
  }

  # No remote backend; state is local — design.md D10.
}

provider "azurerm" {
  features {}
}

# No configuration needed — authenticates the same way azurerm does (Azure
# CLI / environment / OIDC federation), reusing whatever session applied the
# rest of this state.
provider "azapi" {}
