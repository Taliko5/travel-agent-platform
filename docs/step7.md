# Step 7: GitHub Actions CI/CD

## Goal

Backend and frontend verification (lint + test) and Docker build jobs on every push to `main` and every PR, gated by branch protection so the checks are a real merge requirement — not just advisory. No image push in this step — that is Step 9 (AWS).

## Decisions

**No secrets required** — all tests are fully mocked (`get_model()` / `get_vectorstore()` lazy-initialized, never called at import time). Pipeline passes on a fresh fork with zero configuration.

**`needs: test` on `build-backend`, `needs: frontend` on `build-frontend`** — don't burn Docker build time on broken branches, per stack.

**pip cache keyed on `requirements.txt` hash** — clean install only runs when dependencies change (~30–60s saved per run). `restore-keys: pip-` falls back to the most recent entry on key miss.

**Docker layer cache via `type=gha, mode=max`** — caches all intermediate layers. The `pip install`/`npm ci` layers are reused on source-only changes.

**ESLint prerequisite** — the frontend job runs `npm run lint`, which requires `eslint`/`eslint-config-next` as devDependencies and a committed config; without them `next lint` prompts interactively to install, which hangs non-interactively in CI. This was closed by `step6c-test-lint-format`, which landed `eslint`/`eslint-config-next`/`.eslintrc.json` before this frontend job was applied.

**Placeholder `npm test` step** — kept as a decision record even though it turned out to be moot: by the time this frontend job was applied, `step6c-test-lint-format` had already replaced the intended placeholder with a real Vitest suite (6 test files, 21 tests). `npm test` runs `vitest run` for real, not a placeholder.

**Concurrency, permissions, path filtering, branch protection, Renovate, Trivy, gitleaks** — see `openspec/changes/harden-ci-pipeline/design.md` for the full rationale behind each addition below.

**Python version single-sourced via `backend/.python-version`** — `python-version: "3.13"` was hardcoded directly in `ci.yml`, duplicating `backend/Dockerfile`'s `FROM python:3.13-slim` with no shared source of truth (unlike Node, which already has a root `.nvmrc`). Added `backend/.python-version` and pointed `actions/setup-python` at it via `python-version-file`, mirroring the Node pattern. `backend/Dockerfile`'s `FROM` line stays a separate manual pin — Docker can't read a version file into `FROM` without extra `ARG` plumbing, the same tradeoff already accepted for `frontend/Dockerfile`'s `node:24-alpine`.

## File

See `.github/workflows/ci.yml` for the full workflow. Jobs:

- `changes` — `dorny/paths-filter@v3`, producing `backend`/`frontend` boolean outputs used to gate the jobs below (jobs still run and report a status; their real steps no-op when their path group didn't change, so branch-protection required checks are always satisfiable).
- `test` — checkout → Python (`backend/.python-version`) → pip cache → install deps → `ruff check backend/` → `ruff format --check backend/` → `pytest backend/tests/ -v`.
- `build-backend` — needs `test` → Docker Buildx → build `backend/Dockerfile` (`push: false`, GHA layer cache) → Trivy scan (non-blocking, SARIF) → upload to Security tab.
- `frontend` — checkout → `actions/setup-node@v4` (`node-version-file: ".nvmrc"`) → `npm ci` → `npm run lint` → `npm test` → `npm run build`.
- `build-frontend` — needs `frontend` → Docker Buildx → build `frontend/Dockerfile` (`push: false`, GHA layer cache) → Trivy scan (non-blocking, SARIF) → upload to Security tab.
- `gitleaks` — scans the push/PR diff for committed secrets, independent of path filtering (secrets can land in any file).

Workflow-level `concurrency` (cancel superseded runs for the same ref) and `permissions: contents: read` (least-privilege `GITHUB_TOKEN`; `build-backend`/`build-frontend` additionally grant `security-events: write` for the SARIF upload step) apply across all jobs.

### Branch protection (manual, out-of-band)

`test`, `frontend`, `build-backend`, and `build-frontend` are configured as required status checks on `main` under Settings → Branches. This is what makes the pipeline a real merge gate rather than an advisory green checkmark — it cannot be committed as code (no repo-settings-as-code mechanism here) and must be applied by a repo admin.

### Renovate (dependency updates)

The Mend Renovate GitHub App must be installed on the repo (manual, out-of-band, same category as branch protection) for `renovate.json` (repo root, `{"extends": ["config:recommended"]}`) to take effect, covering `backend/requirements.txt` and `frontend/package-lock.json`.

### Step 9 extension (ECR push)

When Step 9 adds ECR push, append a third `push` job to the same `ci.yml` — `test` and `build` are unchanged:

```yaml
  push:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      - uses: aws-actions/amazon-ecr-login@v2
      - uses: docker/build-push-action@v5
        with:
          context: ./backend
          file: ./backend/Dockerfile
          push: true
          tags: ${{ steps.login-ecr.outputs.registry }}/travel-agent-backend:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## Tasks

- [x] 7.1 Create `.github/workflows/ci.yml`
- [ ] 7.2 Verify `test` job passes (ruff + pytest, no API key) — job reported `success` when PR #1 merged, but its real steps were path-filter-skipped (that PR touched no `backend/` files); not yet exercised for real under the new pipeline structure.
- [ ] 7.3 Verify `build-backend` job passes (docker build succeeds in CI) — same caveat as 7.2; Docker build verified locally against the exact `context`/`file` paths, not yet on a live runner.
- [x] 7.4 Update `docs/plan.md` Step 7 to Done
- [x] 7.5 Apply `frontend`/`build-frontend` jobs, concurrency/permissions/path-filtering, Trivy, gitleaks (`openspec/changes/harden-ci-pipeline/`) — merged via PR #1.
- [ ] 7.6 Verify `frontend` and `build-frontend` jobs pass in CI — same caveat as 7.2/7.3.
- [ ] 7.7 Configure branch protection on `main` (manual, out-of-band)
- [ ] 7.8 Install Renovate GitHub App (manual, out-of-band)
- [x] 7.9 Single-source backend Python version via `backend/.python-version` (branch `single-source-python-version`)

## Debugging

```bash
ruff check backend/
ruff check backend/ --fix
cd backend && pytest tests/ -v
docker build -f backend/Dockerfile backend/
```

Common `build-backend`/`build-frontend` job failures:
- Package in `venv` but not frozen to `requirements.txt`
- File path in `COPY` that doesn't exist in `backend/` or `frontend/`
- `next lint` prompting interactively (missing `eslint`/`eslint-config-next` or config — should not recur, both are committed)

## Definition of Done

- [x] `.github/workflows/ci.yml` committed (`test`, `build-backend`, `frontend`, `build-frontend`, `gitleaks`, `changes`)
- [ ] `test` job: `ruff check`, `ruff format --check`, `pytest` all exit 0 — not yet exercised for real post-refactor (see 7.2)
- [ ] `frontend` job: `npm run lint`, `npm test`, `npm run build` all exit 0 — not yet exercised for real post-refactor (see 7.6)
- [ ] `build-backend`/`build-frontend` jobs: Docker images build without errors — not yet exercised for real post-refactor (see 7.3/7.6); both build clean locally
- [ ] Trivy SARIF results appear in the Security tab for both images — Trivy steps haven't run yet (path-filtered out on every PR so far)
- [x] All jobs green in GitHub Actions UI, including on a docs-only diff (path-filter skip still reports success) — confirmed on PR #1
- [ ] Branch protection on `main` requires `test`, `frontend`, `build-backend`, `build-frontend`
- [ ] Renovate GitHub App installed, Dependency Dashboard issue created
- [x] No secrets required
