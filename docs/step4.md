# Step 4: MCP Servers (Weather / Flights / Hotels)

## Goal

Add live and mock data tools to the agent via MCP servers. The agent routes to these based on classified intent.

| Server | Tool | Data |
|---|---|---|
| `weather_server.py` | `get_weather(city)` | Live — Open-Meteo |
| `flight_server.py` | `search_flights(query)` | Mock — 6 city pairs |
| `hotel_server.py` | `search_hotels(query)` | Mock — 6 cities |

## Decisions

**MCP over LangChain `@tool`** — tools follow the [Model Context Protocol](https://modelcontextprotocol.io) standard and are reusable by Claude Desktop, Claude Code, and future agents without copying code.

**Open-Meteo for weather** — no API key, global coverage, 10k req/day free. Two-step: geocoding API → lat/lon, forecast API → temperature.

**Mock data for flights/hotels** — real APIs (Amadeus, Booking.com) require paid credentials. Mock data validates routing and response generation. The tool interface is a drop-in replacement when a real API is added.

**`@lru_cache(maxsize=1)` on `get_model()` and `get_vectorstore()`** — prevents instantiation at import time. Lets `pytest tests/ -v` pass without `GOOGLE_API_KEY`.

## File Structure

```
backend/
├── mcp_servers/
│   ├── __init__.py
│   ├── weather_server.py
│   ├── flight_server.py
│   └── hotel_server.py
├── agent/
│   ├── state.py          ← weather_data, flight_data, hotel_data fields
│   ├── nodes.py          ← call_*_tool nodes; get_model() lazy init
│   └── graph.py          ← route_by_intent conditional routing
└── tests/
    ├── test_step4_weather.py
    ├── test_step4_flights.py
    └── test_step4_hotels.py
```

## Specs

### `weather_server.py`

Two-step Open-Meteo call (no API key):
1. `GET geocoding-api.open-meteo.com/v1/search?name={city}&count=1` → lat/lon
2. `GET api.open-meteo.com/v1/forecast?latitude=...&longitude=...&current=temperature_2m` → temp

Returns: `"Current weather in {city}: {temp}°C"` | `"Could not find location: {city}"` | `"Weather service unavailable"`

### `flight_server.py`

6 city pairs in `MOCK_FLIGHTS` (tuple keys, lowercase): tokyo/new york, tokyo/london, fukuoka/tokyo, lima/miami, riga/london, abu dhabi/london. Matching: lowercase query, both city names must appear. No match → `FALLBACK_FLIGHTS` + `"(Showing sample results — specific route not found)"`.

Return format: `"Found 3 flights:\n\n1. ANA NH009 | Tokyo → New York | Dep: 11:00 | Arr: 10:05+1 | Price: $850"`

### `hotel_server.py`

6 cities in `MOCK_HOTELS` (lowercase string keys): tokyo, kyoto, fukuoka, lima, riga, abu dhabi. Matching: city name appears in lowercase query. No match → `FALLBACK_HOTELS` + `"(Showing sample results — specific destination not found)"`.

Return format: `"Found 3 hotels in Tokyo:\n\n1. Park Hyatt Tokyo | ⭐⭐⭐⭐⭐ | $450/night\n   → iconic views of Mt. Fuji"`

### `agent/graph.py` — routing flow

```
START → classify_intent → route_by_intent
  ├── weather         → call_weather_tool → generate_response → END
  ├── hotel           → call_hotel_tool   → generate_response → END
  ├── transportation  → call_flight_tool  → generate_response → END
  └── general / other → retrieve_context  → generate_response → END
```

Transportation splits on flight keywords (`flight`, `fly`, `airline`, `airport`, `plane`, `airfare`); non-flight transportation falls through to RAG.

See `backend/agent/graph.py` for `route_by_intent()` and `backend/agent/state.py` for `AgentState`. Patching pattern is in `CLAUDE.md`.

## Tasks

### Weather

- [x] 4.1 Install `mcp[cli]`, rename `mcp-servers/` → `mcp_servers/`
- [x] 4.2 Create `weather_server.py` with `get_weather` tool
- [x] 4.3 Test weather server standalone
- [x] 4.4 Add `weather_data` to `AgentState`
- [x] 4.5 Add `call_weather_tool` node
- [x] 4.6 Add conditional routing in graph
- [x] 4.7 Update `generate_response` to include `weather_data`
- [x] 4.8 End-to-end test via `POST /chat`

### Flights

- [x] 4.9 Create `flight_server.py` with `search_flights` tool
- [x] 4.10 Test flight server standalone
- [x] 4.11 Add `flight_data` to `AgentState`
- [x] 4.12 Add `call_flight_tool` node
- [x] 4.13 Expand routing: transportation + flight keywords → `call_flight_tool`
- [x] 4.14 Update `generate_response` to include `flight_data`
- [x] 4.15 End-to-end test via `POST /chat`

### Hotels

- [x] 4.16 Create `hotel_server.py` with `search_hotels` tool
- [x] 4.17 Test hotel server standalone
- [x] 4.18 Add `hotel_data` to `AgentState`
- [x] 4.19 Add `call_hotel_tool` node
- [x] 4.20 Expand routing: hotel → `call_hotel_tool`
- [x] 4.21 Update `generate_response` to include `hotel_data`
- [x] 4.22 End-to-end test via `POST /chat`

### Wrap-up

- [x] 4.23 Update `requirements.txt`
- [x] 4.24 Refactor to lazy init (`get_model`, `get_vectorstore`) — `pytest tests/ -v` passes without API key
- [x] 4.25 47 tests pass, all mocked
