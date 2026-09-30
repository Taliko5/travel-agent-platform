## Why

`docs/plan.md`'s Step 10 already names the problem: the single `push` job on `main` conflates "did the code merge cleanly" with "deploy this to whatever cluster happens to be raised right now." `docs/step9-raise-evidence.md` Task 10.4 and `docs/index.md`'s "What Went Wrong" #2 record the concrete result — a push to `main` while no cluster is raised turns CI red for a reason unrelated to the commit. Splitting integration from deployment removes that false signal: `main` stays green on its own merits, and a deploy happens only when someone deliberately merges into `release`.

## What Changes

- Scope is the main/release split only. `docs/plan.md` Step 10's browser-triggered raise/teardown proposal and "Also do on the next raise" items stay out.
- The whole `push` job — ACR build/push and `helm upgrade --install` — moves from `main` to `release`; `main` keeps `test`/`build-backend`/`build-frontend`/`chart-lint`/`gitleaks` and no longer authenticates to Azure. This deviates from `docs/plan.md`'s wording that `main` keeps pushing images; `design.md` records why publish and deploy move together instead of splitting build-once/deploy-many.
- `release` is updated only by a pull request from `main`, merged with a merge commit — no squash, no rebase. The resulting push triggers the deploy job, tagging images with that merge commit's `github.sha`, not `main`'s.
- Trust stays one federated credential: `ci_deploy_branch` changes from `main` to `release`. The credential's name embeds the branch, so it's replaced; the CI identity and client ID are unchanged, so no repository Variable changes.
- A merge into `release` with no cluster raised still fails the deploy step — the intended signal, not something to skip past.
- `release` deploy runs get their own `concurrency` group, so a later push can't cancel one mid-flight; `main`'s cancel-in-progress behavior is unchanged.
- `on.pull_request.branches` gains `release`, so the main-into-release PR runs CI checks; the `push` job itself stays gated on push events only.
- The deploy step's result reflects workload readiness, not just manifest acceptance: `helm upgrade --install` gains `--wait` and an explicit `--timeout` (provisional, pending a measured deploy duration). An `if: failure()` step dumps pod status, events, descriptions, and container logs — including `rag-ingest` — to the job log, the only record surviving a teardown. Helm and `kubelogin` versions are pinned instead of `latest`.
- Manual, out-of-band: a GitHub ruleset on `release` requiring a pull request (0 approvals), merge-commit method only, blocking force-push/deletion. Not committable as code. "PRs into `release` come only from `main`" is an operating rule, not enforced.

## Non-Goals

- Browser-triggered cluster raise/teardown.
- Build-once, deploy-many (`main` publishes images, `release` only deploys them).
- GitHub Environments as the OIDC federation subject.
- Enforcing pull requests' source branch into `release`.
- Narrowing CI's Cluster Admin role (`step9-aks-deployment` design.md D4).
- Skipping the deploy step when no cluster exists.
- Automatic rollback on a failed deploy (`--atomic` or equivalent) — it removes failed pods before they can be diagnosed, and on a first install uninstalls the release including its PVC.

## Capabilities

### Modified Capabilities
- `deployment` — its "A merge to the default branch" scenario ties publish/deploy to the default branch; this ties them to a merge into `release` instead. `deployment` exists only in the un-archived `step9-aks-deployment` change, which must be archived before this one can modify it.

## Impact

- `.github/workflows/ci.yml` — `on.push`/`on.pull_request`, `concurrency`, the `push` job's `if`, `--wait`/`--timeout`, the failure-diagnostics step, pinned Helm/kubelogin versions.
- `Infrastructure/terraform/platform/variables.tf` — `ci_deploy_branch` default.
- `docs/index.md`, `docs/plan.md` — updated to reflect the split.
- `openspec/changes/step9-aks-deployment/design.md` D4 — a dated addendum, not a rewrite.
- One platform-layer Terraform apply, replacing the CI federated credential.
- A manual `release` ruleset in GitHub repository settings.
- `docs/step7.md` unchanged, as a historical record.
