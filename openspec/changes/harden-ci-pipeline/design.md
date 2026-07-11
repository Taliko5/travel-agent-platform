## Context

`.github/workflows/ci.yml` currently has two jobs, `test` and `build`, both backend-only. `docs/step7.md` already drafts a third `frontend` job (lint + build) as "pending confirmation" but it was never applied — and applying it as-drafted would fail, because `frontend/package.json` has no `eslint` or `eslint-config-next` dependency and no ESLint config file exists anywhere in the repo. `next lint` prompts interactively to install ESLint on first run; there's no TTY in GitHub Actions to answer that prompt, so the step would fail (or hang, depending on Next version behavior).

Beyond that blocker, the pipeline has no `concurrency` control, no explicit `permissions:`, runs unconditionally regardless of what changed, and — the biggest gap — nothing on GitHub actually requires any of these jobs to pass before a PR can merge to `main`. Step 9 (AWS deployment) is documented as depending on "Step 5 and 7 complete," which implies Step 7 should be a real gate, not just a green checkmark nobody is required to look at.

## Goals / Non-Goals

**Goals:**
- Make the drafted frontend job actually runnable (fix the ESLint gap first).
- Bring frontend build verification to parity with backend (both get a Docker build job).
- Add baseline workflow hygiene: concurrency cancellation, least-privilege `permissions:`, path filtering so unrelated changes don't trigger unrelated jobs.
- Make explicit that CI is only a gate once branch protection is configured, and hand off that exact manual step.

**Non-Goals:**
- Adding frontend tests (no test runner exists; installing one is a separate, larger decision — framework choice, first test suite — out of scope here; tracked as "Step 6c" in `docs/plan.md` instead). This change only wires a placeholder `npm test` step into CI.
- Closing backend test coverage gaps (`agent/graph.py`, `api/main.py`, `rag/retriever.py`).
- `ruff format --check`, compose/k8s manifest validation, README badge — all deferred.
- Making Trivy or gitleaks merge-blocking — both start report-only/non-blocking; gating is a follow-up once findings are triaged.
- Step 9's ECR push job (`docs/step7.md`'s "Step 9 extension" section) — untouched, added later.

## Decisions

**Frontend `test` step: wire it into the CI job now with a placeholder script, defer real test authoring to Step 6c.**
The frontend job runs `npm test` alongside lint and build. `package.json`'s `"test"` script is a placeholder (e.g. `echo "no tests yet" && exit 0`) — no test runner (Jest/Vitest/Playwright) is installed, no test files are written. Alternative considered: omit the `test` step entirely until a runner and tests exist. Rejected — that means a second `ci.yml` diff is needed the moment Step 6c lands, and in the meantime nothing in CI documents that testing is a known, tracked gap rather than an oversight. Wiring the step now with a trivially-passing placeholder means Step 6c's only CI-facing change is swapping the script body (e.g. to `vitest run`); the workflow YAML doesn't need to change at all. Test-authoring itself — choosing a runner, writing test files for `ChatInterface.tsx`/`MessageList.tsx`/`MessageBubble.tsx`/`ChatInput.tsx` — is explicitly out of this change's scope and tracked separately as "Step 6c: Frontend unit tests" appended to `docs/plan.md`'s Step 6 section (mirroring how Step 6's "UI polish" follow-up was already appended there).

**ESLint: add `eslint` + `eslint-config-next` as devDependencies, with `next/core-web-vitals` config, before applying the frontend job.**
Alternative considered: drop the `lint` step from the frontend job and rely solely on `next build`'s built-in type-checking. Rejected — `next build` type-checks but does not run ESLint rules (e.g. unused vars, react-hooks rules), so dropping lint silently narrows what Step 6's "gap" was supposed to close. Installing ESLint is a few lines and keeps the job matching what `docs/step7.md` already described.

**Job structure: rename `build` → `build-backend`, add `frontend` and `build-frontend`, each `build-*` job depends on its same-stack `test`/`frontend` job via `needs:`.**
Alternative considered: a single combined `build` job producing both images sequentially. Rejected — keeping backend and frontend lanes independent means a frontend Dockerfile break doesn't block backend build feedback and vice versa, consistent with `docs/step7.md`'s existing rationale for `needs: test` ("don't burn Docker build time on broken branches") applied per-stack rather than globally.

**Path filtering: use `dorny/paths-filter` at the job level rather than top-level `on.push.paths`/`on.pull_request.paths`.**
Two options considered:
| Approach | Behavior | Trade-off |
|---|---|---|
| `on.push.paths` / `on.pull_request.paths` (workflow-level) | Whole workflow (all jobs) only triggers if a matching path changed | Simpler, zero extra actions, but binary — can't have backend changes skip *only* the frontend job while still running backend jobs; a mixed-path PR (e.g. touching both `backend/` and `frontend/`) still runs everything, which is fine, but a `docs/`-only PR skips CI entirely, meaning even `build-backend`/`build-frontend` never report a status — which can leave required-status-check PRs stuck with no check to satisfy (see branch protection below) |
| `dorny/paths-filter` (job-level, gates steps within jobs via `if:`) | Each job still triggers and reports a status (even if it does nothing but the filter step), but skips its real work when its path group didn't change | Slightly more workflow YAML (one filter step + `if:` conditions per job), but every job still posts a required status on every PR — compatible with branch protection's "required checks" model, avoids the stuck-PR problem above |

Decision: **`dorny/paths-filter`**, specifically because branch protection (this same change's Decision below) requires `test`, `frontend`, `build-backend`, `build-frontend` as required checks — and GitHub's required-checks feature blocks merges indefinitely if a required job never runs at all for a given PR (e.g. a docs-only PR under `paths:` workflow-level filtering). Job-level skipping via `if:` keeps every required check reporting a (fast, no-op) success even when its path group is untouched.

**Permissions: `permissions: contents: read` at workflow level.**
No job in this workflow writes to the repo, opens PRs, or manages packages — read-only checkout is sufficient. Set once at the top rather than per-job since no job needs anything broader.

**Concurrency: `group: ${{ github.workflow }}-${{ github.ref }}`, `cancel-in-progress: true`.**
Standard pattern — a new push to the same branch/PR ref supersedes the previous run's relevance.

**Branch protection: manual GitHub Settings step, not YAML.**
This repo has no branch-protection-as-code mechanism (no Terraform GitHub provider, no GitHub ruleset file support wired up). Branch protection is configured under Settings → Branches → Branch protection rules, and must be done by a repo admin outside of any PR this change produces. Documented as an explicit task with instructions, and called out in the proposal's Definition-of-Done — the CI changes in this proposal are necessary but not sufficient for CI to be a real merge gate.

**Dependency updates: Renovate over Dependabot.**
The repo has neither `.github/dependabot.yml` nor any existing Renovate config today, so this is a clean addition, not a migration. Dependabot was the lower-setup-cost alternative — it needs no GitHub App install, just a committed YAML file — but Renovate was chosen specifically for PR grouping (e.g. batching all patch-level pip bumps into one PR instead of one-PR-per-package) and the auto-maintained Dependency Dashboard issue, both of which pay off more as the dependency surface grows (this repo already spans pip + npm + two Dockerfiles). Trade-off accepted: Renovate requires installing the Mend Renovate GitHub App on this repository first — a manual, out-of-band step, same category as branch protection, that cannot be satisfied by committing `renovate.json` alone. Start config: `{"extends": ["config:recommended"]}` at repo root, covering `backend/requirements.txt` and `frontend/package-lock.json`; grouping/scheduling rules layered on later if the default cadence is too noisy.

**Image scanning: Trivy, non-blocking at first.**
`aquasecurity/trivy-action` runs after each of `build-backend`/`build-frontend`, scanning the image just built. Output format `sarif`, uploaded via `github/codeql-action/upload-sarif`, surfaces results in the repo's Security tab alongside Dependabot/Renovate-style alerts — a single place to triage, rather than build logs. Starts with `exit-code: 0` (report-only) deliberately: the base images (`python:3.13-slim`, `node:24-alpine`) almost certainly have some known CVEs already, and flipping straight to blocking (`exit-code: 1`) would fail every PR on day one for pre-existing issues unrelated to the change being reviewed. Tightening to `exit-code: 1, severity: CRITICAL` (then later `HIGH`) is called out as a deliberate follow-up once an initial scan has been reviewed. No secrets or external account needed — consistent with `docs/step7.md`'s "no secrets required" principle.

**Secret scanning: gitleaks, corrected rationale.**
Checked the specific claim that motivated this suggestion — that `backend/.env` is untracked and exposed to an accidental `git add -A`. It isn't: `.gitignore` line 8 explicitly lists `backend/.env` (confirmed via `git check-ignore -v`), and only `backend/.env.example` / `frontend/.env.local.example` are tracked in git; the real `.env` files were never committed. So that exact failure mode isn't currently live. The requirement is kept anyway on different grounds: gitleaks catches hardcoded credentials pasted directly into source (not just stray env files), catches anything already sitting in git history from before `.gitignore` was tightened, and catches future files that aren't yet covered by an ignore rule — general defense-in-depth rather than a fix for a live hole. Runs against the PR diff on `push`/`pull_request`, no external account required, OSS CLI/action — same "no secrets required" tier as Trivy.

## Risks / Trade-offs

- **[Risk]** `dorny/paths-filter` is a third-party action, adding a supply-chain dependency beyond the already-used `docker/*` and `actions/*` actions. → **Mitigation**: it's widely used (proposal-level risk acceptance, same trust tier as `docker/build-push-action`), pin to a major version tag as the other actions in `ci.yml` already do.
- **[Risk]** Adding ESLint may surface pre-existing lint violations in `frontend/src/` that have never been checked, blocking the first CI run on unrelated code, not the CI change itself. → **Mitigation**: run `npm run lint` locally as part of implementing this change (task in `tasks.md`) and fix or explicitly accept any findings before the workflow is applied, so the first CI run on `main` is green.
- **[Risk]** Branch protection is a manual step outside version control — it can silently drift (e.g. an admin unchecks "require status checks" later) with no diff to catch it. → **Mitigation**: none available within this change's scope; noted as a known limitation of not having repo-settings-as-code.
- **[Trade-off]** Job-level path filtering (chosen) has more YAML than workflow-level `paths:` (rejected) for a marginal correctness gain (avoiding stuck required-checks on docs-only PRs). Considered acceptable given branch protection is an explicit goal of this change.
- **[Risk]** Renovate is inert without the GitHub App installed — `renovate.json` alone does nothing, and there's no CI-visible failure mode if the install step is skipped (unlike a broken workflow job). → **Mitigation**: call out explicitly in `tasks.md` as a checked, verifiable step (confirm the Dependency Dashboard issue appears after install), not just a file commit.
- **[Risk]** Trivy scanning the base images on day one will likely surface pre-existing CVEs unrelated to any single PR's diff, creating Security-tab noise. → **Mitigation**: deliberately non-blocking start (`exit-code: 0`); triage happens as a follow-up before tightening to blocking.
- **[Risk]** gitleaks scanning only the PR diff (not full history) on `push`/`pull_request` won't catch secrets already committed in past history. → **Mitigation**: accepted for this change's scope (matches "no secrets required, no extra account" framing); a full-history scheduled scan is a natural follow-up, not blocking here.

## Migration Plan

1. Add ESLint deps/config to `frontend/`, run `npm run lint` locally, fix any findings.
2. Extend `.github/workflows/ci.yml`: concurrency + permissions blocks, `dorny/paths-filter` job, rename `build`→`build-backend`, add `frontend` and `build-frontend` jobs, gate all four behind path-filter outputs, add Trivy scan steps to both build jobs, add a gitleaks job.
3. Push to a branch, open a PR, confirm all checks run and go green (including on a trivial docs-only diff, to verify path-filter skip behavior still reports success; and confirm Trivy SARIF appears in the Security tab).
4. Install the Mend Renovate GitHub App on the repo, add `renovate.json`, confirm the Dependency Dashboard issue is created (manual, tracked as a task).
5. Repo admin configures branch protection on `main` requiring the required checks (manual, tracked as a task, not a code change).
6. Update `docs/step7.md` (mark frontend job as applied, remove "pending confirmation") and `docs/plan.md` (Step 7 → Done) in a follow-up commit once 1–5 are verified.

No rollback complexity — this is additive CI configuration; reverting the workflow file returns to the prior two-job state.

## Open Questions

- Should `build-frontend` and `build-backend` also validate `docker-compose.yaml` (`docker compose config`)? Deferred to backlog per proposal, but flagging in case the user wants it folded in now instead.
- Exact ESLint rule set: `next/core-web-vitals` only, or also `next/typescript`? Recommend `next/core-web-vitals` as the minimal default `create-next-app` ships; revisit if the first lint run surfaces type-related issues better caught by the stricter set.
