## Context

`proposal.md` states the problem and the shape of the fix: split `main` (integration) from `release` (deploy), moving the whole `push` job in `.github/workflows/ci.yml` to trigger on `release` instead of `main`. This document decides the mechanics: how trust moves, how `release` advances, what a deploy may assume about the cluster, and what changes in `Infrastructure/terraform/platform/`.

Read directly from the files this change touches:

```
$ grep -n "branches:\|ref ==" .github/workflows/ci.yml
7:  branches: [main]
9:  branches: [main]
307:  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
```

`concurrency.group` is `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true` (ci.yml:11-14) — one group per branch, unconditionally cancelled. `identities.tf`'s `azurerm_federated_identity_credential.ci` names itself `github-actions-${var.ci_deploy_branch}` and trusts `subject = "repo:${var.github_repository}:ref:refs/heads/${var.ci_deploy_branch}"` — the branch is baked into both the resource name and the trust subject. `variables.tf`'s `ci_deploy_branch` defaults to `"main"`, and its description reads "must match the push job's gate (design.md D4: `github.ref == 'refs/heads/main'`)" — wrong the moment the gate changes unless updated in the same apply.

## Goals

See `proposal.md`'s "What Changes" — not restated here.

## Non-Goals

See `proposal.md`'s Non-Goals — not restated here.

## Decisions

### D1 — Publish and deploy move together to `release`

The `push` job keeps doing both things it does today — build/push images, then `helm upgrade --install` — gated on `release` instead of `main`.

**Rejected: build-once, deploy-many** (`main` publishes; `release` only deploys an already-published tag). Needs a second federated credential (separate `main`-trust and `release`-trust subjects) and an image-existence check, since `helm upgrade --install` without `--wait` succeeds even when the referenced tag doesn't exist — Helm confirms the manifest was accepted, not that a pod using it ever started. Adopting build-once-deploy-many later is additive, one more credential, so nothing here forecloses it.

### D2 — `release` advances only by a merge-commit pull request from `main`

The deployed SHA is the PR's merge commit; `main`'s tip is that commit's second parent, recoverable with `git rev-parse <merge-commit>^2`, which returns the `main` commit the merge brought in — traceability with no second recorded value.

**Rejected: squash or rebase.** Both create a commit on `release` with no matching commit on `main`, so a later `main`-into-`release` PR either re-presents the same diff or has nothing to merge — every sync becomes a diff to interpret, not a fast-forward-shaped merge.

**Rejected: direct fast-forward push.** No PR record, and it can't coexist with the pull-request-required ruleset (D8) this change relies on.

`on.pull_request.branches` gains `release` so the `main`-into-`release` PR shows CI checks; the `push` job itself stays gated on `push` events only (D1), so opening the PR does not deploy anything.

### D3 — Trust stays one federated credential; `ci_deploy_branch` becomes `release`

The credential's name embeds the branch it trusts, so changing `ci_deploy_branch`'s default from `"main"` to `"release"` forces Terraform to replace `azurerm_federated_identity_credential.ci` — new name, new `subject`. `azurerm_user_assigned_identity.ci` and its client ID are untouched: only what ref is trusted changes, not what authenticates. `variables.tf`'s description, which currently names the `main` gate, is updated in the same change.

**Rejected: two federated credentials.** Only useful under build-once-deploy-many (D1), not adopted here.

**Rejected: a GitHub Environment as the federation subject.** The repository is public, so Environments are available, but an Environment's branch rule only matters once a workflow can run against arbitrary refs (`workflow_dispatch`), which this change doesn't introduce. Deferred to the browser-triggered raise change in `docs/plan.md` Step 10.

### D4 — Concurrency: cancel-in-progress everywhere except `release`

The existing `concurrency.group` stays; `cancel-in-progress` becomes `${{ github.ref != 'refs/heads/release' }}` — cancel on every ref except `release`.

Helm doesn't roll back a killed upgrade, so a cancelled deploy can leave the release object `pending-upgrade`, blocking the next `helm upgrade --install` until manually resolved. D6's `--wait` makes deploys long enough for a second merge mid-deploy to be routine, not a corner case. GitHub's concurrency group holds at most one running and one pending run — a newer pending run replaces an older pending one, it doesn't stack — so disabling cancellation on `release` lets the in-flight deploy finish rather than creating unbounded queueing.

### D5 — A merge to `release` with no cluster raised fails the deploy step

No skip logic, no "does the cluster exist" pre-check. The merge is an explicit deploy intent, so "nothing to deploy to" should surface as a failure, not pass silently. A pre-check also couldn't do better than the deploy step itself: `docs/step9-raise-evidence.md` Task 10.4 shows `az aks get-credentials` failing with `AuthorizationFailed`, not a not-found error, after teardown — CI's cluster role assignments (`step9-aks-deployment` design.md D4) live in the cluster Terraform state and are destroyed with the cluster (that document's D10). A dedicated existence probe would hit the same authorization wall the real deploy already hits.

### D6 — Readiness: `--wait` plus `--timeout 10m`; failure diagnostics to the job log

`helm upgrade --install` gains `--wait --timeout 10m`. `--wait` blocks until the resources Helm manages report ready — for this chart, the backend and frontend Deployments' pods passing the readiness probes already defined in `backend-deployment.yaml` (`/health`, port 8000) and `frontend-deployment.yaml`. It does **not** cover whether the Gateway's `HTTPRoute` is actually routing traffic — that's outside what `--wait` inspects.

`10m` is provisional, not measured — replaced once the Migration Plan's step 4 records a real deploy duration.

On `if: failure()`, a diagnostics step writes `kubectl get pods`, `kubectl get events`, `kubectl describe pod`, and every container's logs including the `rag-ingest` init container, to the job log — the only record surviving a later teardown. This step runs only when the Helm deploy step itself failed, not on any earlier failure — D5's `AuthorizationFailed` case leaves no kubeconfig, so running `kubectl` there would only add noise. Each diagnostic command is best-effort, so one failing command doesn't stop the others from running.

`docs/step9-raise-evidence.md` Task 9.15 recorded a pod stuck at `Init:0/1` after a Key Vault grant was revoked, only reaching `Running`/`Ready` once the grant was restored — a pod state that a deploy without `--wait` would not observe, since `helm upgrade --install` would have reported success the moment the manifest was accepted.

**Rejected: `--atomic` or equivalent.** Reasons recorded in `proposal.md`'s Non-Goals; not repeated here.

### D7 — Pin Helm and `kubelogin` versions instead of `latest`

`ci.yml` currently installs `kubelogin` with `kubelogin-version: 'latest'` and Helm with no pin. Both become fixed versions, so flag behavior (`--wait`, `--timeout`) can't change underneath a later run with no corresponding commit to explain it. The version numbers themselves are not decided here — see Open Questions.

**Rejected: leave both unpinned.** Nothing requires the newest release of either tool.

### D8 — Manual GitHub ruleset on `release`; not committable as code

A ruleset requiring a pull request (0 approvals, solo repository), merge-commit method only (D2), blocking force-push and deletion. This is GitHub settings, not a repository file — a one-time manual step in the Migration Plan below. "PRs into `release` come only from `main`" is enforced nowhere; it's an operating rule (see Risks).

## Risks / Trade-offs

- `release` accumulates merge commits `main` never has — expected, the direct product of D2's traceability model.
- The deployed SHA (`release`'s merge commit) differs from `main`'s tip SHA at the same point in time; anything assuming "deployed" means `main`'s HEAD needs to read the merge commit's second parent instead.
- Nothing technical stops a PR into `release` from a branch other than `main` — D8's ruleset checks "is this a pull request," not its source branch. Operating rule only.
- `--wait` (D6) makes every deploy take as long as the workload needs to become ready, up to the timeout — longer than today's no-wait `helm upgrade --install`.

## Migration Plan

Every command below is run by the operator; this states what to run and what to check.

**0. Before this change is merged:** create `release` from current `main` (GitHub "New branch", or `git push origin main:release`) — a normal branch sharing `main`'s history, not an orphan (an orphan would make future `main`-into-`release` PRs impossible). Because that commit's `ci.yml` still triggers `push` only on `main`, creating the branch starts no workflow run. Check: no Actions run for `release`; `release` is 0 ahead/0 behind `main`. Then configure the D8 ruleset.

**1. Merge this change into `main`.** Check: the `main` run shows the `push` job `skipped`.

**2. Platform layer `terraform plan`.** Expected: `azurerm_federated_identity_credential.ci` replaced (name change, D3); possibly `backend_serviceaccount[0]` destroyed if no cluster is raised, unrelated to this change. Anything else is a stop condition.

**3. `terraform apply`.**

**4. At the next raise** (after the cluster layer apply and the platform layer's second apply, per `step9-aks-deployment` design.md D4's two-apply sequence): open and merge a `main`-into-`release` PR. Verify OIDC login succeeds, `--wait` completes, the job is green. Record the observations in `docs/`, including the measured deploy duration for D6.

**Why steps 1 and 3 must not be swapped.** Applying first replaces the federated credential to trust `release` while `ci.yml` on `main` still logs in expecting `main`'s trust — the old workflow's OIDC token presents a subject the replaced credential no longer trusts, breaking `main`'s CI for the window between the two steps.

## Open Questions

- **Pinned Helm and `kubelogin` versions (D7).** The plan was to read them from the successful deploy's "Set up Helm"/"Set up kubelogin" step logs, referenced in `docs/step9-raise-evidence.md`'s summary table as "Task 8.8" — but that file has no section logging those two steps' output, only a one-line summary of Task 8.8's outcome (RBAC Writer couldn't touch CRDs; CI widened to Cluster Admin). The version strings need to come from GitHub's own run log, not this file.
- **The measured deploy duration (D6).** Not available until Migration Plan step 4 runs.
- **Whether GitHub's ruleset UI offers "merge-commit method only" as a rule (D8).** Assumed available, not confirmed against the current editor.
- **The `deployment` spec delta.** Depends on `step9-aks-deployment` being archived first, so its `deployment` capability exists in main specs to modify.
