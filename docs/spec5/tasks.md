# Step 5 Tasks

## Task List

### Docker

| # | Task | File(s) | Depends On |
|---|---|---|---|
| 5.1 | Create `.dockerignore` | `.dockerignore` | — |
| 5.2 | Create `backend/Dockerfile` | `backend/Dockerfile` | 5.1 |
| 5.3 | Smoke test: `docker build` succeeds | — | 5.2 |
| 5.4 | Fill in `docker-compose.yaml` | `docker-compose.yaml` | 5.3 |
| 5.5 | Smoke test: `docker-compose up` starts cleanly | — | 5.4 |
| 5.6 | Verify `/health` and `/chat` respond inside container | — | 5.5 |

### Kubernetes

| # | Task | File(s) | Depends On |
|---|---|---|---|
| 5.7 | Create `Infrastructure/k8s/backend-deployment.yaml` | `Infrastructure/k8s/backend-deployment.yaml` | 5.3 |
| 5.8 | Create `Infrastructure/k8s/backend-service.yaml` | `Infrastructure/k8s/backend-service.yaml` | 5.7 |
| 5.9 | Validate manifests with `kubectl dry-run` | — | 5.7, 5.8 |

### Wrap-up

| # | Task | File(s) | Depends On |
|---|---|---|---|
| 5.10 | Create `backend/.env.example` | `backend/.env.example` | — |
| 5.11 | Update `docs/steps.md` Step 5 row to ✅ | `docs/steps.md` | 5.6, 5.9 |

---

## Task Detail

### 5.1 — Create `.dockerignore`

Create at the **project root** (same directory as `docker-compose.yaml`).

```
# Python
**/__pycache__/
**/*.pyc
**/*.pyo
**/venv/
**/.venv/

# Environment / secrets
**/.env

# ChromaDB data (re-ingested from a volume, not baked into image)
**/rag/chroma_db/

# Tests and docs (not needed at runtime)
**/tests/
**/docs/

# Git and editor
.git/
.gitignore
**/.pytest_cache/
```

---

### 5.2 — Create `backend/Dockerfile`

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Key decisions:
- `WORKDIR /app` — all paths inside the container are relative to `/app`
- `COPY requirements.txt` then `RUN pip install` **before** `COPY . .` — this layer is cached unless `requirements.txt` changes, so rebuilds are fast when only source files change
- `ENV PYTHONPATH=/app` — allows `from agent.state import ...` to resolve from any working directory
- `--host 0.0.0.0` — required for Docker; default `127.0.0.1` is not reachable from outside the container

---

### 5.3 — Smoke Test: `docker build`

```bash
# From project root
docker build -f backend/Dockerfile backend/ -t travel-agent-backend:local

# Expected: no errors, image appears in docker images
docker images | grep travel-agent-backend
```

The build should complete without errors. If it fails on a package install, check that `requirements.txt` is current (`pip freeze > requirements.txt` inside venv).

---

### 5.4 — Fill in `docker-compose.yaml`

Replace the empty `docker-compose.yaml` at the project root with:

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    volumes:
      - chroma_data:/app/rag/chroma_db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

volumes:
  chroma_data:
```

Key decisions:
- `env_file: ./backend/.env` — injects `GOOGLE_API_KEY` at runtime; `.env` is never in the image
- `chroma_data` named volume — ChromaDB index persists across `down` / `up` cycles
- `healthcheck` — docker-compose marks the container `healthy` only after `/health` responds 200

Note on re-ingestion: the ChromaDB volume starts empty on first run. The RAG data must be ingested once after the container starts:

```bash
docker-compose exec backend python rag/ingest.py
```

---

### 5.5 — Smoke Test: `docker-compose up`

```bash
docker-compose up --build
```

Expected output (last few lines):
```
backend-1  | INFO:     Application startup complete.
backend-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

If the container exits immediately, check logs: `docker-compose logs backend`.

---

### 5.6 — Verify `/health` and `/chat`

With the container running, in a separate terminal:

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status": "ok"}

# Chat (non-RAG query — no ingest needed)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the weather in Tokyo?"}'
# Expected: intent = "weather", response includes temperature

# Chat (hotel query — requires ingest first)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hotels in Lima"}'
# Expected: intent = "hotel", response includes mock hotel names
```

---

### 5.7 — Create `backend-deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: travel-agent-backend
  labels:
    app: travel-agent-backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: travel-agent-backend
  template:
    metadata:
      labels:
        app: travel-agent-backend
    spec:
      containers:
        - name: backend
          image: travel-agent-backend:latest
          ports:
            - containerPort: 8000
          env:
            - name: GOOGLE_API_KEY
              valueFrom:
                secretKeyRef:
                  name: travel-agent-secrets
                  key: google-api-key
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
```

The `GOOGLE_API_KEY` is read from a k8s Secret named `travel-agent-secrets`. Create it with:
```bash
kubectl create secret generic travel-agent-secrets \
  --from-literal=google-api-key=<your-key>
```

---

### 5.8 — Create `backend-service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: travel-agent-backend
spec:
  selector:
    app: travel-agent-backend
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
```

`ClusterIP` makes the backend reachable within the cluster at `travel-agent-backend:80`. In Step 8 this will be changed to `LoadBalancer` or fronted by an ALB Ingress Controller.

---

### 5.9 — Validate Manifests with `kubectl dry-run`

```bash
kubectl apply --dry-run=client -f Infrastructure/k8s/backend-deployment.yaml
kubectl apply --dry-run=client -f Infrastructure/k8s/backend-service.yaml
```

Both should print `configured (dry run)` with no errors when a cluster is reachable.

**Note:** `kubectl apply --dry-run=client` always fetches the API group list from the cluster to resolve resource types — it cannot run fully offline even with `--validate=false`. If no cluster is available locally, validate YAML structure instead:

```bash
python3 -c "
import yaml
for f in ['Infrastructure/k8s/backend-deployment.yaml', 'Infrastructure/k8s/backend-service.yaml']:
    doc = yaml.safe_load(open(f))
    print(f\"{f} → kind={doc['kind']} name={doc['metadata']['name']} ✓\")
"
```

Full `kubectl` validation will run in Step 8 when a cluster is provisioned.

---

### 5.10 — Create `backend/.env.example`

```
# Copy this file to .env and fill in your values
GOOGLE_API_KEY=your-google-api-key-here
```

This file is committed to git. The real `backend/.env` is gitignored. New contributors use this as the setup template.

---

## Definition of Done

- [ ] `docker build -f backend/Dockerfile backend/` exits 0
- [ ] `docker-compose up` starts the backend and marks it healthy
- [ ] `GET /health` returns 200 from inside the container
- [ ] `POST /chat` with a weather query returns a valid response from inside the container
- [ ] `kubectl apply --dry-run=client` passes for both k8s manifests
- [ ] `backend/.env.example` is committed; real `.env` is not
- [ ] `docs/steps.md` Step 5 row updated to ✅
