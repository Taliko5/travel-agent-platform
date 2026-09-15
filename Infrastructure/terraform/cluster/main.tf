# Holds everything this state creates (items 1-8 in design.md's inventory).
# Separate from the platform resource group by design (D10): this state's
# `terraform destroy` must never be able to reach that one — task 5.8 confirms
# below that nothing in this state makes that possible.
#
# Task 5.8: this state takes the platform state's outputs only as plain
# string-valued input variables (var.acr_id, var.ci_identity_principal_id),
# never via a `terraform_remote_state` data source. Neither ID is a Terraform
# reference to a resource declared in this configuration — they are opaque
# strings passed at apply time — so no resource or data source anywhere in
# this state's files can be reached by a `terraform destroy` run here.
# `grep -rn "terraform_remote_state" .` returns nothing in this directory.
resource "azurerm_resource_group" "cluster" {
  name     = var.resource_group_name
  location = var.region
  tags     = var.tags
}
