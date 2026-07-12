## 1. Frontend ESLint setup (blocker for the frontend job)

- [x] 1.1 Add `eslint` and `eslint-config-next` to `frontend/package.json` devDependencies, matching the installed Next.js 14 major version — already landed via `step6c-test-lint-format` before this change was applied; verified present.
- [x] 1.2 Add ESLint config (`frontend/.eslintrc.json` extending `next/core-web-vitals`, or `eslint.config.mjs` if using flat config) — already landed via `step6c-test-lint-format`; verified present (`.eslintrc.json` extends `next/core-web-vitals` + `prettier`).
- [x] 1.3 Run `npm run lint` locally in `frontend/` and fix or explicitly accept any findings, so the first CI run is green — ran clean, no findings (Node 24 via nvm; note local shell had defaulted to system Node 12, which breaks `next lint`/`next build` non-obviously — use `nvm use 24` first).
- [x] 1.4 Run `npm run build` locally to confirm lint additions don't break the existing build — clean build.
- [x] 1.5 Add a placeholder `"test"` script — moot: `step6c-test-lint-format` already replaced this with a real Vitest suite (`"test": "vitest run"`, 6 test files, 21 tests) before this change was applied. No placeholder needed.

## 2. Workflow hygiene blocks

- [x] 2.1 Add workflow-level `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }` to `.github/workflows/ci.yml`
- [x] 2.2 Add workflow-level `permissions: contents: read` to `.github/workflows/ci.yml`

## 3. Path filtering

- [x] 3.1 Add a `changes` job using `dorny/paths-filter@v3` producing `backend` and `frontend` boolean outputs (e.g. `backend/**` and `frontend/**` path groups)
- [x] 3.2 Gate `test`/`build-backend` steps behind `needs.changes.outputs.backend == 'true'` via `if:` conditions (job still runs and reports status; internal steps no-op when path group didn't change)
- [x] 3.3 Gate `frontend`/`build-frontend` steps behind `needs.changes.outputs.frontend == 'true'` the same way
- [x] 3.4 Push a docs-only test commit to a scratch branch and confirm all four checks still report success (not skipped/absent) with no real work performed — confirmed on PR #1 (commit 703f4e9, run 29189846403): this PR itself only touches `.github/`, `docs/`, `openspec/`, `renovate.json` — `test`, `frontend`, `build-backend`, `build-frontend` all reported `success` with their real steps `skipped`.

## 4. Frontend CI job

- [x] 4.1 Add `frontend` job to `.github/workflows/ci.yml`: checkout → `actions/setup-node@v4` with `node-version-file: ".nvmrc"` and `cache: npm` / `cache-dependency-path: frontend/package-lock.json` → `npm ci` (working-directory: frontend) → `npm run lint` → `npm test` → `npm run build`
- [ ] 4.2 Confirm the job passes in CI (not just locally) — job reported `success` on PR #1, but its real steps were path-filter-skipped (this PR touches no `frontend/` files). Still needs a PR that actually touches `frontend/` to exercise `npm ci`/lint/test/build for real on a runner.

## 5. Docker build jobs (backend + frontend parity)

- [x] 5.1 Rename existing `build` job to `build-backend` in `.github/workflows/ci.yml` (`needs: test` unchanged)
- [x] 5.2 Add `build-frontend` job: `needs: frontend`, Docker Buildx + `docker/build-push-action@v5` with `context: ./frontend`, `file: ./frontend/Dockerfile`, `push: false`, `cache-from: type=gha`, `cache-to: type=gha,mode=max`
- [ ] 5.3 Confirm both `build-backend` and `build-frontend` pass in CI — jobs reported `success` on PR #1, but their real steps were path-filter-skipped (no `backend/`/`frontend/` changes in this PR). Docker builds were verified locally against the exact `context`/`file` paths (both images built clean), but not yet exercised on a GitHub-hosted runner. Also caught and fixed two real CI issues along the way: `trivy-action@0.28.0` needed a `v` prefix, and even `v0.28.0` failed because its internal `setup-trivy@v0.2.1` pin had been deleted upstream — bumped to `trivy-action@v0.36.0`, which resolves cleanly.

## 6. Branch protection (manual, out-of-band)

- [ ] 6.1 In GitHub Settings → Branches, add a branch protection rule for `main` requiring status checks: `test`, `frontend`, `build-backend`, `build-frontend` — requires repo-admin access via the GitHub UI; not performed in this session.
- [ ] 6.2 Confirm a deliberately-broken test PR is blocked from merging by the new rule, then close it without merging — depends on 6.1.

## 7. Renovate (dependency updates)

- [ ] 7.1 Install the Mend Renovate GitHub App on this repository (manual, out-of-band — cannot be done via file commit) — requires repo-admin access via GitHub UI; not performed in this session.
- [x] 7.2 Add `renovate.json` at repo root: `{"extends": ["config:recommended"]}`, scoped to `backend/requirements.txt` and `frontend/package-lock.json`
- [ ] 7.3 Confirm the Dependency Dashboard issue is created after install, and at least one update PR appears if an outdated dependency exists — depends on 7.1.

## 8. Trivy image scanning

- [x] 8.1 Add a Trivy scan step (`aquasecurity/trivy-action`) after `build-backend`, scanning the just-built backend image, `exit-code: 0`, `format: sarif`
- [x] 8.2 Add the equivalent Trivy scan step after `build-frontend` for the frontend image
- [x] 8.3 Add `github/codeql-action/upload-sarif` steps to upload both scan results to the repo's Security tab
- [ ] 8.4 Confirm scan results appear in the Security tab after a PR run, and confirm the build jobs do not fail regardless of findings (non-blocking by design) — not yet exercised: the Trivy/upload-sarif steps were path-filter-skipped on PR #1 (no `backend/`/`frontend/` changes). Needs a PR touching those paths.
- [ ] 8.5 (Not part of this change) Note as a follow-up: once initial CVE findings are triaged, tighten to `exit-code: 1`, `severity: CRITICAL`

## 9. Secret scanning

- [x] 9.1 Add a `gitleaks` job to `.github/workflows/ci.yml`, triggered on `push`/`pull_request`, scanning the diff
- [x] 9.2 Confirm the job passes on the current repo state (no findings expected, since `backend/.env` is already gitignored and untracked) — confirmed on PR #1: `gitleaks` is not path-filtered, so it ran for real (not skipped) and passed with no findings.
- [ ] 9.3 Optionally verify detection works by testing locally with a dummy secret pattern (not committed) — optional, not done.

## 10. Docs sync

- [x] 10.1 Update `docs/step7.md`: mark the frontend job section as applied (remove "pending confirmation"), add the concurrency/permissions/path-filtering/branch-protection/Renovate/Trivy/gitleaks additions, note the ESLint prerequisite and the placeholder `npm test` step
- [x] 10.2 Update `docs/plan.md` Step 7 status from "Next" to "Done"
- [x] 10.3 Append a new "Step 6c" subsection — moot as separately-tracked work: `docs/plan.md`'s existing "Step 6c: Testing, Linting & Formatting" section (landed via `step6c-test-lint-format`, before this change was applied) already documents the real Vitest suite in more detail than this task's originally-planned placeholder-script framing. No further edit needed.
