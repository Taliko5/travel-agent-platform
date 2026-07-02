# Design: Travel Agent Platform

## System Architecture

```
User / Frontend (Next.js)
        |
        | HTTP POST /chat
        v
  FastAPI (port 8000)
        |
        v
  LangGraph Agent
    ┌─────────────────────────────────┐
    │  AgentState flows through nodes  │
    │                                  │
    │  [classify_intent]               │
    │       ↓                          │
    │  [retrieve_context] (RAG)        │
    │       ↓                          │
    │  [generate_response]             │
    └─────────────────────────────────┘
        |                  |
        v                  v
   ChromaDB            MCP Servers (Step 4+)
  (vector store)      weather_server.py
                      flight_server.py
                      hotel_server.py
```

## Component Decisions

### LLM: Google Gemini (`gemini-3.5-flash`)
- Free tier available; suitable for development
- `thinking_level="low"` balances speed and reasoning quality
- Response parsing handles list format returned by thinking-enabled models

### Agent Framework: LangGraph
- Chosen over plain LangChain chains because it supports explicit stateful, multi-node flows
- `StateGraph` + `TypedDict` state makes data flow explicit and type-checked
- Replaces LangChain's older `AgentExecutor` (deprecated as of 2025)

### API: FastAPI + Uvicorn
- Async-native: matches LLM call latency patterns
- Pydantic models validate request/response shapes at the boundary
- Auto-generated `/docs` serves as API documentation

### Vector Store: ChromaDB
- Local-first; no external service dependency during development
- `persist_directory` saves the store to disk — survives restarts without re-ingestion
- Semantic search via cosine similarity on embeddings (not keyword matching)

### Embeddings: `gemini-embedding-001`
- Separate model from the chat LLM (embedding models have different API endpoints)
- Text-only; sufficient for the current travel guide documents
- Upgrade path: `gemini-embedding-2` (multimodal) when image/document support is needed

### MCP Protocol: FastMCP (from `mcp[cli]`)
- FastMCP wraps the official MCP Python SDK with a decorator-based API
- Tools run as **separate processes**, communicating via stdio or HTTP/SSE
- This decouples tool logic from the agent — tools are reusable by any MCP-compatible client (Claude Desktop, Claude Code, future agents)
- Decision: use FastMCP (not plain LangChain `@tool`) to produce a genuine MCP server

## Data Flow: `/chat` Request

```
POST /chat  {"message": "hotels in Kyoto under $200"}
    |
    v
AgentState = {
  user_input: "hotels in Kyoto under $200",
  intent: None,
  context: None,        # RAG result (Step 3 pending integration)
  response: None
}
    |
    v
classify_intent node
  → prompt: "classify into: transportation, hotel, weather, general"
  → LLM returns raw text → stripped → allowlist-filtered
  → state.intent = "hotel"
    |
    v
retrieve_context node  [TODO: wire in]
  → embed user_input
  → similarity_search(k=2) against ChromaDB
  → state.context = "Kyoto is known for... best hotels include..."
    |
    v
generate_response node
  → prompt includes intent + user_input + context
  → LLM returns ~200-word response with URLs
  → state.response = "..."
    |
    v
ChatResponse { intent: "hotel", response: "..." }
```

## State Schema

```python
class AgentState(TypedDict):
    user_input: str           # original user message
    intent: Optional[str]     # transportation | hotel | weather | general
    context: Optional[str]    # RAG-retrieved destination text (to be added)
    response: Optional[str]   # final LLM response
```

**Note:** `context` field is not yet in `state.py` — needs to be added when RAG is wired into the graph (see Steps).

## Intent Categories

| Intent | Covers |
|---|---|
| `transportation` | flights, trains, buses, routes between cities |
| `hotel` | accommodation, lodging, stays |
| `weather` | climate, seasons, best time to visit |
| `general` | catch-all — sightseeing, food, culture, unknown |

## MCP Server Design

Each MCP server is a standalone Python process:

```
backend/mcp-servers/
├── weather_server.py   # Open-Meteo API (no API key needed)
├── flight_server.py    # mock / future Amadeus/Skyscanner
└── hotel_server.py     # mock / future Booking.com
```

Each exposes `@mcp.tool()` functions. The LangGraph agent connects to them via an MCP client (to be added to `nodes.py` or as a separate node).

Weather API flow (2-step, no key required):
1. `GET geocoding-api.open-meteo.com/v1/search?name={city}` → lat/lon
2. `GET api.open-meteo.com/v1/forecast?latitude=...&longitude=...&current=temperature_2m` → weather

## Infrastructure Plan (Steps 5–8)

| Layer | Technology | Purpose |
|---|---|---|
| Containerization | Docker + docker-compose | Local parity; single-command startup |
| Orchestration | Kubernetes (k8s) | Production deployment target |
| Cloud | AWS ECS / EKS | Managed container hosting |
| CI/CD | GitHub Actions | Automated test → build → deploy |
| Metrics | Prometheus + Grafana | Dashboards, alerting |
| Tracing | OpenTelemetry | Distributed trace of agent calls |
| Logging | CloudWatch | Centralized log aggregation on AWS |

## Known Issues / Pending Work

1. **RAG not wired into agent** — `retriever.py` works standalone but `nodes.py` does not call it yet. `generate_response` currently sends no retrieved context to the LLM. Fix: add a `retrieve_context` node between `classify_intent` and `generate_response`, and add `context: Optional[str]` to `AgentState`.

2. **Only 4 destination files** — `rag/data/` has abudhabi, fukuoka, lima, riga. More cities (especially Tokyo, Kyoto, Osaka, NYC) should be added to improve recall coverage.

3. **No MCP client in agent** — `weather_server.py` does not exist yet. Once created, a MCP client call needs to be added to the graph for weather-intent queries.

4. **`generate_response` is intent-blind** — the current prompt sends intent to the LLM as a label but doesn't change behavior based on it. Future: branch the graph on intent to call different tools (MCP weather, MCP hotel search, etc.).
