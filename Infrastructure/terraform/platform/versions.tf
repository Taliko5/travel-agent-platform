terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # No remote backend configured — this design doesn't create a storage
  # account to hold it, and adding one would be a resource this pass never
  # decided. State is local; the repository's top-level .gitignore keeps
  # *.tfstate*, .terraform/ and *.tfvars out of the repository.
}

provider "azurerm" {
  features {}
}
