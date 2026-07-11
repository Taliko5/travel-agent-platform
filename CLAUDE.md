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

# Lint
ruff check backend/

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
    └── test_step4_weather.py

frontend/
├── src/theme/index.ts      extendTheme(): unicorn color scales, chatRadius, fonts
└── src/app/
    ├── page.tsx            renders <ChatInterface />
    ├── providers.tsx       "use client" ChakraProvider wrapper
    └── components/
        ├── ChatInterface.tsx  orchestrator: state + POST /chat fetch, composes below
        ├── SparkleHeader.tsx  decorative accents (no state)
        ├── MessageList.tsx    maps messages[] → MessageBubble
        ├── MessageBubble.tsx  single message + conditional intent label
        └── ChatInput.tsx      input + star send button
```

## Patterns to Know

**Lazy initialization** — `get_model()` and `get_vectorstore()` use `@lru_cache(maxsize=1)`. The Gemini client and ChromaDB are only instantiated on first call, not at import time. This is what lets `pytest` pass without `GOOGLE_API_KEY`.

**Patching in tests** — patch `agent.nodes.get_model`, not `agent.nodes.model`. Set the return value: `mock_get_model.return_value.invoke.return_value = mock_response`.

**Intent routing** — `route_by_intent()` in `graph.py`. Transportation intent splits further: flight keywords → `call_flight_tool`, otherwise → `retrieve_context`.

**State flow** — all nodes receive and return the full `AgentState` dict (`{**state, "field": value}`). Unused fields are `None`, not absent.

## Docs

- `docs/plan.md` — step-by-step roadmap and progress
- `docs/step4.md` — MCP servers (weather / flights / hotels)
- `docs/step5.md` — Docker + docker-compose + k8s
- `docs/step6.md` — Frontend (Next.js 14 / TypeScript)
- `docs/step7.md` — GitHub Actions CI/CD
