# Travel Agent Platform

AI-powered travel planning agent. User asks a travel question → intent classified → relevant tool called (live weather / mock flights / mock hotels / RAG) → grounded response generated.

## Commands

```bash
# Backend
cd backend
source venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                          # localhost:3000

# Tests (no API key needed — all mocked)
cd backend && pytest tests/ -v
cd frontend && npm test              # Vitest + React Testing Library

# Coverage (report-only, doesn't fail the build)
cd backend && pytest --cov=. --cov-report=term tests/ -v
cd frontend && npm test -- --coverage

# Lint
ruff check backend/
cd frontend && npm run lint          # ESLint (next/core-web-vitals)

# Format
ruff format backend/                 # ruff format --check backend/ to check only
cd frontend && npm run format        # npm run format:check to check only

# Ingest travel guides into ChromaDB (run once)
cd backend && python rag/ingest.py

# Docker (full stack)
docker-compose up --build
docker-compose exec backend python rag/ingest.py   # first-time ingest
docker-compose down
```

## Architecture

```
Next.js 14 (frontend/ — localhost:3000)
    │
    │ POST /chat
    ▼
FastAPI (api/main.py — localhost:8000)
    │
    ▼
LangGraph Agent
    ├── classify_intent          (gemini-3.5-flash)
    │       ↓ route_by_intent
    ├── call_weather_tool        → Open-Meteo live API
    ├── call_flight_tool         → mock data
    ├── call_hotel_tool          → mock data
    └── retrieve_context         → ChromaDB RAG
            ↓
    generate_response            (gemini-3.5-flash)
```

## Key Files

```
backend/
├── agent/
│   ├── state.py            AgentState TypedDict
│   ├── nodes.py            all node functions + get_model()
│   └── graph.py            build_graph() + route_by_intent()
├── api/main.py             FastAPI app
├── mcp_servers/
│   ├── weather_server.py   get_weather(city)
│   ├── flight_server.py    search_flights(query)
│   └── hotel_server.py     search_hotels(query)
├── rag/
│   ├── ingest.py           embed + store in ChromaDB
│   └── retriever.py        retrieve_context() + get_vectorstore()
└── tests/
    ├── test_step4_flights.py
    ├── test_step4_hotels.py
    ├── test_step4_weather.py
    ├── test_graph_routing.py     route_by_intent branching
    ├── test_api_main.py          /health, /, /chat + CORS (api.main.graph mocked)
    └── test_rag_retriever.py     retrieve_context (get_vectorstore mocked)

frontend/
├── src/theme/index.ts      extendTheme(): unicorn color scales, chatRadius, fonts
├── src/test-utils.tsx      renderWithProviders — RTL render wrapped with real Providers
├── vitest.config.ts        jsdom env, @vitest/coverage-v8, path alias @/* → src/*
└── src/app/
    ├── page.tsx            renders <ChatInterface />
    ├── providers.tsx       "use client" ChakraProvider wrapper
    └── components/
        ├── ChatInterface.tsx  orchestrator: state + POST /chat fetch, composes below
        ├── SparkleHeader.tsx  decorative accents (no state)
        ├── MessageList.tsx    maps messages[] → MessageBubble
        ├── MessageBubble.tsx  single message + conditional intent label
        ├── ChatInput.tsx      input + star send button
        └── *.test.tsx         one test file per component above, colocated
```

## Patterns to Know

**Lazy initialization** — `get_model()` and `get_vectorstore()` use `@lru_cache(maxsize=1)`. The Gemini client and ChromaDB are only instantiated on first call, not at import time. This is what lets `pytest` pass without `GOOGLE_API_KEY`.

**Patching in tests** — patch `agent.nodes.get_model`, not `agent.nodes.model`. Set the return value: `mock_get_model.return_value.invoke.return_value = mock_response`.

**Intent routing** — `route_by_intent()` in `graph.py`. Transportation intent splits further: flight keywords → `call_flight_tool`, otherwise → `retrieve_context`.

**State flow** — all nodes receive and return the full `AgentState` dict (`{**state, "field": value}`). Unused fields are `None`, not absent.

**Frontend test rendering** — always use `renderWithProviders` from `frontend/src/test-utils.tsx`, never RTL's bare `render`. Every component runs inside `<Providers>` (`ChakraProvider` + the custom "unicorn" theme) in production; bare `render` mounts without that context and either breaks theme-dependent styling or silently falls back to Chakra's defaults (a false pass).

**Backend `/chat` endpoint tests** — mock `api.main.graph` directly (`patch("api.main.graph")`, set `.ainvoke` to an `AsyncMock`), not the individual agent nodes. `build_graph()` only wires `StateGraph` nodes/edges at import time — it never invokes a node — so importing `api.main` needs no `GOOGLE_API_KEY` either way. Agent routing itself is covered separately in `test_graph_routing.py` and the Step 4 test files.

**Runtime version single-sourcing** — Node version lives in root `.nvmrc` (both `frontend/` and `.github/workflows/ci.yml`'s `setup-node` read it); Python version lives in `backend/.python-version` (`ci.yml`'s `setup-python` reads it via `python-version-file`). `backend/Dockerfile` and `frontend/Dockerfile` still hardcode their base image version separately — Docker `FROM` can't read a version file without extra `ARG` plumbing — so bumping a runtime version means updating the version file *and* the Dockerfile.

**CI path filtering** — `.github/workflows/ci.yml`'s `changes` job (`dorny/paths-filter`) gates `test`/`build-backend` on `backend/**` changes and `frontend`/`build-frontend` on `frontend/**` changes via per-step `if:` conditions, not job-level `if:`. This means a backend-only PR still shows `frontend`/`build-frontend` as green (steps no-op), not skipped/absent — required for branch-protection required-checks to stay satisfiable on every PR.

## Comments

Code carries the *what*. `docs/` and `openspec/` carry the *why*. A comment earns its place only
when a reader needs something at that exact line that neither the code nor the docs can give them.

Write a comment only when:

- The reason for the code is not recoverable by reading it — an ordering requirement, a
  workaround, a rate limit, a deliberate omission.
- A value looks arbitrary but is not: timeouts, retry counts, bucket boundaries, magic numbers.

Do not write a comment that:

- Restates the line below it (`# increment the counter`).
- Narrates structure (`# --- helpers ---`, `# imports`).
- Duplicates a docstring, a type hint, or a test name.
- Argues a design decision at length.

**Two lines is the target, not a hard limit.** Running a line or two over is fine for a
mechanical constraint that has no home in the docs — an import cycle, a library's actual
callback behaviour, a test-client default. A six-line paragraph is not. If the comment is long
enough to *argue* something, it belongs in `docs/` or `openspec/changes/*/` — leave a one-line
pointer instead:
`# Deliberately unseeded — see tasks.md Section 9.` Never delete the rationale; move it and point
at it. `TODO` comments follow the same budget: one line naming what is missing and where it is
tracked (`# TODO: no recording call sites yet — tasks.md Section 9-a`).

This rule does not apply to docstrings, or to tool directives such as `# noqa:`, `# type: ignore`
and `# pragma:`. Never delete a `# noqa` to save a line — it changes lint behaviour.

## Docs

- `docs/plan.md` — step-by-step roadmap and progress
- `docs/step4.md` — MCP servers (weather / flights / hotels)
- `docs/step5.md` — Docker + docker-compose + k8s
- `docs/step6.md` — Frontend (Next.js 14 / TypeScript)
- `docs/step7.md` — GitHub Actions CI/CD
- `docs/step8.md` — Observability (OpenTelemetry / Prometheus / Grafana)
