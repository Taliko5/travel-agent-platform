# Step 10 — Release Branch Deploy Evidence

Evidence record for `openspec/changes/step10-release-branch-deploy`. Tasks 7.1–7.3
(Migration Plan steps 1–3: merge, plan, apply) are recorded here as they happen, in
the same style as `docs/step9-raise-evidence.md`.

<a id="task-7-1"></a>

## Task 7.1 — `main` no longer deploys

Run: <MAIN_RUN_URL>

The `push` job shows `skipped`.

<a id="task-7-2"></a>

## Task 7.2 — Platform plan, and drift found on the way

**First plan**, run without `-var="operator_object_id=..."` and before the updated
`main` was pulled into Cloud Shell. It showed:

- No change to `azurerm_federated_identity_credential.ci`.
- A destroy of `azurerm_role_assignment.operator_secrets_officer[0]` — the expected
  consequence of omitting `operator_object_id`, which `platform/README.md` already
  warns about.
- A create of `azurerm_role_assignment.backend_keyvault_secrets_user`.

**Cause of the create.** `docs/step9-raise-evidence.md` Task 9.15 deleted and
recreated the backend identity's "Key Vault Secrets User" role assignment with
`az role assignment delete`/`az role assignment create`. Terraform state still held
the original assignment's ID, `09c05d1e-c7aa-03b3-a36d-b7ea7d150d01`, while Azure
now held a different one for the same logical grant, `8b684465-da42-46aa-929c-4a24b6730b1e`.
Applying the plan as shown would have tried to create a duplicate assignment rather
than recognize the existing one.

**Fix, with nothing created or deleted in Azure:**

1. `terraform state show azurerm_role_assignment.backend_keyvault_secrets_user`
   confirmed the state held the stale ID.
2. State was backed up.
3. `terraform state rm azurerm_role_assignment.backend_keyvault_secrets_user`.
4. `terraform import` of the existing assignment ID, passed the same `-var` used
   for plan/apply.
   - A first import attempt failed with `Resource already managed by Terraform` —
     the stale entry was still in state at that point, before step 3 ran. Recorded
     here because it's part of the sequence, not a separate incident.

**Final plan, with `-var="operator_object_id=..."` supplied**, was exactly the
expected diff (design.md's Migration Plan step 2):

- `azurerm_federated_identity_credential.ci` replaced — name
  `github-actions-main` → `github-actions-release`, forces replacement; `subject`
  `refs/heads/main` → `refs/heads/release`.
- `azurerm_federated_identity_credential.backend_serviceaccount[0]` destroyed.

```
Plan: 1 to add, 0 to change, 2 to destroy.
```

<a id="task-7-3"></a>

## Task 7.3 — Apply

```
Apply complete! Resources: 1 added, 0 changed, 2 destroyed.
```

Post-apply check:

```
Name                    Subject
github-actions-release  repo:Taliko5/travel-agent-platform:ref:refs/heads/release
```

The CI identity itself (`azurerm_user_assigned_identity.ci`) was not replaced —
only the federated credential naming it was — so its client ID, and the
`AZURE_CLIENT_ID` repository variable that carries it, are unchanged.

<a id="task-8-1"></a>

## Task 8.1 — `main`-into-`release` pull request

PR #23, merged with a merge commit. The `push` job did not run on the PR.

<a id="task-8-2-first"></a>

## Task 8.2 — First deploy attempt: no cluster raised (design.md D5 observed)

Run: https://github.com/Taliko5/travel-agent-platform/actions/runs/36751262229,
attempt 1.

Azure login (OIDC) succeeded — the error later in the job names object id
`2785c1f0-588c-438c-9818-63422fd5307d`, the CI identity's principal ID, so the
`release`-scoped federated credential was accepted. The job then failed at "Get
AKS credentials" with `AuthorizationFailed` on `listClusterUserCredential` for
`travel-agent-cluster`/`travel-agent`; `az aks show` confirmed
`ResourceGroupNotFound`. The failure was reported, not skipped — matching the
spec requirement "A Deploy Fails When No Target Exists." The diagnostics step
did not run, since the Helm step never ran (D6).

**Raise, to get a cluster for attempt 2:**

```
Apply complete! Resources: 11 added, 0 changed, 0 destroyed.
```

Platform second apply, with both `operator_object_id` and `aks_oidc_issuer_url`
passed, planned exactly `azurerm_federated_identity_credential.backend_serviceaccount[0]`
created against the new cluster's issuer:

```
Plan: 1 to add, 0 to change, 0 to destroy.
```

`az aks show` reported `provisioningState`: `Succeeded`.

<a id="task-8-2-second"></a>

## Task 8.2 — Second attempt: cluster raised

Same run, attempt 2 ("Re-run all jobs"). The job succeeded. "Deploy with Helm"
took <HELM_DURATION>; the diagnostics step was skipped: <DIAG_SKIPPED>.

`kubectl get pods` afterward: the backend, frontend, and both gateway pods were
all `1/1 Running`, `0` restarts.

**Also done on this raise** (`docs/plan.md` Step 10 "Also do on the next raise"):

- **PVC survives pod replacement.** Before: pod
  `travel-agent-backend-866d698cb9-vcmrt`, `rag-ingest` log: "Loaded 4 documents"
  / "Saved 4 documents to Chroma at rag/chroma_db". After `kubectl delete pod`,
  the new pod `travel-agent-backend-866d698cb9-gdqhq` went `Init:0/1` →
  `PodInitializing` → `Running` → `1/1`; its `rag-ingest` log: "Chroma store at
  rag/chroma_db already has documents, skipping ingestion". The backend log
  shows `GET /health` returning `200`.
- **Node OS disk.** `az disk list` on the node resource group listed only the
  PVC's disk (`pvc-86083bb9-3abe-48c4-a18e-82b9577a62ce`, `StandardSSD_LRS`).
  `az aks nodepool list` showed pool `system`, `OsDiskType` `Managed`, `128` GB,
  `Standard_D2s_v7`. AKS node OS disks belong to the VM scale set and are not
  listed by `az disk list`; the OS disk's storage SKU was not captured before
  teardown and remains open.

**Teardown:**

```
Destroy complete! Resources: 11 destroyed.
```

`travel-agent-cluster` and `MC_travel-agent-cluster_travel-agent_germanywestcentral`
both returned `ResourceGroupNotFound`; `travel-agent-platform` reported
`provisioningState`: `Succeeded`.

**Found on the way, not part of this task's own checks:**
`Infrastructure/terraform/cluster/README.md`'s example for the platform second
apply passed only `aks_oidc_issuer_url`, omitting `operator_object_id` — which
`platform/README.md` says must be passed on every apply. Fixed in that file.
