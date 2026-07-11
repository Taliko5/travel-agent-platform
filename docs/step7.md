# Step 7: GitHub Actions CI/CD

## Goal

Two-job pipeline on every push to `main` and every PR: lint + test, then Docker build. No image push in this step — that is Step 9 (AWS).

## Decisions

**No secrets required** — all tests are fully mocked (`get_model()` / `get_vectorstore()` lazy-initialized, never called at import time). Pipeline passes on a fresh fork with zero configuration.

**`needs: test` on the build job** — don't burn Docker build time on broken branches.

**pip cache keyed on `requirements.txt` hash** — clean install only runs when dependencies change (~30–60s saved per run). `restore-keys: pip-` falls back to the most recent entry on key miss.

**Docker layer cache via `type=gha, mode=max`** — caches all intermediate layers. The `pip install` layer (~60s) is reused on source-only changes.

## File

See `.github/workflows/ci.yml` for the full workflow.

Two jobs:
- `test` — checkout → Python 3.13 → pip cache → install deps → `ruff check backend/` → `pytest backend/tests/ -v`
- `build` — checkout → Docker Buildx → `docker build` with GHA layer cache (`push: false`)

### Gap: no frontend job

`frontend/` (Step 6) has `npm run lint` and `npm run build` scripts but neither runs in CI — a broken build or lint error on the frontend can merge to `main` undetected. Proposed third job, independent of `test`/`build` (no `needs:`, so it runs in parallel):

```yaml
  frontend:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version-file: ".nvmrc"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Lint
        working-directory: frontend
        run: npm run lint

      - name: Build
        working-directory: frontend
        run: npm run build
```

Not yet applied to `.github/workflows/ci.yml` — pending confirmation.

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
- [ ] 7.2 Verify `test` job passes (ruff + pytest, no API key)
- [ ] 7.3 Verify `build` job passes (docker build succeeds in CI)
- [ ] 7.4 Update `docs/plan.md` Step 7 to Done

## Debugging

```bash
ruff check backend/
ruff check backend/ --fix
cd backend && pytest tests/ -v
docker build -f backend/Dockerfile backend/
```

Common `build` job failures:
- Package in `venv` but not frozen to `requirements.txt`
- File path in `COPY` that doesn't exist in `backend/`

## Definition of Done

- [x] `.github/workflows/ci.yml` committed
- [ ] `test` job: `ruff check` exits 0, `pytest` exits 0
- [ ] `build` job: Docker image builds without errors
- [ ] Both jobs green in GitHub Actions UI
- [ ] No secrets required
