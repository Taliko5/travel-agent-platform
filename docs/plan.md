# Plan

## Roadmap

| Step | Description | Status |
|---|---|---|
| 1–2 | LangGraph agent (intent classify + response) | Done |
| 3a | RAG: ChromaDB ingest + retriever | Done |
| 3b | RAG: Wire retriever into agent graph | Done |
| 4 | MCP servers — weather, flights, hotels | Done |
| 5 | Docker + docker-compose + k8s manifests | Done |
| 6 | Frontend — Next.js 14 / TypeScript | Done |
| 7 | GitHub Actions CI/CD | Next |
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

See `docs/step6.md` and `openspec/changes/add-chat-frontend/`.

Built: Next.js 14 (App Router, TypeScript) chat UI, Chakra UI pastel "unicorn" theme. `frontend/src/app/components/` split into `ChatInterface.tsx` (state + `POST /chat` fetch), `MessageList.tsx`, `MessageBubble.tsx`, `ChatInput.tsx` (star send button), `SparkleHeader.tsx` — one component per concern so each can be swapped independently later. Containerized (`frontend/Dockerfile`) and added to `docker-compose.yaml`.

Also required adding `CORSMiddleware` to `backend/api/main.py` (`allow_origins=["http://localhost:3000"]`) — discovered during smoke testing that the backend had none, which silently blocked every browser `fetch` despite `curl` working fine.

Verified: `npm run dev` + local backend, and full `docker-compose up --build` — both confirmed intent + response round-trip end-to-end.

**UI polish** (`openspec/changes/improve-chat-ui/`): assistant responses now render as real markdown (`react-markdown` + `remark-gfm`, headings/bold/lists) instead of literal `#`/`**` characters via `MessageBubble.tsx`. New `ThinkingIndicator.tsx` shows a three-dot bounce + "...thinking" bubble in the message list while a request is in flight. `ChatInterface.tsx`'s outer panel now has a visible border/shadow card treatment, and the page background (`globals.css`) carries the unicorn pastel gradient that was previously accent-only. Also bumped frontend Node runtime 20 → 24 (latest LTS): `frontend/.nvmrc`, `package.json` `engines`, and `Dockerfile` base image all updated; `tsc`/`build`/`dev` verified clean under Node 24.18.0.

**Step 6c: Testing, Linting & Formatting** (`openspec/changes/step6c-test-lint-format/`): closed the gap left by Step 7's CI draft, which found the frontend had zero automated tests and no formatter, and the backend had no coverage for its actual request-handling path.

Frontend: Vitest + React Testing Library + jsdom (chosen over Jest for faster startup and less config against this Next.js/ESM setup). `frontend/src/test-utils.tsx` exports `renderWithProviders`, wrapping RTL's `render` with the real `Providers`/`ChakraProvider` component — every component test uses it instead of bare `render`, since the app always mounts inside the custom "unicorn" theme. 6 new test files, 21 tests, covering `ChatInput`, `MessageBubble` (including markdown rendering), `MessageList`, `ThinkingIndicator`, and `ChatInterface` (mocked `fetch`, asserts request shape + response rendering + loading-indicator lifecycle); `SparkleHeader` gets a smoke test only, being stateless/decorative. Added Prettier + `eslint-config-prettier` (`.prettierrc`, `format`/`format:check` scripts) and `@vitest/coverage-v8` (report-only, no thresholds). `frontend/package.json` also gained `eslint` + `eslint-config-next` here, since `harden-ci-pipeline` (the change that was going to add them) hadn't landed yet.

Backend: 3 new test files closing coverage gaps in `agent/graph.py` (`route_by_intent` branching), `api/main.py` (`/health`, `/`, `/chat` via `TestClient` with `api.main.graph` mocked — no LLM call, no API key needed — plus CORS header assertions), and `rag/retriever.py` (`retrieve_context` with `get_vectorstore` mocked). 63 tests total, all passing. Also discovered `pytest`, `pytest-asyncio`, and `ruff` were installed locally but never frozen into `backend/requirements.txt` — meaning CI's `pip install -r requirements.txt` step wouldn't have actually provided them; added all three plus `pytest-cov`. `ruff format --check backend/` and `pytest --cov=backend --cov-report=term` (report-only coverage) are now wired into the CI `test` job.

Frontend CI wiring (format-check, real `npm test`, coverage as actual workflow steps) is verified working locally but not yet wired into `.github/workflows/ci.yml` — that requires the `frontend` job `harden-ci-pipeline` introduces, which hadn't been applied yet at the time this landed.

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
