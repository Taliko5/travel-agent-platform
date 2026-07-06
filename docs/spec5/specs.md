# Step 5 Technical Specifications

## File Structure

```
travel-agent-platform/
├── .dockerignore                          ← new
├── docker-compose.yaml                    ← fill in (was empty placeholder)
├── backend/
│   ├── .env.example                       ← new
│   ├── Dockerfile                         ← new
│   └── ... (existing files unchanged)
└── Infrastructure/
    └── k8s/
        ├── backend-deployment.yaml        ← new
        └── backend-service.yaml           ← new
```

---

## `.dockerignore` Specification

**Location:** project root (same level as `docker-compose.yaml`)

**Purpose:** Prevents large or sensitive directories from being sent to the Docker build daemon as part of the build context. Keeps builds fast and images clean.

```
**/__pycache__/
**/*.pyc
**/*.pyo
**/venv/
**/.venv/
**/.env
**/rag/chroma_db/
**/tests/
**/docs/
.git/
.gitignore
**/.pytest_cache/
```

---

## `backend/Dockerfile` Specification

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

### Layer caching order

| Layer | Invalidated when |
|---|---|
| `FROM python:3.13-slim` | Base image changes |
| `COPY requirements.txt` + `RUN pip install` | `requirements.txt` changes |
| `COPY . .` | Any source file changes |

The `requirements.txt` layer is cached independently of source changes. A code edit does not re-run `pip install` — rebuilds complete in seconds.

### `PYTHONPATH=/app`

The backend's import structure assumes `backend/` is the root:

```python
from agent.state import AgentState      # backend/agent/state.py
from mcp_servers.weather_server import get_weather
```

Setting `PYTHONPATH=/app` (where `/app` = `backend/`) makes these imports resolve correctly regardless of the process working directory inside the container.

### Why `--host 0.0.0.0`

Docker containers have their own network namespace. Uvicorn's default `--host 127.0.0.1` binds only to the loopback interface inside the container, which is unreachable from the host or from other containers. `0.0.0.0` binds to all interfaces, making the port reachable via the published port mapping.

---

## `docker-compose.yaml` Specification

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

### Field reference

| Field | Value | Reason |
|---|---|---|
| `build.context` | `./backend` | All `COPY` instructions in the Dockerfile are relative to `backend/` |
| `ports` | `"8000:8000"` | Maps host port 8000 → container port 8000 |
| `env_file` | `./backend/.env` | Injects `GOOGLE_API_KEY` at runtime; not baked into the image |
| `volumes` (named) | `chroma_data:/app/rag/chroma_db` | ChromaDB index persists across container restarts |
| `healthcheck.test` | `curl -f /health` | Uses the existing FastAPI `/health` endpoint |
| `healthcheck.start_period` | `10s` | Gives uvicorn time to start before health checks begin |

### ChromaDB volume lifecycle

```
docker-compose up           → volume created (empty); ingest required once
docker-compose down         → containers removed; volume persists
docker-compose down -v      → containers + volume removed; ingest required again
docker-compose up           → volume reused; no ingest needed
```

First-run ingest command:
```bash
docker-compose exec backend python rag/ingest.py
```

---

## `Infrastructure/k8s/backend-deployment.yaml` Specification

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

### Probe design

| Probe | Purpose | Trigger |
|---|---|---|
| `readinessProbe` | Holds traffic until uvicorn is ready | Pod starts, or after a crash |
| `livenessProbe` | Restarts the container if the app hangs | `/health` stops responding |

Both probes use the same `/health` endpoint already in the FastAPI app.

### `GOOGLE_API_KEY` via Secret

The API key is stored in a Kubernetes Secret (not a ConfigMap — Secrets are base64-encoded and can be restricted with RBAC). Create the Secret before applying the Deployment:

```bash
kubectl create secret generic travel-agent-secrets \
  --from-literal=google-api-key=YOUR_KEY_HERE
```

In Step 8 (AWS), this will be replaced with AWS Secrets Manager + the External Secrets Operator, or injected via ECS task definition secrets.

### `replicas: 1`

Single replica is appropriate for development and demo. In Step 8, this will be increased and paired with a HorizontalPodAutoscaler (HPA) based on CPU utilisation.

---

## `Infrastructure/k8s/backend-service.yaml` Specification

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

### Port mapping

```
External request → port 80 (Service) → port 8000 (container)
```

Inside the cluster, other services can reach the backend at `http://travel-agent-backend/chat`.

### `ClusterIP` → `LoadBalancer` upgrade path

| Step | Service type | Access |
|---|---|---|
| Step 5 (now) | `ClusterIP` | Within cluster only |
| Step 8 (AWS) | `LoadBalancer` or ALB Ingress | Public internet |

Changing from `ClusterIP` to `LoadBalancer` is a one-line edit in the manifest. No other files need to change.

---

## `backend/.env.example` Specification

```
# Copy this file to .env and fill in your values.
# The real .env is gitignored — never commit it.
GOOGLE_API_KEY=your-google-api-key-here
```

Committed to git. Serves as documentation and a setup template. New contributors:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and set GOOGLE_API_KEY
```

---

## API Contract: Unchanged

The `POST /chat` contract does not change in Step 5. Docker is purely an infrastructure concern — the application code is not modified.

| Endpoint | Method | Behaviour |
|---|---|---|
| `/health` | GET | Returns `{"status": "ok"}` — used by healthcheck and probes |
| `/chat` | POST | `{"message": "..."}` → `{"intent": "...", "response": "..."}` |

---

## Common Commands Reference

```bash
# Build and start
docker-compose up --build

# Start in background
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Run ingest (first-time or after volume wipe)
docker-compose exec backend python rag/ingest.py

# Run tests inside container
docker-compose exec backend python -m pytest tests/ -v

# Stop (keep volume)
docker-compose down

# Stop and wipe ChromaDB volume
docker-compose down -v

# Validate k8s manifests (no cluster needed)
kubectl apply --dry-run=client -f Infrastructure/k8s/
```
