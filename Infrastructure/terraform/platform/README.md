# Platform state

The Azure resources that outlive a cluster: resource group, container
registry, Key Vault, and the two identities CI and the backend authenticate
with. Applied once, not part of the routine raise/destroy cycle — that's
`Infrastructure/terraform/cluster/`, a separate state so that its
`terraform destroy` can never reach anything here (design.md D10).

## Applied twice, not once

The backend's federated identity credential needs the AKS cluster's OIDC
issuer URL, which doesn't exist until `Infrastructure/terraform/cluster/`
has been applied — and that state, in turn, needs this one's outputs (the
registry ID, the vault name) to attach to. The order is:

1. `terraform apply` here, with `aks_oidc_issuer_url` left at its default
   (`""`). Everything is created except the backend's federated identity
   credential, which is skipped (`count = 0`) — `terraform output
   backend_federated_credential_configured` reads `false`.
2. Apply `Infrastructure/terraform/cluster/`, feeding it this state's
   `acr_id`, `key_vault_id`, `key_vault_name` and `key_vault_tenant_id`
   outputs.
3. Apply here again with `-var="aks_oidc_issuer_url=$(terraform -chdir=../cluster output -raw oidc_issuer_url)"`.
   The federated identity credential is created on this second apply, and
   `backend_federated_credential_configured` reads `true`.

Nothing is destroyed or recreated by the second apply — every other
resource in this state is untouched, since only the one conditional
resource depends on the new variable.

## What this state deliberately doesn't do

- **Doesn't create the secret's value.** `GOOGLE_API_KEY` is set with
  `az keyvault secret set --vault-name $(terraform output -raw
  key_vault_name) --name $(terraform output -raw
  key_vault_secret_object_name) --value <key>`, run by an operator, never by
  Terraform (design.md D5). There is no `azurerm_key_vault_secret` resource
  in this state.
- **Doesn't grant CI access to the AKS cluster.** `azurerm_role_assignment`
  scoped to the cluster needs the cluster to exist; that grant lives in
  `Infrastructure/terraform/cluster/`, against this state's
  `ci_identity_principal_id` output.
