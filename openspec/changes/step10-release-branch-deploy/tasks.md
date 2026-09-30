## 1. Prerequisite

- [x] 1.1 [edit] Confirm `step9-aks-deployment` is archived and the `deployment` capability exists in main specs, since this change's `specs/deployment/spec.md` delta (MODIFIED + ADDED requirements) modifies it. Confirmed: `openspec/changes/archive/2026-09-30-step9-aks-deployment/` exists, and `openspec/specs/deployment/spec.md` exists.

## 2. Before Merging (Migration Plan step 0)

- [x] 2.1 [operator] Create `release` from current `main` — `git push origin main:release`, or GitHub's "New branch" from `main`. A normal branch sharing `main`'s history, not an orphan (design.md's Migration Plan step 0 explains why: an orphan branch has no common ancestor, which would make every future `main`-into-`release` pull request a conflict-everywhere merge). Check: no Actions run appears for `release` in the Actions tab; run `git fetch origin` then `git rev-list --left-right --count origin/main...origin/release`, expecting `0	0` — a branch created in the GitHub UI has no local `release` to diff against. Confirmed: `git ls-remote origin refs/heads/release refs/heads/main` returned the same SHA for both, `6e1bc743685cf7facaaaa83913c296b30d90a9fb` (commit "doc: add azure architecture (#21)"), and no Actions run appeared for `release`.
- [x] 2.2 [operator] Configure the D8 ruleset on `release` in GitHub repository settings: require a pull request (0 required approvals — solo repository), restrict the merge method to merge commits only, block force-push and branch deletion. Check by reopening the ruleset editor and reading back all four settings — there is no command output for this one.
- [x] 2.3 [operator] Open the Step 9 deploy run that succeeded against the archived `step9-aks-deployment` change and read its "Set up Helm", "Set up kubelogin", and "Set up kubectl" step logs for the version each installed (design.md's Open Questions: `docs/step9-raise-evidence.md` never recorded these, only that run's RBAC outcome). Recorded: "Set up Helm" logged `Installing v4.3.0` and `Helm tool version 'v4.3.0' has been cached`; "Set up kubelogin" logged `Added /opt/hostedtoolcache/kubelogin/0.2.19/x64/bin/linux_amd64/kubelogin to PATH`; "Set up kubectl" logged `'v0.2.19'`. Also noted in passing: `kubectl` was found unpinned (`version: latest`) in the same job. These are task 3.6's input.

## 3. Workflow Edits — `.github/workflows/ci.yml`

Each edit below is surgical: one clause or one step, not a rewrite of the job.

- [ ] 3.1 [edit] Add `release` to `on.push.branches` and `on.pull_request.branches` (currently `[main]` at both, lines 7 and 9), alongside `main` rather than replacing it — the workflow itself must trigger on either branch for `main`'s own jobs and the `main`-into-`release` PR's checks to keep running; which jobs actually act on which ref is governed separately by D1/D2 and by tasks 3.2–3.3 below.
- [ ] 3.2 [edit] `concurrency.cancel-in-progress` (line 14) changes from the literal `true` to `${{ github.ref != 'refs/heads/release' }}`; `concurrency.group` (line 12) is unchanged — D4.
- [ ] 3.3 [edit] The `push` job's `if` (line 307) changes `github.ref == 'refs/heads/main'` to `github.ref == 'refs/heads/release'`; the `&& github.event_name == 'push'` clause is unchanged — D1.
- [ ] 3.4 [edit] The "Deploy with Helm" step (line 378) gains `--wait=watcher --timeout 10m` on its `helm upgrade --install` invocation, and an explicit `id` (e.g. `helm-deploy`) so task 3.5's diagnostics step can key off its outcome — D6. `--wait=watcher` rather than bare `--wait`: Helm 4.3.0 documents `--wait` alone as the watcher strategy and the default without it as `hookOnly`, so writing the strategy explicitly keeps behavior fixed if that default changes.
- [ ] 3.5 [edit] Add a diagnostics step immediately after "Deploy with Helm", gated `if: failure() && steps.helm-deploy.outcome == 'failure'` — the explicit `failure()` is required to override the job's default skip-on-failure behavior, and keying on that specific step's outcome (rather than job-wide `failure()` alone) is what excludes an earlier failure such as D5's `AuthorizationFailed`, which leaves no kubeconfig for `kubectl` to use. Inside it, run `kubectl get pods`, `kubectl get events`, `kubectl describe pod`, and every container's logs including the `rag-ingest` init container's — each command suffixed `|| true` so one failing command doesn't stop the rest (the default shell already runs with `set -e`) — D6.
- [ ] 3.6 [edit] Pin Helm, kubelogin, and kubectl: the "Set up Helm" step (line 360) to `'v4.3.0'` (`with: version: 'v4.3.0'` on `azure/setup-helm@v4`); the "Set up kubectl" step (line 363) to `'v0.2.19'` (`with: version: 'v0.2.19'` on `azure/setup-kubectl@v4`); and the "Set up kubelogin" step's `kubelogin-version` (line 368) from `'latest'` to `'v0.2.19'` — all three per task 2.3's recorded result. `kubectl` is pinned alongside the other two because task 3.5's diagnostics step also runs it, and the spec requirement "Deploy Tooling Versions Are Version-Controlled" covers all deploy tooling, not Helm alone — D7.

## 4. Terraform Edit — `Infrastructure/terraform/platform/variables.tf`

- [ ] 4.1 [edit] `ci_deploy_branch`'s default changes from `"main"` to `"release"`; its description — which currently names the `push` job's `main` gate — is updated to describe the new `release` gate instead. No other Terraform file changes: `identities.tf`'s `azurerm_federated_identity_credential.ci` already reads this variable rather than hardcoding a branch, so it needs no edit — D3.

## 5. Spec and Docs

- [ ] 5.1 [edit] `openspec/specs/deployment/spec.md`: replace the placeholder Purpose ("TBD - created by archiving change step9-aks-deployment. Update Purpose after archive.") with one or two sentences stating what the `deployment` capability covers.
- [ ] 5.2 [edit] `docs/index.md`: update the sentence "The pipeline (`.github/workflows/ci.yml`) runs on every push and pull request to `main`" to name `release` too; update the `push` row of the CI jobs table (currently "Push to `main` only, after both build jobs") to the new gate; update the HCL comment `# resolves to: repo:Taliko5/travel-agent-platform:ref:refs/heads/main` to `refs/heads/release`; update the last sentence of "What Went Wrong" #2 (currently "This is part of why `docs/plan.md` Step 10 proposes separating integration from deploy triggers") to point at this change rather than describing the split as still-proposed.
- [ ] 5.3 [edit] `docs/plan.md` Step 10: mark the `main`/`release` split as in progress, pointing at `openspec/changes/step10-release-branch-deploy/`; note that this change adds readiness-gated deploy success and tooling-version pinning beyond Step 10's original one-paragraph description; leave the browser-triggered raise/teardown proposal as the remaining, still-undesigned item. Also update `docs/plan.md` Step 13's "Deploy:" bullet (currently `helm upgrade --install --atomic --wait` so a failed rollout reverts on its own) — `--wait` is now delivered by this change; `--atomic` was rejected here (point to this change's `proposal.md` Non-Goals) and Step 13 should revisit it only together with a way to keep diagnostics on a failed rollout, since `--atomic` removes failed pods before they can be diagnosed; also note that Helm 4 has no `--atomic` — its equivalent is `--rollback-on-failure`. And Step 13's "Supply chain:" bullet — the `kubelogin` pin and the new Helm pin are now delivered by this change; pinning third-party actions to commit SHAs and installing CRDs in `chart-lint` from a release tag stay in Step 13.
- [ ] 5.4 [edit] `openspec/changes/archive/2026-09-30-step9-aks-deployment/design.md` D4: append a dated 2026-09-30 addendum — a short note, not a rewrite — recording that the CI federated credential's trusted branch moves from `main` to `release`, per this change's design.md D3.

`docs/step7.md` is not edited — it stays as the historical record `proposal.md`'s Impact list already names it as.

## 6. Local Checks Before the PR

- [ ] 6.1 [operator] Run `openspec validate step10-release-branch-deploy`. Check: it reports no errors.
- [ ] 6.2 [operator] In `Infrastructure/terraform/platform`, run `terraform fmt -check` (check: no file listed in the output — a listed path means it's unformatted) and `terraform validate` (check: `Success! The configuration is valid.`).
- [ ] 6.3 [edit] Parse `.github/workflows/ci.yml` as YAML to confirm task 3's edits didn't break its syntax: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"`. Run against the file as it stands before task 3's edits, to confirm the baseline itself parses and the check works (`pyyaml` was not preinstalled in this environment and needed `pip install pyyaml` first):
  ```
  $ python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"
  OK
  ```
  Re-run the same command after task 3's edits land, and quote that output too.

## 7. Merge and Apply (Migration Plan steps 1–3)

- [ ] 7.1 [operator] Merge this change into `main`. Check: the resulting `main` Actions run shows the `push` job as `skipped`.
- [ ] 7.2 [operator] In `Infrastructure/terraform/platform`, run `terraform plan`. Expected: `azurerm_federated_identity_credential.ci` shows as forcing replacement (name change, D3); `backend_serviceaccount[0]` may additionally show as destroyed, but only if no cluster is currently raised — a pre-existing condition unrelated to this change. **Stop condition**: anything else appearing in the plan (design.md's Migration Plan step 2).
- [ ] 7.3 [operator] Run `terraform apply` for the platform layer.

Task 7.1 must complete before task 7.3 runs — never the reverse. design.md's Migration Plan explains why: applying first replaces the federated credential to trust `release` while `main`'s still-unmerged `ci.yml` logs in expecting `main`'s trust, so the old workflow's OIDC token presents a subject the replaced credential no longer accepts, breaking `main`'s CI for the gap between the two steps.

## 8. At the Next Raise (Migration Plan step 4)

- [ ] 8.1 [operator] Open a `main`-into-`release` pull request. Check: it shows CI checks (D2), and the `push` job does not run on the PR itself — it stays gated on push events only (D1). Merge it.
- [ ] 8.2 [operator] On the resulting `release` push run, check: the OIDC login step succeeds against the replaced credential; the "Deploy with Helm" step visibly waits (measurable wall-clock time, not an instant return) and completes within the timeout; the job is green end to end; and task 3.5's diagnostics step shows as skipped, confirming it stays off on a successful run.
- [ ] 8.3 [edit] Record the observations in `docs/`, including the measured deploy duration. If that measurement warrants it, replace D6's provisional `--timeout 10m` in `.github/workflows/ci.yml` with a value based on it.

## 9. Close Out

- [ ] 9.1 [edit] Tick every task above with the evidence that closed it — a commit, a run link, or quoted command output — following the pattern the archived `step9-aks-deployment/tasks.md` uses.
- [ ] 9.2 [operator] Once every task in Section 8 is checked off, archive this change: `openspec archive step10-release-branch-deploy`.
