## 1. Frontend ESLint setup (blocker for the frontend job)

- [ ] 1.1 Add `eslint` and `eslint-config-next` to `frontend/package.json` devDependencies, matching the installed Next.js 14 major version
- [ ] 1.2 Add ESLint config (`frontend/.eslintrc.json` extending `next/core-web-vitals`, or `eslint.config.mjs` if using flat config)
- [ ] 1.3 Run `npm run lint` locally in `frontend/` and fix or explicitly accept any findings, so the first CI run is green
- [ ] 1.4 Run `npm run build` locally to confirm lint additions don't break the existing build
- [ ] 1.5 Add a placeholder `"test"` script to `frontend/package.json` (e.g. `echo "no tests yet" && exit 0`) — no test runner, no test files; this only makes `npm test` a valid, passing command for the CI step to call

## 2. Workflow hygiene blocks

- [ ] 2.1 Add workflow-level `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true }` to `.github/workflows/ci.yml`
- [ ] 2.2 Add workflow-level `permissions: contents: read` to `.github/workflows/ci.yml`

## 3. Path filtering

- [ ] 3.1 Add a `changes` job using `dorny/paths-filter@v3` producing `backend` and `frontend` boolean outputs (e.g. `backend/**` and `frontend/**` path groups)
- [ ] 3.2 Gate `test`/`build-backend` steps behind `needs.changes.outputs.backend == 'true'` via `if:` conditions (job still runs and reports status; internal steps no-op when path group didn't change)
- [ ] 3.3 Gate `frontend`/`build-frontend` steps behind `needs.changes.outputs.frontend == 'true'` the same way
- [ ] 3.4 Push a docs-only test commit to a scratch branch and confirm all four checks still report success (not skipped/absent) with no real work performed

## 4. Frontend CI job

- [ ] 4.1 Add `frontend` job to `.github/workflows/ci.yml`: checkout → `actions/setup-node@v4` with `node-version-file: ".nvmrc"` and `cache: npm` / `cache-dependency-path: frontend/package-lock.json` → `npm ci` (working-directory: frontend) → `npm run lint` → `npm test` → `npm run build`
- [ ] 4.2 Confirm the job passes in CI (not just locally) — verifies the ESLint non-interactive fix actually works on a runner with no TTY, and that the placeholder `npm test` step passes

## 5. Docker build jobs (backend + frontend parity)

- [ ] 5.1 Rename existing `build` job to `build-backend` in `.github/workflows/ci.yml` (`needs: test` unchanged)
- [ ] 5.2 Add `build-frontend` job: `needs: frontend`, Docker Buildx + `docker/build-push-action@v5` with `context: ./frontend`, `file: ./frontend/Dockerfile`, `push: false`, `cache-from: type=gha`, `cache-to: type=gha,mode=max`
- [ ] 5.3 Confirm both `build-backend` and `build-frontend` pass in CI

## 6. Branch protection (manual, out-of-band)

- [ ] 6.1 In GitHub Settings → Branches, add a branch protection rule for `main` requiring status checks: `test`, `frontend`, `build-backend`, `build-frontend`
- [ ] 6.2 Confirm a deliberately-broken test PR is blocked from merging by the new rule, then close it without merging

## 7. Renovate (dependency updates)

- [ ] 7.1 Install the Mend Renovate GitHub App on this repository (manual, out-of-band — cannot be done via file commit)
- [ ] 7.2 Add `renovate.json` at repo root: `{"extends": ["config:recommended"]}`, scoped to `backend/requirements.txt` and `frontend/package-lock.json`
- [ ] 7.3 Confirm the Dependency Dashboard issue is created after install, and at least one update PR appears if an outdated dependency exists

## 8. Trivy image scanning

- [ ] 8.1 Add a Trivy scan step (`aquasecurity/trivy-action`) after `build-backend`, scanning the just-built backend image, `exit-code: 0`, `format: sarif`
- [ ] 8.2 Add the equivalent Trivy scan step after `build-frontend` for the frontend image
- [ ] 8.3 Add `github/codeql-action/upload-sarif` steps to upload both scan results to the repo's Security tab
- [ ] 8.4 Confirm scan results appear in the Security tab after a PR run, and confirm the build jobs do not fail regardless of findings (non-blocking by design)
- [ ] 8.5 (Not part of this change) Note as a follow-up: once initial CVE findings are triaged, tighten to `exit-code: 1`, `severity: CRITICAL`

## 9. Secret scanning

- [ ] 9.1 Add a `gitleaks` job to `.github/workflows/ci.yml`, triggered on `push`/`pull_request`, scanning the diff
- [ ] 9.2 Confirm the job passes on the current repo state (no findings expected, since `backend/.env` is already gitignored and untracked)
- [ ] 9.3 Optionally verify detection works by testing locally with a dummy secret pattern (not committed)

## 10. Docs sync

- [ ] 10.1 Update `docs/step7.md`: mark the frontend job section as applied (remove "pending confirmation"), add the concurrency/permissions/path-filtering/branch-protection/Renovate/Trivy/gitleaks additions, note the ESLint prerequisite and the placeholder `npm test` step
- [ ] 10.2 Update `docs/plan.md` Step 7 status from "Next" to "Done"
- [ ] 10.3 Append a new "Step 6c: Frontend unit tests" subsection under `docs/plan.md`'s existing Step 6 section (same convention as the "UI polish" addition already there), describing: no test runner installed yet, CI already has an `npm test` step wired and waiting via a placeholder script, and the follow-up work is to pick a runner (Jest/Vitest) and author tests for `ChatInterface.tsx`, `MessageList.tsx`, `MessageBubble.tsx`, `ChatInput.tsx`
