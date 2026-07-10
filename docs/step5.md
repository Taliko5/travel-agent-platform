# Step 5: Docker + docker-compose

## Goal

Containerize the FastAPI backend so it runs identically in dev, CI, and production. Add Kubernetes manifests as the foundation for Step 9.

## Decisions

**Base image: `python:3.13-slim`** — matches dev Python version. Alpine rejected: musl libc causes compatibility issues with ChromaDB's native dependencies.

**No virtualenv in the container** — Docker provides the isolation. Packages installed with `pip install --no-cache-dir` directly into the system Python.

**Layer cache order** — `COPY requirements.txt` + `RUN pip install` before `COPY . .` so the expensive pip layer is cached independently of source changes.

**ChromaDB: named volume (embedded mode for now)**

| Step | Mode | Why |
|---|---|---|
| Step 5 | Embedded + named Docker volume | One variable at a time — containerize first |
| Step 9 | Server mode, standalone StatefulSet | Multi-replica pods can't share a named volume |

Only `get_vectorstore()` in `rag/retriever.py` changes between modes — nothing else is affected.

**Secrets via `env_file`** — `GOOGLE_API_KEY` injected at runtime; never baked into the image. `.dockerignore` also excludes `.env` as a second line of defence.

**k8s Service: `ClusterIP`** — within-cluster access for dev/CI. One-line change to `LoadBalancer` or ALB Ingress in Step 9.

## File Structure

```
travel-agent-platform/
├── .dockerignore                          → see file
├── docker-compose.yaml                    → see file
├── backend/
│   ├── .env.example                       → see file
│   └── Dockerfile                         → see file
└── Infrastructure/
    └── k8s/
        ├── backend-deployment.yaml        → see file
        └── backend-service.yaml           → see file
```

All files are implemented. See each file for the full content.

Key notes:
- `PYTHONPATH=/app` in Dockerfile — makes `from agent.state import ...` resolve from any working directory inside the container
- `--host 0.0.0.0` in CMD — default `127.0.0.1` is unreachable from outside the container
- `docker-compose down -v` wipes the ChromaDB volume; re-run `python rag/ingest.py` after
- k8s Secret must exist before applying the Deployment: `kubectl create secret generic travel-agent-secrets --from-literal=google-api-key=<key>`

## Tasks

- [x] 5.1 Create `.dockerignore`
- [x] 5.2 Create `backend/Dockerfile`
- [x] 5.3 Smoke test: `docker build -f backend/Dockerfile backend/` exits 0
- [x] 5.4 Fill in `docker-compose.yaml`
- [ ] 5.5 Smoke test: `docker-compose up --build` starts cleanly
- [ ] 5.6 Verify `/health` and `/chat` respond inside container
- [x] 5.7 Create `Infrastructure/k8s/backend-deployment.yaml`
- [x] 5.8 Create `Infrastructure/k8s/backend-service.yaml`
- [ ] 5.9 Validate manifests: `kubectl apply --dry-run=client -f Infrastructure/k8s/`
- [ ] 5.10 Create `backend/.env.example`
- [ ] 5.11 Update `docs/plan.md` Step 5 to Done

## Common Commands

```bash
docker-compose up --build                              # build + start
docker-compose up -d --build                           # background
docker-compose logs -f backend                         # logs
docker-compose exec backend python rag/ingest.py       # first-time ingest
docker-compose exec backend python -m pytest tests/ -v # run tests in container
docker-compose down                                    # stop, keep volume
docker-compose down -v                                 # stop + wipe ChromaDB volume
```
