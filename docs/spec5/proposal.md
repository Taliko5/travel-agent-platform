# Step 5 Proposal: Docker + docker-compose

## What We Are Building

A fully containerized local development environment that packages the FastAPI backend into a Docker image and orchestrates it with docker-compose. A Kubernetes Deployment and Service manifest will also be produced as the foundation for Step 8 (AWS deployment).

---

## Why Docker Now

The backend currently runs only inside a hand-crafted `venv`. This creates three concrete problems:

| Problem | Impact |
|---|---|
| "Works on my machine" | A new contributor needs to replicate the exact Python version, package versions, and `.env` setup manually — error-prone and undocumented |
| CI/CD has nothing to run | Step 6 (GitHub Actions) needs a build artifact. Without Docker there is no reproducible unit to test and push |
| AWS deployment is blocked | Step 8 deploys a container image to ECS/EKS. Docker must come first |

Docker solves all three: one `docker build` produces a portable image that behaves identically in dev, CI, and production.

---

## Scope of This Step

**In scope:**
- `backend/Dockerfile` — build the FastAPI backend into a Python 3.13-slim image
- `.dockerignore` — prevent `venv/`, `__pycache__/`, `.env`, and `chroma_db/` from entering the build context
- `docker-compose.yaml` — wire up the backend service with ports, environment, and a named volume for ChromaDB persistence
- `Infrastructure/k8s/backend-deployment.yaml` — Kubernetes Deployment (1 replica)
- `Infrastructure/k8s/backend-service.yaml` — Kubernetes Service (ClusterIP)

**Out of scope:**
- Frontend container — `frontend/` is not yet built
- Multi-stage builds — not needed until image size is a concern
- ECR push / Kubernetes cluster provisioning — Step 8
- TLS / ingress — Step 8
- Secrets management (AWS Secrets Manager, k8s Secrets) — Step 8

---

## Technology Choices

### Base image: `python:3.13-slim`

Matches the dev Python version exactly (`backend/venv` was created with Python 3.13). The `-slim` variant omits build tools and docs — reduces image size by ~200 MB compared to the full image. No Alpine: Alpine's musl libc can cause subtle compatibility issues with Python C-extension packages (ChromaDB, numpy).

Alternative considered: `python:3.13-alpine` — rejected due to musl compatibility risk with ChromaDB's native dependencies.

### No virtualenv inside the container

In a Docker container, isolation is provided by the container itself. Creating a venv inside adds a layer of indirection with no benefit. Packages are installed directly into the system Python with `pip install --no-cache-dir`.

### ChromaDB persistence: named volume (embedded mode for now)

ChromaDB writes its SQLite database and embedding index to `rag/chroma_db/`. If this directory is not mounted as a volume, re-ingestion is required every time the container starts. A named Docker volume (`chroma_data`) persists across `docker-compose down` / `docker-compose up` cycles.

Note: `docker-compose down -v` removes the volume (and data). This is intentional — use it when you want a clean re-ingest.

**Architectural decision — ChromaDB migration plan:**

In Step 5, ChromaDB runs in **embedded mode** (a library call inside the backend process, data stored on a named volume). This is the simplest correct approach for a single-container setup.

In Step 8 (Kubernetes / AWS), ChromaDB will be migrated to **server mode** — a standalone container or StatefulSet with its own persistent volume, accessed by the backend over HTTP. This mirrors how production systems treat stateful services: separate lifecycle, independent scaling, and no shared filesystem dependencies between pods.

| Step | ChromaDB mode | Why |
|---|---|---|
| Step 5 (now) | Embedded, named Docker volume | One variable at a time — containerise first, then separate services |
| Step 8 (K8s/AWS) | Server mode, standalone StatefulSet | Required for multi-replica deployments; pods cannot share a named volume |

The tool interface (`retrieve_context(query)` in `rag/retriever.py`) does not change between modes — only the ChromaDB client initialisation changes from `chromadb.PersistentClient(path=...)` to `chromadb.HttpClient(host=..., port=...)`. The agent graph and API are unaffected.

### Secrets: `env_file` in docker-compose

The `backend/.env` file holds `GOOGLE_API_KEY`. It must not be baked into the image (`COPY .env .` would embed the secret in every layer). docker-compose's `env_file` directive injects it at runtime without touching the image.

The `.dockerignore` file explicitly excludes `.env` as a second line of defence.

### Kubernetes: ClusterIP Service

For local development and CI testing, `ClusterIP` is sufficient — it makes the backend reachable within the cluster. In Step 8 it will be upgraded to `LoadBalancer` (or fronted by an ALB Ingress) when external access is needed.

---

## What This Looks Like After Step 5

```bash
# Start the whole stack (from project root)
docker-compose up --build

# Hit the API
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hotels in Tokyo"}'

# Stop and clean up
docker-compose down
```

A new contributor clones the repo, copies `.env.example` to `backend/.env`, adds their API key, and runs `docker-compose up`. No Python installation, no venv, no pip commands needed.

---

## What This Unlocks

| Step | Dependency on Step 5 |
|---|---|
| Step 6 (CI/CD) | GitHub Actions runs `docker build` to verify the image builds; pytest runs inside the container |
| Step 7 (Observability) | Prometheus and Grafana are added as additional docker-compose services |
| Step 8 (AWS) | The same image is pushed to ECR and pulled by ECS/EKS |

The k8s manifests produced in this step are the exact files Step 8 will apply with `kubectl apply -f`.
