# Cluster state

The Azure resources destroyed and recreated on every session: the AKS
cluster itself, its node pool, the Key Vault secrets provider and managed
Prometheus add-ons, the Azure Monitor workspace, and the role assignments
that let CI and the cluster's own pull identity reach the platform state's
registry (design.md D10).

## Inputs from the platform state

This state never reads `Infrastructure/terraform/platform/` via
`terraform_remote_state` — there is no cross-state data source anywhere in
this directory (`grep -rn "terraform_remote_state" .` returns nothing). It
takes two plain string values as ordinary input variables, supplied at apply
time:

```
$ terraform apply \
    -var="acr_id=$(terraform -chdir=../platform output -raw acr_id)" \
    -var="ci_identity_principal_id=$(terraform -chdir=../platform output -raw ci_identity_principal_id)" \
    -var="region=$(terraform -chdir=../platform output -raw region)"
```

That is task 5.8's confirmation: because neither ID is a Terraform reference
into a resource this configuration declares, `terraform destroy` here has no
path to anything in the platform state — it can only ever destroy what this
state itself created.

## Feeding this state's output back to the platform state

`oidc_issuer_url` is this state's one output the platform state needs, to
complete the backend ServiceAccount's federated identity credential on its
second apply:

```
$ terraform -chdir=../platform apply \
    -var="aks_oidc_issuer_url=$(terraform output -raw oidc_issuer_url)"
```

See `Infrastructure/terraform/platform/README.md` for the full three-step
sequence this completes.

## Application routing add-on: two resources, not one

The App Routing add-on's Gateway API / Istio mode (design.md D2) needed two
separate mechanisms, because the `azurerm` provider (`~> 4.0`) can express
the add-on's base enablement but not the Gateway API layer on top of it:

- **Base enablement** — `azurerm_kubernetes_cluster.this`'s `web_app_routing`
  block (`cluster.tf`), with `default_nginx_controller = "None"` set
  explicitly so the provider's own default doesn't quietly deploy the
  managed-NGINX controller D2 rejects by name.
- **Gateway API / Istio mode** — `azapi_update_resource.app_routing_gateway_api`
  (`cluster.tf`), patching `properties.ingressProfile.gatewayAPI.installation`
  and `properties.ingressProfile.webAppRouting.gatewayAPIImplementations.appRoutingIstio.mode`
  directly against the `Microsoft.ContainerService/managedClusters@2026-04-01`
  API — the two properties `azurerm` has no attribute for. `design.md`'s D2
  mechanism update has the full citation trail (the ARM template reference,
  the Java SDK class, the AKS GA blog post) and the comparison against the
  two rejected alternatives (a full `azapi_resource`, a `local-exec`
  wrapper).

This is a new provider dependency — `azapi`, pinned in `versions.tf`,
first introduced by this patch and used nowhere else in this repository.
Not yet exercised against a live cluster; task 9.5's routing check is what
confirms `Infrastructure/helm/travel-agent/templates/gateway.yaml`'s
`Gateway` actually reaches something through this path rather than finding
nothing there.
