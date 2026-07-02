# Step 4 Tasks

## Task List

### Weather (live API)

| # | Task | File(s) | Depends On |
|---|---|---|---|
| 4.1 | Install `mcp[cli]` and rename directory to `mcp_servers/` | `requirements.txt` | — |
| 4.2 | Create `weather_server.py` with `get_weather` tool | `mcp_servers/weather_server.py` | 4.1 |
| 4.3 | Test weather server standalone | — | 4.2 |
| 4.4 | Add `weather_data` to `AgentState` | `agent/state.py` | 4.2 |
| 4.5 | Add `call_weather_tool` node | `agent/nodes.py` | 4.2 |
| 4.6 | Add conditional routing + wire weather into graph | `agent/graph.py` | 4.3, 4.5 |
| 4.7 | Update `generate_response` prompt to include `weather_data` | `agent/nodes.py` | 4.4 |
| 4.8 | End-to-end test: weather query via `POST /chat` | — | 4.6, 4.7 |

### Flights (mock data)

| # | Task | File(s) | Depends On |
|---|---|---|---|
| 4.9 | Create `flight_server.py` with `search_flights` tool | `mcp_servers/flight_server.py` | 4.1 |
| 4.10 | Test flight server standalone | — | 4.9 |
| 4.11 | Add `flight_data` to `AgentState` | `agent/state.py` | 4.9 |
| 4.12 | Add `call_flight_tool` node | `agent/nodes.py` | 4.9 |
| 4.13 | Expand routing: `transportation` → `call_flight_tool` | `agent/graph.py` | 4.10, 4.12 |
| 4.14 | Update `generate_response` prompt to include `flight_data` | `agent/nodes.py` | 4.11 |
| 4.15 | End-to-end test: transportation query via `POST /chat` | — | 4.13, 4.14 |

### Hotels (mock data)

| # | Task | File(s) | Depends On |
|---|---|---|---|
| 4.16 | Create `hotel_server.py` with `search_hotels` tool | `mcp_servers/hotel_server.py` | 4.1 |
| 4.17 | Test hotel server standalone | — | 4.16 |
| 4.18 | Add `hotel_data` to `AgentState` | `agent/state.py` | 4.16 |
| 4.19 | Add `call_hotel_tool` node | `agent/nodes.py` | 4.16 |
| 4.20 | Expand routing: `hotel` → `call_hotel_tool` | `agent/graph.py` | 4.17, 4.19 |
| 4.21 | Update `generate_response` prompt to include `hotel_data` | `agent/nodes.py` | 4.18 |
| 4.22 | End-to-end test: hotel query via `POST /chat` | — | 4.20, 4.21 |

### Wrap-up

| # | Task | File(s) | Depends On |
|---|---|---|---|
| 4.23 | Update `requirements.txt` | `requirements.txt` | 4.8, 4.15, 4.22 |
| 4.24 | Full regression: test all 4 intents | — | 4.23 |
| 4.25 | Update `docs/steps.md` Step 4 to ✅ | `docs/steps.md` | 4.24 |

---

## Task Detail

### 4.1 — Install `mcp[cli]`

```bash
cd backend
source venv/bin/activate
pip install "mcp[cli]>=1.0,<2"
```

Pin to `<2` because MCP v2 is in beta (stable target: 2026-07-27). Using v1 keeps the project on the stable release.

---

### 4.2 — Create `weather_server.py`

Use Claude Code to generate this file. Prompt to use:

```
Create backend/mcp-servers/weather_server.py using FastMCP.

Requirements:
- Import FastMCP from mcp.server.fastmcp
- Create one async tool: get_weather(city: str) -> str
- Step 1: Call Open-Meteo geocoding API to convert city name to lat/lon
  URL: https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1
- Step 2: Call Open-Meteo forecast API with lat/lon
  URL: https://api.open-meteo.com/v1/forecast?latitude=...&longitude=...&current=temperature_2m,weather_code
- Use httpx.AsyncClient for both calls
- Return a plain string: "Current weather in {city}: {temp}°C"
- If city not found, return: "Could not find location: {city}"
- End with: if __name__ == "__main__": mcp.run()
```

After generation, read the file and make sure you understand every line before moving on.

---

### 4.3 — Test MCP Server Standalone

Run the server directly and confirm it starts without errors:

```bash
cd backend
python mcp-servers/weather_server.py
# Should print: Starting MCP server "travel-weather"...
# Press Ctrl+C to stop
```

Then test the tool by calling the Open-Meteo API manually in a Python script to confirm the response format matches expectations:

```bash
python -c "
import httpx, asyncio
async def test():
    async with httpx.AsyncClient() as c:
        r = await c.get('https://geocoding-api.open-meteo.com/v1/search', params={'name': 'Tokyo', 'count': 1})
        print(r.json())
asyncio.run(test())
"
```

---

### 4.4 — Add Conditional Branch in Graph

The current graph is linear: classify → retrieve → generate.

After this task, the graph branches on `weather` intent:

```
classify_intent
      |
      ├── intent == "weather" → call_weather_tool → generate_response
      └── intent != "weather" → retrieve_context  → generate_response
```

This uses LangGraph's `add_conditional_edges`:

```python
def route_by_intent(state: AgentState) -> str:
    if state["intent"] == "weather":
        return "call_weather_tool"
    return "retrieve_context"

graph.add_conditional_edges("classify_intent", route_by_intent)
```

File to edit: `agent/graph.py`

---

### 4.5 — Add `call_weather_tool` Node

Add a new node to `nodes.py` that calls the MCP weather server.

**Implementation choice:** For the initial integration, call the weather server's Python function directly (no separate process) to keep the wiring simple. The MCP server can still be run independently for Claude Desktop / Claude Code use.

```python
async def call_weather_tool(state: AgentState) -> AgentState:
    # import here to avoid loading httpx at module startup
    from mcp-servers.weather_server import get_weather  # adjust import path
    weather = await get_weather(city=state["user_input"])
    return {
        **state,
        "weather_data": weather,
    }
```

Note: MCP tool functions are `async def`, so `call_weather_tool` must also be `async def`. LangGraph supports async nodes natively.

File to edit: `agent/nodes.py`

---

### 4.6 — Add `weather_data` to `AgentState`

```python
class AgentState(TypedDict):
    user_input: str
    intent: Optional[str]
    context: Optional[str]
    weather_data: Optional[str]   # ← add this
    response: Optional[str]
```

File to edit: `agent/state.py`

---

### 4.7 — Update `generate_response` Prompt

Add weather data to the prompt alongside the existing context section:

```python
weather_section = ""
if state.get("weather_data"):
    weather_section = f"\nLive weather data:\n{state['weather_data']}\n"
```

File to edit: `agent/nodes.py` (`generate_response` function)

---

### 4.8 — End-to-End Test

Start the API server and test via `/docs`:

```bash
uvicorn api.main:app --reload --port 8000
```

Test payload:
```json
{ "message": "What is the weather like in Fukuoka right now?" }
```

Expected: `intent` = `"weather"`, `response` mentions actual temperature in °C.

Also test a non-weather query to confirm the conditional branch still works:
```json
{ "message": "Best hotels in Riga?" }
```

Expected: `intent` = `"hotel"`, response uses RAG context (no weather data).

---

### 4.9 — Update `requirements.txt`

```bash
pip freeze > requirements.txt
```

Confirm `mcp` appears in the output.

---

---

### 4.9 — Create `flight_server.py`

Use Claude Code. Prompt to use:

```
Create backend/mcp_servers/flight_server.py using FastMCP.

Requirements:
- Import FastMCP from mcp.server.fastmcp
- Create one tool: search_flights(query: str) -> str
- Use hardcoded mock data: a dict of city-pair tuples mapped to a list of flights
  Each flight has: airline, flight number, departure time, arrival time, price (USD)
- Cover at least these city pairs: Tokyo→New York, Tokyo→London, Fukuoka→Tokyo,
  Lima→Miami, Riga→London, Abu Dhabi→London
- To pick a result: scan query.lower() for city names and return the best-matching mock flights
- If no match found: return a generic set of 3 flights as a fallback
- Format return as a readable multi-line string listing each option
- End with: if __name__ == "__main__": mcp.run()
```

After generation, read the file and check: does the keyword matching logic make sense? Can you explain it line by line?

---

### 4.10 — Test Flight Server Standalone

```bash
python mcp_servers/flight_server.py
# Ctrl+C to stop
```

Also test the function directly:

```bash
python -c "
import asyncio
from mcp_servers.flight_server import search_flights
async def test():
    result = await search_flights('flights from Tokyo to New York')
    print(result)
asyncio.run(test())
"
```

Expected output: a list of 3 mock flights with airline, times, and price.

---

### 4.11 — Add `flight_data` to `AgentState`

```python
class AgentState(TypedDict):
    user_input: str
    intent: Optional[str]
    context: Optional[str]
    weather_data: Optional[str]
    flight_data: Optional[str]    # ← add this
    response: Optional[str]
```

---

### 4.12 — Add `call_flight_tool` Node

```python
async def call_flight_tool(state: AgentState) -> AgentState:
    """Call the mock flight search tool."""
    from mcp_servers.flight_server import search_flights
    flights = await search_flights(query=state["user_input"])
    return {
        **state,
        "flight_data": flights,
    }
```

---

### 4.13 — Expand Routing for `transportation`

Update `route_by_intent` in `graph.py`:

```python
def route_by_intent(state: AgentState) -> str:
    intent = state["intent"]
    if intent == "weather":
        return "call_weather_tool"
    if intent == "transportation":
        return "call_flight_tool"
    return "retrieve_context"
```

Add the new node and edge to the graph:

```python
graph.add_node("call_flight_tool", call_flight_tool)
graph.add_edge("call_flight_tool", "generate_response")
```

---

### 4.14 — Update `generate_response` for `flight_data`

```python
flight_section = ""
if state.get("flight_data"):
    flight_section = f"\nFlight search results:\n{state['flight_data']}\n"
```

Add `{flight_section}` to the prompt alongside the existing sections.

---

### 4.15 — End-to-End Test: Transportation

```json
{ "message": "Show me flights from Tokyo to New York" }
```

Expected: `intent` = `"transportation"`, response includes mock airline names and prices.

---

### 4.16 — Create `hotel_server.py`

Use Claude Code. Prompt to use:

```
Create backend/mcp_servers/hotel_server.py using FastMCP.

Requirements:
- Import FastMCP from mcp.server.fastmcp
- Create one tool: search_hotels(query: str) -> str
- Use hardcoded mock data: a dict of city name (lowercase) mapped to a list of hotels
  Each hotel has: name, price per night (USD), star rating, one standout feature
- Cover at least these cities: tokyo, kyoto, fukuoka, lima, riga, abu dhabi
- To pick a result: scan query.lower() for city names and return matching mock hotels
- If no city match: return a generic fallback list of 3 hotels
- Format return as a readable multi-line string listing each option
- End with: if __name__ == "__main__": mcp.run()
```

---

### 4.17 — Test Hotel Server Standalone

```bash
python -c "
import asyncio
from mcp_servers.hotel_server import search_hotels
async def test():
    result = await search_hotels('hotels in Riga')
    print(result)
asyncio.run(test())
"
```

Expected output: a list of 3 mock hotels for Riga with names, prices, ratings.

---

### 4.18 — Add `hotel_data` to `AgentState`

```python
class AgentState(TypedDict):
    user_input: str
    intent: Optional[str]
    context: Optional[str]
    weather_data: Optional[str]
    flight_data: Optional[str]
    hotel_data: Optional[str]     # ← add this
    response: Optional[str]
```

---

### 4.19 — Add `call_hotel_tool` Node

```python
async def call_hotel_tool(state: AgentState) -> AgentState:
    """Call the mock hotel search tool."""
    from mcp_servers.hotel_server import search_hotels
    hotels = await search_hotels(query=state["user_input"])
    return {
        **state,
        "hotel_data": hotels,
    }
```

---

### 4.20 — Expand Routing for `hotel`

Update `route_by_intent` in `graph.py`:

```python
def route_by_intent(state: AgentState) -> str:
    intent = state["intent"]
    if intent == "weather":
        return "call_weather_tool"
    if intent == "transportation":
        return "call_flight_tool"
    if intent == "hotel":
        return "call_hotel_tool"
    return "retrieve_context"
```

Add the new node and edge:

```python
graph.add_node("call_hotel_tool", call_hotel_tool)
graph.add_edge("call_hotel_tool", "generate_response")
```

---

### 4.21 — Update `generate_response` for `hotel_data`

```python
hotel_section = ""
if state.get("hotel_data"):
    hotel_section = f"\nHotel search results:\n{state['hotel_data']}\n"
```

Add `{hotel_section}` to the prompt.

---

### 4.22 — End-to-End Test: Hotel

```json
{ "message": "Find me hotels in Lima" }
```

Expected: `intent` = `"hotel"`, response includes mock hotel names and prices.

---

### 4.23 — Update `requirements.txt`

```bash
pip freeze > requirements.txt
```

---

### 4.24 — Full Regression Test

Test all 4 intents in sequence to confirm nothing is broken:

| Query | Expected intent | Expected data source |
|---|---|---|
| `"What is the weather in Fukuoka?"` | `weather` | Open-Meteo live API |
| `"Flights from Riga to London"` | `transportation` | Mock flight data |
| `"Hotels in Abu Dhabi"` | `hotel` | Mock hotel data |
| `"Best food to try in Lima"` | `general` | ChromaDB RAG |

---

## Definition of Done

- [ ] `mcp_servers/weather_server.py` — starts, returns live temperature
- [ ] `mcp_servers/flight_server.py` — starts, returns mock flights
- [ ] `mcp_servers/hotel_server.py` — starts, returns mock hotels
- [ ] All 4 intents route correctly via `POST /chat`
- [ ] `AgentState` has `weather_data`, `flight_data`, `hotel_data` fields
- [ ] `generate_response` includes all three data sections in prompt
- [ ] `requirements.txt` updated with `mcp`
- [ ] `docs/steps.md` Step 4 row updated to ✅
