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
