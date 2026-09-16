# Step 9 — Raise Evidence

Evidence record for `openspec/changes/step9-aks-deployment`. Section 7 (Pre-Apply
Gate) requires the go-ahead for each specific raise to be recorded here, before
anything in Section 8 runs. Section 9's 15 verification tasks may be completed
incrementally across multiple raise/teardown cycles (tasks.md Section 7.5); each
cycle gets its own dated entry below.

## Cost inventory re-confirmation (task 7.1)

Checked `design.md`'s "Azure resources this change would create, and what each
costs" (items 1–13) against the resource blocks actually written in
`Infrastructure/terraform/platform/` and `Infrastructure/terraform/cluster/`
(Sections 4 and 5). Commands run and what they showed:

```
$ grep -n '^resource "' Infrastructure/terraform/platform/*.tf
platform/main.tf:4:resource "azurerm_resource_group" "platform"
platform/main.tf:10:resource "random_string" "suffix"
platform/keyvault.tf:11:resource "azurerm_key_vault" "this"
platform/keyvault.tf:34:resource "azurerm_role_assignment" "operator_secrets_officer"
platform/identities.tf:6:resource "azurerm_user_assigned_identity" "ci"
platform/identities.tf:13:resource "azurerm_federated_identity_credential" "ci"
platform/identities.tf:24:resource "azurerm_role_assignment" "ci_acr_push"
platform/identities.tf:31:resource "azurerm_user_assigned_identity" "backend"
platform/identities.tf:41:resource "azurerm_role_assignment" "backend_keyvault_secrets_user"
platform/identities.tf:51:resource "azurerm_federated_identity_credential" "backend_serviceaccount"
platform/registry.tf:4:resource "azurerm_container_registry" "this"

$ grep -n '^resource "' Infrastructure/terraform/cluster/*.tf
cluster/cluster.tf:2:resource "azurerm_kubernetes_cluster" "this"
cluster/cluster.tf:73:resource "azapi_update_resource" "app_routing_gateway_api"
cluster/monitoring.tf:7:resource "azurerm_monitor_workspace" "this"
cluster/monitoring.tf:24:resource "azurerm_monitor_data_collection_endpoint" "prometheus"
cluster/monitoring.tf:32:resource "azurerm_monitor_data_collection_rule" "prometheus"
cluster/monitoring.tf:60:resource "azurerm_monitor_data_collection_rule_association" "prometheus"
cluster/main.tf:13:resource "azurerm_resource_group" "cluster"
cluster/registry.tf:6:resource "azurerm_role_assignment" "kubelet_acr_pull"
cluster/role-assignments.tf:14:resource "azurerm_role_assignment" "ci_aks_cluster_user"
cluster/role-assignments.tf:24:resource "azurerm_role_assignment" "ci_aks_rbac_writer"
```

Mapped against the inventory:

| Item | Resource | Found in Terraform | Match |
|---|---|---|---|
| 1 | Resource group (cluster) | `cluster/main.tf` `azurerm_resource_group.cluster` | Yes |
| 2 | AKS cluster, Free tier | `cluster/cluster.tf` `azurerm_kubernetes_cluster.this`, `sku_tier = "Free"` | Yes |
| 3 | System node pool, 2 × `Standard_D4as_v5` | `cluster/variables.tf` `node_count` default `2`, `node_vm_size` default `"Standard_D4as_v5"` | Yes |
| 4 | 2 × node OS disk, Premium SSD | No `os_disk_type`/`os_disk_size_gb` set on `default_node_pool` — provider default, left open exactly as the inventory's P6/P10 split and task 8.7 anticipate | Yes (deliberately unpinned) |
| 5 | Node resource group (`MC_…`) | Not a Terraform resource — created by AKS, matching the inventory's own "Created by AKS, not by us" note | Yes |
| 6 | Standard Load Balancer (AKS-managed) | No `azurerm_lb` resource anywhere in `cluster/` — AKS-managed, matching the inventory | Yes |
| 7 | Standard static public IPv4 | No `azurerm_public_ip` resource anywhere in `cluster/` — AKS-managed, matching the inventory | Yes |
| 8 | Azure Monitor workspace | `cluster/monitoring.tf` `azurerm_monitor_workspace.this` | Yes |
| 9 | Resource group (platform) | `platform/main.tf` `azurerm_resource_group.platform` | Yes |
| 10 | ACR, Basic | `platform/registry.tf` `azurerm_container_registry.this`, `sku = "Basic"`, `admin_enabled = false` | Yes |
| 11 | Key Vault (standard) | `platform/keyvault.tf` `azurerm_key_vault.this`, `sku_name = "standard"`, `soft_delete_retention_days = 90` | Yes |
| 12 | CI managed identity + federated credential | `platform/identities.tf` `azurerm_user_assigned_identity.ci` + `azurerm_federated_identity_credential.ci` | Yes |
| 13 | Backend managed identity + federated credential | `platform/identities.tf` `azurerm_user_assigned_identity.backend` + `azurerm_federated_identity_credential.backend_serviceaccount` | Yes |

**Result: no discrepancy.** All 13 inventoried items are accounted for by an
actual resource block (or, for items 5–7, by the documented absence of one,
which the inventory itself already states). Nothing in Sections 4–5 declares a
resource the inventory doesn't list, and nothing in the inventory lacks a
corresponding definition. No re-approval of the inventory is triggered.

**Adjacent finding, not a cost-inventory discrepancy, flagged rather than fixed
silently (this pass does not touch resource definitions):**
`Infrastructure/terraform/cluster/variables.tf`'s `kubernetes_version` variable
description reads *"task 8.3 queries which versions this region actually
offers... Set explicitly on subsequent applies once 8.3 has run."* Under the
current `tasks.md` numbering the region-version-query task is **8.4**, not 8.3
— the comment was written before a task 8.2 (repository Variables) was
inserted into Section 8 and everything after it shifted down by one. The
description's own cross-reference is stale. Does not affect task 7.1's result
(item 4/the version question is still correctly left unpinned), but is a real
inconsistency for whoever next edits Section 8's numbering or reads that
variable's description looking for the current task number.

## Approval record (tasks 7.2 / 7.3)

**Presented:** the full resource inventory in `design.md`'s "Azure resources
this change would create, and what each costs" section, items 1–13 (see table
above for the re-confirmation against Sections 4–5).

**Expected cost while the cluster is up:** ≈ $0.48/hour (design.md's "Cost
floor while the cluster is up": items 3 + 4 + 6 + 7 = $0.416 + $0.031 + $0.025
+ $0.005 ≈ $0.48/hour, before metrics ingestion and egress).

**Expected standing cost after teardown:** ≈ $5/month — item 10 (ACR, Basic)
alone. Everything else in the inventory is free at rest.

**Intended session length / cadence:** the work in Sections 8–10 will be spread
across roughly 7 calendar days, done in multiple separate sessions rather than
one continuous sitting. The cluster is raised only while actively being worked
on, and torn down (Section 10, full `terraform destroy` of the cluster state)
whenever work pauses, however briefly. Explicitly clarified with the owner:
this is **not** 7 days of the cluster running continuously — it is a
raise/work/teardown cycle repeated across roughly 7 calendar days, with the
cluster's actual up-time being the sum of the individual working sessions, not
the elapsed calendar span.

**Go-ahead:** the owner's approval — given in Japanese conversation, rendered
in English here as "go-ahead" per repo convention — followed the cost
breakdown and the session-length/cadence point above being presented and
confirmed, and is conditional on stopping the cluster (a full Section 10
teardown) whenever work pauses. Tasks.md's new 7.5.1 restates that same
condition as an operational rule for this sequence. Approval was obtained by
the owner (noriko) outside this session; recorded here per task 7.3, not
re-solicited in this session per the owner's instruction.

**Date:** 2026-09-14
**Commit:** `4e0cc6956bdf10337f163dd44cd9252e59ddb885` (branch `feat/task-9`)

This approval authorizes the specific raise described above — the resource
inventory as it stands at this commit, at this cost, for this session cadence.
Per task 7.4, it is not standing authorization for any later raise; each
subsequent raise in the multi-day sequence needs its own record here (tasks.md
7.5 governs which of Sections 8–10 repeat on those later raises).

## Raise/teardown cycle log

Each cycle's entry goes here as it happens, recording: which of tasks 8.1–8.8
actually ran that cycle (per 7.5.3, later cycles start at 8.6), which of
9.1–9.15 were attempted and their result, and which of 10.1–10.6 were run at
that cycle's teardown (per 7.5.5, interim teardowns need only 10.1–10.2; the
final teardown needs all six).

### Cycle 1 — 2026-09-14

**Pre-flight: active subscription/tenant confirmed.** Before any billable task
ran, the owner confirmed the Cloud Shell session's active subscription and
tenant match the repository's `AZURE_TENANT_ID`/`AZURE_SUBSCRIPTION_ID`
Variables (task 6.7), closing design.md's open "which subscription" question
for this session:

Retrieved with `az account show --query '{tenantId:tenantId, subscriptionId:id,
subscriptionName:name}' -o table` in Cloud Shell. The owner confirmed both
values match what is already stored as the `AZURE_TENANT_ID` and
`AZURE_SUBSCRIPTION_ID` repository Variables (task 6.7) — not restated here as
raw values, per the Working Agreement's "never restate figures" rule; those
Variables are the single source of truth. Not independently re-verified from
this environment (no `gh` CLI/token, same limitation noted at task 6.7).

**Task 8.1 — platform state applied, run in Azure Cloud Shell.**

Command:
```
cd Infrastructure/terraform/platform
terraform init
terraform apply -var="operator_object_id=$(az ad signed-in-user show --query id -o tsv)"
```

Output, as pasted back by the owner (the `terraform init` transcript was not
separately captured and is not recorded here):

```
Warning: Argument is deprecated

  with azurerm_key_vault.this,
  on keyvault.tf line 18, in resource "azurerm_key_vault" "this":
  18:   enable_rbac_authorization = true

This property has been renamed to `rbac_authorization_enabled` and will be
removed in v5.0 of the provider

Apply complete! Resources: 10 added, 0 changed, 0 destroyed.

Outputs:

acr_id = "/subscriptions/c7927c9d-c486-4c11-bab4-19db99e220b6/resourceGroups/travel-agent-platform/providers/Microsoft.ContainerRegistry/registries/travelagentacr52f2y82s"
acr_login_server = "travelagentacr52f2y82s.azurecr.io"
backend_federated_credential_configured = false
backend_identity_client_id = "f2739b2d-73ba-48c1-a843-8cbfea73cf5f"
backend_identity_principal_id = "d34674d1-c3c0-4a18-a6ec-8aa749fb39af"
ci_identity_client_id = "c6f7b5b4-846f-4218-a3c7-b48bcc037993"
ci_identity_principal_id = "2785c1f0-588c-438c-9818-63422fd5307d"
key_vault_id = "/subscriptions/c7927c9d-c486-4c11-bab4-19db99e220b6/resourceGroups/travel-agent-platform/providers/Microsoft.KeyVault/vaults/travel-agent-kv-52f2y82s"
key_vault_name = "travel-agent-kv-52f2y82s"
key_vault_secret_object_name = "google-api-key"
key_vault_tenant_id = "18ff101d-9da4-499d-acc0-e9dbef4f4d8f"
region = "germanywestcentral"
resource_group_name = "travel-agent-platform"
```

`backend_federated_credential_configured = false` is expected at this stage —
`aks_oidc_issuer_url` is still empty on this first apply, so
`azurerm_federated_identity_credential.backend_serviceaccount` was correctly
skipped (`count = 0`). Task 8.6.1 is what flips this to `true`, after the
cluster state exists.

**Task 8.2 — repository Variables set.** The remaining four CI repository
Variables — `AZURE_CLIENT_ID`, `ACR_LOGIN_SERVER`, `BACKEND_IDENTITY_CLIENT_ID`,
`KEY_VAULT_NAME` — were set from the corresponding outputs above
(`ci_identity_client_id`, `acr_login_server`, `backend_identity_client_id`,
`key_vault_name` respectively). Values not restated here — already captured
once in the output block above. Not independently verified from this
environment (no `gh` CLI/token, same limitation noted at task 6.7).

**Task 8.3 — secret set out-of-band, run in Azure Cloud Shell.**

Command:
```
cd Infrastructure/terraform/platform
az keyvault secret set --vault-name "$(terraform output -raw key_vault_name)" --name "$(terraform output -raw key_vault_secret_object_name)" --value "<redacted>" --query "{name:name, enabled:attributes.enabled}" -o table
```

Result: `name: google-api-key, enabled: True`.

The secret's value is never recorded here, by design — `design.md` D5 states
the value is set out-of-band and never enters Terraform state or the
repository, and task 4.6 confirmed no `azurerm_key_vault_secret` resource
exists in `platform/` for exactly this reason. It was never typed into this
chat or shown to Claude Code either.

**Verification (this task's own requirement): the value appears in no
repository file and no Terraform state file.** Run by the owner directly in
Azure Cloud Shell, not by Claude Code:
```
grep -r "<the secret value>" ~/travel-agent-platform
grep "<the secret value>" Infrastructure/terraform/platform/terraform.tfstate
```
Both returned zero matches.

**Task 8.4 — supported Kubernetes versions queried (partial), run in Azure
Cloud Shell.**

Command:
```
az aks get-versions --location germanywestcentral --output table
```

Result: versions **1.34.0 through 1.36.3** are listed under SupportPlan
`KubernetesOfficial, AKSLongTermSupport` — standard support, no extra cost.
Versions **1.33.13 and below** show only `AKSLongTermSupport` — out of
standard support; using one of those would mean opting into AKS's paid Long
Term Support plan.

This settles `design.md` D2's regional-propagation concern: the region
already offers up through 1.36.3, matching the global supported-version
table with no lag observed. It also surfaces a cost consideration D2 didn't
originally anticipate — the standard/LTS support-plan split — noted here for
a task 8.7/D2 follow-up if relevant; not acted on in this entry.

`kubernetes_version` remains `null` for task 8.6's upcoming apply, per this
variable's own documented plan (`cluster/variables.tf`). Which version the
provider actually selects on that apply will be recorded here as a follow-up
entry after 8.6, then pinned explicitly into `cluster/variables.tf`'s default
for subsequent applies in this raise/teardown sequence (task 7.5.2). Task 8.4
is not yet complete — the "record which version the cluster is created at"
half is still open.

**Task 8.5 — 2-vCPU node pool probe and SKU correction, run in Azure Cloud
Shell.**

Two `az aks create` probes were run in a throwaway resource group,
`aks-vcpu-probe-rg`, deleted immediately after each test. The exact `az aks
create` invocations were not pasted into this chat and are not reproduced
verbatim here — the results below are as reported by the owner:

- `Standard_D2as_v5`: rejected — `BadRequest`, *"not allowed in your
  subscription in location germanywestcentral."* A subscription-level
  restriction on the entire Dasv5 (AMD, v5) family in this region, not the
  2-vCPU system-pool policy `design.md` D14 quotes. `Standard_D4as_v5` —
  this design's originally-chosen SKU, same family — would have failed
  task 8.6's apply for the same reason.
- `Standard_D2s_v7` (2 vCPU, confirmed in the allowed list): succeeded —
  the System-mode node pool provisioned, `provisioningState: Succeeded`.

**SKU correction.** `Standard_D4as_v5` replaced by `Standard_D4s_v7` (Intel,
v7 generation, same 4 vCPU / 16 GiB floor) as `cluster/variables.tf`'s
`node_vm_size` default, for the subscription-availability reason above.
Price query, run twice independently: first by the owner via `curl` in Azure
Cloud Shell against the public Azure Retail Prices API; then re-confirmed by
Claude Code via WebFetch against the same API, before the figure went into
`design.md`. Both runs returned the same result:

```
GET https://prices.azure.com/api/retail/prices?$filter=armRegionName eq 'germanywestcentral' and armSkuName eq 'Standard_D4s_v7' and priceType eq 'Consumption'
```

Result: `Standard_D4s_v7`, Linux, Consumption → **$0.305/hour** (Windows and
Spot meters also returned by the same query, not used).

**Go-ahead:** the owner reviewed the SKU-availability finding and the
corrected cost floor above and approved proceeding, conditional on the same
Section 10 teardown discipline already governing this raise/teardown
sequence (task 7.5.1) — the same condition task 7.3's original go-ahead was
made on.

**Date:** 2026-09-15

**Tasks 8.4, 8.6, 8.7 — cluster state raised, Kubernetes version and node OS
disk recorded. Run in Azure Cloud Shell, 2026-09-16.**

**Task 8.4 — Kubernetes version.** `kubernetes_version` left `null` for this
first apply, per `cluster/variables.tf`'s own documented plan. The
provider's default resolved to:

```
kubernetes_version = "1.35"
current_kubernetes_version = "1.35.7"
```

(from `terraform state show azurerm_kubernetes_cluster.this`.)

**Task 8.6 — cluster state apply, three attempts.**

*Attempt 1* failed on two independent errors:

```
Error: ... unexpected status 400 (400 Bad Request) ...
"code": "ErrCode_InsufficientVCPUQuota"
```

```
Error: ... unexpected status 409 (409 Conflict) ...
"MissingSubscriptionRegistration: The subscription is not registered to
use namespace 'Microsoft.Monitor'."
```

State after attempt 1: only `azurerm_resource_group.cluster` and
`azurerm_monitor_data_collection_endpoint.prometheus` existed — both
free/non-billable, nothing else created.

The node SKU was then corrected `Standard_D4s_v7` → `Standard_D2s_v7` to
fit this subscription's 4-vCPU regional quota ceiling — full reasoning and
the price recomputation already recorded in `design.md` D14's 2026-09-16
addendum, not repeated here.

*Attempt 2*, after the SKU fix but before `Microsoft.Monitor` was
registered: `azurerm_kubernetes_cluster.this` and
`azapi_update_resource.app_routing_gateway_api` were created successfully
(the `azapi` resource completed after 3m7s, since it depends on the
cluster's resource ID) — billing started at this point. It then failed
again on `azurerm_monitor_workspace.this`, the same
`MissingSubscriptionRegistration` error as attempt 1 — the provider had not
actually been registered yet.

Fixed via `az provider register --namespace Microsoft.Monitor` in Cloud
Shell, confirmed with:

```
$ az provider show --namespace Microsoft.Monitor --query registrationState -o tsv
Registered
```

No repository change involved.

*Attempt 3* succeeded:

```
Apply complete! Resources: 3 added, 1 changed, 0 destroyed.
```

Started 19:41, finished 19:54 (2026-09-16). This 13-minute window is only
the final invocation — the cluster itself (`azurerm_kubernetes_cluster.this`)
was actually created during attempt 2 above, so the true timeline is three
attempts across the session, not one continuous 13-minute build.

Final `terraform state list` (11 resources, matching this repo's own count
of `resource` blocks across `cluster/*.tf`):

```
azapi_update_resource.app_routing_gateway_api
azurerm_kubernetes_cluster.this
azurerm_monitor_data_collection_endpoint.prometheus
azurerm_monitor_data_collection_rule.prometheus
azurerm_monitor_data_collection_rule_association.prometheus
azurerm_monitor_workspace.this
azurerm_resource_group.cluster
azurerm_role_assignment.ci_aks_cluster_user
azurerm_role_assignment.ci_aks_rbac_writer
azurerm_role_assignment.kubelet_acr_pull
azurerm_role_assignment.operator_aks_rbac_cluster_admin
```

(plus `data.azurerm_client_config.current`, a data source, not a resource.)

Final `terraform output`:

```
cluster_name = "travel-agent"
kubelet_identity_object_id = "8dcf9a8a-6074-423c-af40-a739c0203491"
monitor_workspace_id = ".../Microsoft.Monitor/accounts/travel-agent-metrics"
oidc_issuer_url = "https://germanywestcentral.oic.prod-aks.azure.com/18ff101d-9da4-499d-acc0-e9dbef4f4d8f/f5675991-3c9e-4edc-9b54-4c7e776b69ba/"
resource_group_name = "travel-agent-cluster"
```

**Task 8.7 — node OS disk.** `terraform state show
azurerm_kubernetes_cluster.this`:

```
os_disk_size_gb = 128
os_disk_type = "Managed"
```

Settles `design.md`'s Open Question two ways: the disk is not ephemeral,
so the disk cost line in the cost table applies rather than being removed;
128 GiB matches the P10 tier already priced there, assuming Premium SSD
(AKS's typical OS-disk default) — the SKU tier itself is not independently
re-confirmed against the actual disk (e.g. via `az disk list`), consistent
with this design's existing "not verified, here's what would settle it
further" convention rather than stated as a confirmed fact.
