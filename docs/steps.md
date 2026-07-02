# Implementation Steps

## Progress Overview

| Step | Description | Status |
|---|---|---|
| 1–2 | LangGraph agent (intent classify + response) | ✅ Done |
| 3a | RAG: ChromaDB ingest + retriever | ✅ Done |
| 3b | RAG: Wire retriever into agent graph | ✅ Done |
| 4a | MCP Server — weather (live API) | ✅ Done |
| 4b | MCP Server — flights + hotels (mock) | 🔲 Next |
| 5 | Docker + docker-compose | 🔲 Planned |
| 6 | GitHub Actions CI/CD | 🔲 Planned |
| 7 | Observability (Grafana, Prometheus, OpenTelemetry) | 🔲 Planned |
| 8 | AWS deployment (ECS / EKS) | 🔲 Planned |

---

## Step 1–2: LangGraph Agent ✅

**What was built:**
- `backend/agent/state.py` — `AgentState` TypedDict with `user_input`, `intent`, `response`
- `backend/agent/nodes.py` — `classify_intent` and `generate_response` nodes using `gemini-3.5-flash`
- `backend/agent/graph.py` — `build_graph()` using `StateGraph`, linear flow: START → classify → generate → END
- `backend/api/main.py` — FastAPI with `GET /health` and `POST /chat`

**Key decisions made:**
- Gemini (not OpenAI) — free tier, sufficient for development
- `thinking_level="low"` — balance speed vs reasoning
- Intent allowlist `["transportation", "hotel", "weather", "general"]` + fallback to `"general"`
- Double validation: prompt instructs lowercase, code enforces `.strip().lower()` + `next()`

**Test:** `python test_graph.py` and `POST /chat` via `/docs`

---

## Step 3a: RAG — ChromaDB Ingest + Retriever ✅

**What was built:**
- `backend/rag/data/` — 4 destination text files (Abu Dhabi, Fukuoka, Lima, Riga), ~200 words each, tourist-oriented
- `backend/rag/ingest.py` — loads `.txt` files as `Document` objects, embeds with `gemini-embedding-001`, saves to ChromaDB
- `backend/rag/retriever.py` — `retrieve_context(query, k=2)` performs semantic similarity search

**Key decisions made:**
- Curated short files (not Wikipedia dumps) — reduces retrieval noise
- `gemini-embedding-001` (not `langchain-community`) — `langchain-community` was sunset May 2026
- `persist_directory="rag/chroma_db"` — survives restarts; ingest only needs to run once

**Test:** `python rag/retriever.py` — verified semantic search returns relevant destinations

---

## Step 3b: Wire RAG into Agent ✅

**What was built:**
- `context: Optional[str]` added to `AgentState`
- `retrieve_context_node` added to `nodes.py` — calls `retriever.retrieve_context(state["user_input"])`
- Graph updated: START → classify → retrieve → generate → END
- `generate_response` prompt includes `state["context"]` when present

**Test:** `python test_graph.py` — confirmed `context` is populated from ChromaDB and passed to the LLM.

---

## Step 4: MCP Server 🔲 Next

**Goal:** Build a real MCP server (not just a LangChain `@tool`) for weather data. The server runs as a separate process and communicates via the MCP protocol.

**Install:**
```bash
pip install "mcp[cli]" httpx
```

**File to create:** `backend/mcp-servers/weather_server.py`

**Implementation approach (use Claude Code):**
- Use `FastMCP` from `mcp.server.fastmcp`
- One `@mcp.tool()` async function: `get_weather(city: str) -> str`
- Two-step Open-Meteo API call (geocoding → forecast), no API key needed
- `httpx.AsyncClient` for async HTTP
- `if __name__ == "__main__": mcp.run()` to start the server

**After the server is built:**
- Test standalone: `python mcp-servers/weather_server.py`
- Add MCP client call in the agent graph for weather-intent queries
- Update `AgentState` with a `weather_data: Optional[str]` field if needed

**Why FastMCP over LangChain `@tool`:**
The tool runs in a separate process — it can be reused by Claude Desktop, Claude Code, and any future MCP-compatible agent. This is the key value of MCP: decoupled, reusable tooling.

---

## Step 5: Docker + docker-compose 🔲 Planned

**Goal:** Containerize the FastAPI backend so it runs identically in dev and production.

**Files to create:**
- `backend/Dockerfile`
- `docker-compose.yaml` (already exists as placeholder — fill in)

**Approach:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose** should run:
- `backend` service (FastAPI)
- `frontend` service (Next.js, once created)

**Also in this step:** Add `infra/k8s/` manifests (Deployment + Service) for the backend.

---

## Step 6: GitHub Actions CI/CD 🔲 Planned

**Goal:** Automate test → lint → build → push on every PR and push to `main`.

**File to create:** `.github/workflows/ci.yml`

**Pipeline stages:**
1. `pytest` — unit tests for nodes and graph
2. `ruff` or `flake8` — linting
3. `docker build` — verify image builds
4. On merge to `main`: push image to ECR (Step 8 dependency)

**Note:** Write tests for `classify_intent` and `retrieve_context` before this step.

---

## Step 7: Observability 🔲 Planned

**Goal:** Add metrics, traces, and dashboards to make the system inspectable in production.

**Stack:**
- OpenTelemetry SDK → instrument FastAPI and LangGraph calls
- Prometheus → scrape metrics endpoint
- Grafana → dashboards (latency, error rate, intent distribution)
- CloudWatch → log aggregation on AWS

**Key metrics to track:**
- `/chat` latency (p50, p95, p99)
- Intent classification distribution
- LLM call duration
- RAG retrieval hit rate

**Files to create:** `infra/monitoring/` (Grafana dashboard JSON, Prometheus config)

---

## Step 8: AWS Deployment 🔲 Planned

**Goal:** Deploy the backend to AWS, accessible over the internet.

**Options:**
- ECS (simpler, managed) — good starting point
- EKS (Kubernetes) — matches the k8s manifests from Step 5, production-grade orchestration

**Infrastructure as code:** `infra/terraform/` — VPC, ECS cluster or EKS cluster, ECR, ALB

**Prerequisites:** Steps 5 and 6 must be complete (Docker image + CI pipeline pushing to ECR).

---

## Immediate Next Actions

1. **Complete Step 3b** — wire RAG into the graph before moving to Step 4
2. **Add more destination files** — at least Tokyo, Kyoto, NYC to `rag/data/`, then re-run ingest
3. **Step 4** — use Claude Code to generate `weather_server.py`, then read and understand it
4. **Write at least 2 tests** before Step 6 (CI has nothing to run otherwise)
