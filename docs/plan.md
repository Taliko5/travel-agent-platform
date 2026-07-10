# Plan

## Roadmap

| Step | Description | Status |
|---|---|---|
| 1–2 | LangGraph agent (intent classify + response) | Done |
| 3a | RAG: ChromaDB ingest + retriever | Done |
| 3b | RAG: Wire retriever into agent graph | Done |
| 4 | MCP servers — weather, flights, hotels | Done |
| 5 | Docker + docker-compose + k8s manifests | Done |
| 6 | Frontend — Next.js 14 / TypeScript | Next |
| 7 | GitHub Actions CI/CD | Planned |
| 8 | Observability (Grafana, Prometheus, OpenTelemetry) | Planned |
| 9 | AWS deployment (ECS / EKS) | Planned |

---

## Steps 1–2: LangGraph Agent

- `agent/state.py` — `AgentState` TypedDict
- `agent/nodes.py` — `classify_intent`, `generate_response` using `gemini-3.5-flash`
- `agent/graph.py` — `build_graph()`, linear: START → classify → generate → END
- `api/main.py` — FastAPI with `GET /health` and `POST /chat`

Decisions: Gemini over OpenAI (free tier); `thinking_level="low"` for speed; intent allowlist + `.strip().lower()` + `next()` double validation.

---

## Step 3a: RAG — ChromaDB Ingest + Retriever

- `rag/data/` — 4 destination files (Abu Dhabi, Fukuoka, Lima, Riga)
- `rag/ingest.py` — embeds with `gemini-embedding-001`, saves to ChromaDB
- `rag/retriever.py` — `retrieve_context(query, k=2)` with lazy `get_vectorstore()`

---

## Step 3b: Wire RAG into Agent

- `context: Optional[str]` added to `AgentState`
- `retrieve_context_node` added to `nodes.py`
- Graph updated: classify → retrieve → generate

---

## Step 4: MCP Servers

See `docs/step4.md`.

Built: `weather_server.py` (live), `flight_server.py` (mock), `hotel_server.py` (mock), conditional routing in graph, `call_*_tool` nodes, lazy init for `get_model()` and `get_vectorstore()`.

Tests: 47 tests, all mocked, pass without `GOOGLE_API_KEY`.

---

## Step 5: Docker + docker-compose

See `docs/step5.md`.

Built: `backend/Dockerfile`, `.dockerignore`, `docker-compose.yaml`, `backend/.env.example`, `Infrastructure/k8s/backend-deployment.yaml`, `Infrastructure/k8s/backend-service.yaml`.

---

## Step 6: Frontend

See `docs/step6.md`.

Goal: chat UI in Next.js 14 / TypeScript connecting to `POST /chat`. Shows intent and AI response. Containerized and added to docker-compose.

---

## Step 7: GitHub Actions CI/CD

See `docs/step7.md`.

Goal: two-job pipeline (test + build) on push to `main` and PRs. No secrets required — all tests mocked. Step 8 adds a third `push` job for ECR.

---

## Step 8: Observability

Stack: OpenTelemetry → FastAPI and LangGraph instrumentation; Prometheus → metrics scraping; Grafana → dashboards; CloudWatch → AWS log aggregation.

Key metrics: `/chat` latency (p50/p95/p99), intent distribution, LLM call duration, RAG retrieval rate.

---

## Step 9: AWS Deployment

Options: ECS (simpler) or EKS (matches k8s manifests from Step 5). Infrastructure via Terraform: VPC, cluster, ECR, ALB.

Prerequisites: Steps 5 and 7 complete (Docker image + CI pushing to ECR).
