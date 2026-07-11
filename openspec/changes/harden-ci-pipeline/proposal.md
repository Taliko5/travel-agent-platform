## Why

`docs/step7.md` scoped Step 7 CI/CD as a backend-only, two-job pipeline (`test`, `build`) plus a drafted-but-unapplied frontend job. Verifying that draft against the actual repo state surfaced a blocker (the frontend has no ESLint installed, so `npm run lint` fails non-interactively in CI) and several gaps that leave the pipeline incomplete or purely advisory: the frontend Docker image is never built in CI, superseded runs aren't cancelled, the workflow requests default (broad) `GITHUB_TOKEN` permissions, every push runs the full pipeline regardless of what changed, and — most importantly — nothing on GitHub actually requires these checks to pass before merging to `main`. Step 9 (AWS deployment) depends on Step 7 being genuinely complete, not just present.

## What Changes

- Add ESLint (`eslint` + `eslint-config-next`) as frontend devDependencies with a committed config, so `npm run lint` is runnable non-interactively.
- Apply the frontend CI job from `docs/step7.md` (checkout → setup-node via root `.nvmrc` → `npm ci` → lint → test → build), now that lint is safe to run. The `test` step runs `npm test` against a placeholder script (`package.json` `"test"` — no test runner, no test files) so the step passes today and requires no CI change once real frontend tests land; authoring those tests is explicitly out of this change's scope (see below).
- Add a `build-frontend` job that builds `frontend/Dockerfile` with `push: false`, mirroring the existing backend `build` job (renamed `build-backend` for symmetry).
- Add a workflow-level `concurrency` group with `cancel-in-progress: true`.
- Add a workflow-level `permissions: contents: read` block.
- Add path filtering (see `design.md` for the chosen mechanism) so backend-only changes skip the frontend job and vice versa.
- Document a manual, non-YAML task: configure GitHub branch protection on `main` requiring `test`, `frontend`, `build-backend`, and `build-frontend` to pass before merge. **This cannot be committed as code** — it's a repo settings change — but it is the step that makes every job above load-bearing instead of advisory.
- Add Renovate for automated dependency updates: install the Mend Renovate GitHub App on the repo (**manual, out-of-band step, cannot be done via file commit alone**), then add `renovate.json` at the repo root covering `backend/requirements.txt` (pip) and `frontend/package-lock.json` (npm), starting from `{"extends": ["config:recommended"]}`.
- Add container image vulnerability scanning: a step after `build-backend` and `build-frontend` using `aquasecurity/trivy-action` to scan each built image, uploading SARIF results via `github/codeql-action/upload-sarif` to the repo's Security tab. Starts non-blocking (`exit-code: 0`) — tightening to `exit-code: 1` (gating merges) is a follow-up once existing base-image CVEs are triaged.
- Add secret scanning: a `gitleaks` step run on push/PR diffs, catching hardcoded credentials in source (not covered by Trivy, which scans built images for known CVEs, not committed secrets).
- Update `docs/step7.md` and `docs/plan.md` once the above lands, reflecting the frontend job as applied (not just drafted) and Step 7 status accordingly.

Explicitly **out of scope** (called out so they aren't silently assumed handled):
- **Authoring frontend unit tests** — no Jest/Vitest/Playwright exists, and no test files exist for `ChatInterface.tsx`, `MessageList.tsx`, `MessageBubble.tsx`, `ChatInput.tsx`, etc. Writing those tests is a substantive implementation task (choosing a runner, authoring test code), not CI-wiring, so it does not belong in Step 7. This change only adds a placeholder `npm test` step/script so the CI job is structurally ready; the real work is tracked as a new "Step 6c: Frontend unit tests" entry appended to `docs/plan.md`'s existing (Done) Step 6 section — following the same convention already used for Step 6's "UI polish" addition.
- Backend test coverage gaps (`agent/graph.py` routing, `api/main.py` `/chat` + CORS, `rag/retriever.py`) — untested today, unchanged by this proposal.
- `ruff format --check`, `docker compose config` / k8s manifest validation, README CI badge — deferred to a later, Step-8-adjacent change.
- Tightening Trivy to blocking (`exit-code: 1`, `severity: CRITICAL`) — deferred until an initial scan has been reviewed and existing base-image CVEs triaged; this change only wires up non-blocking scanning.

## Capabilities

### New Capabilities
- `ci-pipeline`: GitHub Actions pipeline behavior — which jobs run, what triggers them, what they require to pass, and the workflow-level safety settings (concurrency, permissions, path filtering) that govern them.

### Modified Capabilities
_None — `chat-frontend` (existing spec) is unaffected; this change only touches build/CI tooling around it, not its runtime requirements._

## Impact

- `.github/workflows/ci.yml` — restructured: `build` → `build-backend`, new `frontend`, `build-frontend`, and secret-scanning jobs, new `concurrency`/`permissions` blocks, path filters added, Trivy scan steps appended to both build jobs.
- `frontend/package.json`, new `frontend/.eslintrc.json` (or `eslint.config.mjs`) — new devDependencies, lint config, and a placeholder `"test"` script.
- New `renovate.json` at repo root.
- `docs/step7.md` — updated to reflect applied (not drafted) state, frontend job now includes lint/test/build.
- `docs/plan.md` — Step 7 status updated to Done; new "Step 6c: Frontend unit tests" subsection appended under the existing Step 6 section, describing the deferred test-authoring work.
- GitHub repo settings (Settings → Branches) — manual, out-of-band change required for branch protection; tracked as a task but not enforceable via this PR.
- GitHub App installation (Mend Renovate) — manual, out-of-band, required before `renovate.json` takes effect.
- GitHub Security tab — new source of alerts once Trivy SARIF uploads are wired up.
