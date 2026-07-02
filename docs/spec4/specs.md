# Step 4 Technical Specifications

## File Structure

```
backend/
├── mcp-servers/
│   └── weather_server.py       ← new
├── agent/
│   ├── state.py                ← add weather_data field
│   ├── nodes.py                ← add call_weather_tool node; update generate_response
│   └── graph.py                ← add conditional branch on weather intent
└── requirements.txt            ← add mcp>=1.0,<2
```

---

## `weather_server.py` Specification

### Location
`backend/mcp-servers/weather_server.py`

### Dependencies
- `mcp[cli]>=1.0,<2` — FastMCP server
- `httpx` — async HTTP (already in requirements)

### Server identity
```python
mcp = FastMCP("travel-weather")
```

### Tool: `get_weather`

**Signature:**
```python
@mcp.tool()
async def get_weather(city: str) -> str:
```

**Docstring (used by LLM to understand the tool):**
```
Get the current weather for a given city.

Args:
    city: Name of the city in English, e.g. "Tokyo" or "Lima"
```

**Step 1 — Geocoding request:**
```
GET https://geocoding-api.open-meteo.com/v1/search
    ?name={city}
    &count=1
```

Expected response shape:
```json
{
  "results": [
    {
      "name": "Tokyo",
      "latitude": 35.6895,
      "longitude": 139.6917,
      "country": "Japan"
    }
  ]
}
```

If `results` key is missing or empty → return `"Could not find location: {city}"`

**Step 2 — Forecast request:**
```
GET https://api.open-meteo.com/v1/forecast
    ?latitude={lat}
    &longitude={lon}
    &current=temperature_2m,weather_code
```

Expected response shape:
```json
{
  "current": {
    "temperature_2m": 22.4,
    "weather_code": 1
  }
}
```

**Return value:**
```
"Current weather in {city}: {temperature_2m}°C"
```

Example: `"Current weather in Tokyo: 28.3°C"`

**Error cases:**

| Condition | Return value |
|---|---|
| `results` missing or empty | `"Could not find location: {city}"` |
| HTTP error on geocoding | `"Weather service unavailable"` |
| HTTP error on forecast | `"Weather service unavailable"` |

**Entry point:**
```python
if __name__ == "__main__":
    mcp.run()
```

---

## `agent/state.py` Specification

Add one field:

```python
class AgentState(TypedDict):
    user_input: str
    intent: Optional[str]
    context: Optional[str]
    weather_data: Optional[str]   # ← new: populated only for weather intent
    response: Optional[str]
```

`weather_data` is `None` for all non-weather intents.

---

## `agent/nodes.py` Specification

### New node: `call_weather_tool`

```python
async def call_weather_tool(state: AgentState) -> AgentState:
    """Call the MCP weather server tool to get live weather data."""
    from mcp_servers.weather_server import get_weather
    weather = await get_weather(city=state["user_input"])
    return {
        **state,
        "weather_data": weather,
    }
```

Note on import path: `mcp-servers/` contains a hyphen which Python cannot use in a module name directly. Options:
- Rename directory to `mcp_servers/` (recommended — use underscores, not hyphens, for Python packages)
- Or use `importlib` to load by path

**Recommendation: rename `mcp-servers/` to `mcp_servers/`** before implementing.

### Updated: `generate_response`

Add a `weather_section` block alongside the existing `context_section`:

```python
def generate_response(state: AgentState) -> AgentState:
    """Generate a response based on the classified intent and user's question."""

    context_section = ""
    if state.get("context"):
        context_section = f"\nRelevant travel information:\n{state['context']}\n"

    weather_section = ""
    if state.get("weather_data"):
        weather_section = f"\nLive weather data:\n{state['weather_data']}\n"

    prompt = f"""
    intent: {state["intent"]}
    {context_section}
    {weather_section}
    question: {state["user_input"]}
    Respond with about 200 words. Include URLs if relevant.
    """

    response = model.invoke(prompt)

    return {
        **state,
        "response": response.text,
    }
```

---

## `agent/graph.py` Specification

### Routing function

```python
def route_by_intent(state: AgentState) -> str:
    """Route to weather tool or RAG retrieval based on intent."""
    if state["intent"] == "weather":
        return "call_weather_tool"
    return "retrieve_context"
```

### Updated graph structure

```python
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("call_weather_tool", call_weather_tool)
    graph.add_node("generate_response", generate_response)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges("classify_intent", route_by_intent)
    graph.add_edge("retrieve_context", "generate_response")
    graph.add_edge("call_weather_tool", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()
```

Visual flow:
```
START
  ↓
classify_intent
  ↓ (route_by_intent)
  ├── "weather"      → call_weather_tool → generate_response → END
  └── everything else → retrieve_context  → generate_response → END
```

---

## API Contract: `POST /chat` After Step 4

### Weather query

**Request:**
```json
{ "message": "What is the weather like in Riga right now?" }
```

**Response:**
```json
{
  "intent": "weather",
  "response": "The current weather in Riga is 18°C. Riga, Latvia's capital, typically..."
}
```

### Non-weather query (unchanged behavior)

**Request:**
```json
{ "message": "What are the best hotels in Fukuoka?" }
```

**Response:**
```json
{
  "intent": "hotel",
  "response": "Fukuoka offers excellent accommodation options... [uses RAG context]"
}
```

---

## External API Reference

### Open-Meteo Geocoding
- Docs: https://open-meteo.com/en/docs/geocoding-api
- No API key required
- Rate limit: 10,000 requests/day (free)

### Open-Meteo Forecast
- Docs: https://open-meteo.com/en/docs
- No API key required
- `weather_code` meanings: https://open-meteo.com/en/docs#weathervariables

### WMO Weather Codes (optional enhancement)
The `weather_code` integer can be translated to a human-readable description (e.g., `0` = Clear sky, `61` = Rain). This is optional for Step 4 — the temperature alone is sufficient for a working demo.

---

## Rename Reminder

Before writing any code, rename the directory:

```bash
cd backend
mv mcp-servers mcp_servers
touch mcp_servers/__init__.py
```

This makes it importable as a Python module (`from mcp_servers.weather_server import get_weather`).

---

## `flight_server.py` Specification

### Location
`backend/mcp_servers/flight_server.py`

### Server identity
```python
mcp = FastMCP("travel-flights")
```

### Mock data structure

```python
MOCK_FLIGHTS = {
    ("tokyo", "new york"): [
        {"airline": "ANA",    "flight": "NH009", "dep": "11:00", "arr": "10:05+1", "price": "$850"},
        {"airline": "JAL",    "flight": "JL004", "dep": "18:00", "arr": "17:00+1", "price": "$920"},
        {"airline": "United", "flight": "UA837", "dep": "16:30", "arr": "15:25+1", "price": "$780"},
    ],
    ("tokyo", "london"): [
        {"airline": "ANA",    "flight": "NH211", "dep": "11:30", "arr": "15:45",   "price": "$750"},
        {"airline": "BA",     "flight": "BA006", "dep": "20:00", "arr": "23:55",   "price": "$820"},
        {"airline": "Finnair","flight": "AY071", "dep": "09:00", "arr": "14:20",   "price": "$690"},
    ],
    ("fukuoka", "tokyo"): [
        {"airline": "ANA",    "flight": "NH254", "dep": "07:00", "arr": "08:20",   "price": "$90"},
        {"airline": "JAL",    "flight": "JL316", "dep": "09:30", "arr": "10:55",   "price": "$105"},
        {"airline": "Peach",  "flight": "MM102", "dep": "06:15", "arr": "07:40",   "price": "$55"},
    ],
    ("lima", "miami"): [
        {"airline": "LATAM",  "flight": "LA802", "dep": "23:45", "arr": "07:30+1", "price": "$310"},
        {"airline": "American","flight":"AA900", "dep": "22:00", "arr": "05:40+1", "price": "$380"},
        {"airline": "Spirit", "flight": "NK722", "dep": "01:00", "arr": "08:50",   "price": "$210"},
    ],
    ("riga", "london"): [
        {"airline": "airBaltic","flight":"BT601","dep": "06:55", "arr": "08:10",   "price": "$130"},
        {"airline": "Ryanair", "flight": "FR8421","dep":"14:20", "arr": "15:35",   "price": "$85"},
        {"airline": "Wizz Air","flight": "W61234","dep":"19:00", "arr": "20:15",   "price": "$95"},
    ],
    ("abu dhabi", "london"): [
        {"airline": "Etihad", "flight": "EY19",  "dep": "02:25", "arr": "07:10",  "price": "$550"},
        {"airline": "BA",     "flight": "BA054",  "dep": "08:30", "arr": "13:15",  "price": "$620"},
        {"airline": "Virgin", "flight": "VS401",  "dep": "22:10", "arr": "03:00+1","price": "$490"},
    ],
}

FALLBACK_FLIGHTS = [
    {"airline": "Generic Air", "flight": "GA100", "dep": "08:00", "arr": "varies", "price": "$400"},
    {"airline": "Budget Fly",  "flight": "BF200", "dep": "14:00", "arr": "varies", "price": "$280"},
    {"airline": "Star Travel", "flight": "ST300", "dep": "20:00", "arr": "varies", "price": "$350"},
]
```

### Tool: `search_flights`

**Signature:**
```python
@mcp.tool()
async def search_flights(query: str) -> str:
```

**Docstring:**
```
Search for available flights based on a natural language query.

Args:
    query: A travel query describing origin and destination,
           e.g. "flights from Tokyo to New York" or "Tokyo to London"
```

**Matching logic:**
1. Convert `query` to lowercase
2. Scan `MOCK_FLIGHTS` keys — check if both cities in the tuple appear in `query`
3. If a match is found, format and return those flights
4. If no match, return `FALLBACK_FLIGHTS` with a note: `"(Showing sample results — specific route not found)"`

**Return format:**
```
Found 3 flights:

1. ANA NH009 | Tokyo → New York | Dep: 11:00 | Arr: 10:05+1 | Price: $850
2. JAL JL004 | Tokyo → New York | Dep: 18:00 | Arr: 17:00+1 | Price: $920
3. United UA837 | Tokyo → New York | Dep: 16:30 | Arr: 15:25+1 | Price: $780
```

**Error cases:**

| Condition | Return value |
|---|---|
| No matching city pair | Return fallback flights with a note |
| Empty query | Return fallback flights |

---

## `hotel_server.py` Specification

### Location
`backend/mcp_servers/hotel_server.py`

### Server identity
```python
mcp = FastMCP("travel-hotels")
```

### Mock data structure

```python
MOCK_HOTELS = {
    "tokyo": [
        {"name": "Park Hyatt Tokyo",       "price": "$450/night", "stars": 5, "highlight": "iconic views of Mt. Fuji from upper floors"},
        {"name": "Shinjuku Granbell Hotel","price": "$180/night", "stars": 4, "highlight": "stylish boutique hotel in Shinjuku entertainment district"},
        {"name": "APA Hotel Shinjuku",     "price": "$90/night",  "stars": 3, "highlight": "compact and efficient, 2 min walk to Kabukicho"},
    ],
    "kyoto": [
        {"name": "The Westin Miyako Kyoto","price": "$320/night", "stars": 5, "highlight": "Japanese garden with traditional tea house"},
        {"name": "Hotel Granvia Kyoto",    "price": "$200/night", "stars": 4, "highlight": "directly above Kyoto Station, excellent transport access"},
        {"name": "Piece Hostel Sanjo",     "price": "$45/night",  "stars": 2, "highlight": "highly rated budget option, central location"},
    ],
    "fukuoka": [
        {"name": "The Royal Park Hotel",   "price": "$160/night", "stars": 4, "highlight": "5 min walk to Hakata Station, city views"},
        {"name": "Canal City Fukuoka Washington Hotel","price":"$120/night","stars":3,"highlight":"inside Canal City mall, walking distance to Nakasu yatai"},
        {"name": "Dormy Inn Hakata",       "price": "$85/night",  "stars": 3, "highlight": "natural hot spring bath, famous midnight ramen service"},
    ],
    "lima": [
        {"name": "Belmond Miraflores Park","price": "$380/night", "stars": 5, "highlight": "clifftop location overlooking the Pacific Ocean"},
        {"name": "Casa Andina Premium",    "price": "$150/night", "stars": 4, "highlight": "central Miraflores, close to Larcomar shopping center"},
        {"name": "Hotel Antigua Miraflores","price":"$80/night",  "stars": 3, "highlight": "colonial building, quiet residential street, great breakfast"},
    ],
    "riga": [
        {"name": "Grand Hotel Kempinski",  "price": "$280/night", "stars": 5, "highlight": "overlooking Freedom Monument, spa and fine dining"},
        {"name": "Radisson Blu Latvija",   "price": "$160/night", "stars": 4, "highlight": "tallest hotel in Baltics, panoramic city views"},
        {"name": "Neiburgs Hotel",         "price": "$110/night", "stars": 4, "highlight": "art nouveau building in Old Town, boutique atmosphere"},
    ],
    "abu dhabi": [
        {"name": "Emirates Palace Mandarin Oriental","price":"$900/night","stars":5,"highlight":"gold-leaf interiors, private beach, 1km of Gulf coastline"},
        {"name": "Yas Island Rotana",      "price": "$200/night", "stars": 4, "highlight": "adjacent to Ferrari World and Yas Waterworld"},
        {"name": "Aloft Abu Dhabi",        "price": "$120/night", "stars": 3, "highlight": "modern design, rooftop pool, near National Exhibition Centre"},
    ],
}

FALLBACK_HOTELS = [
    {"name": "City Center Hotel",  "price": "$150/night", "stars": 4, "highlight": "central location, good transport links"},
    {"name": "Budget Inn Express", "price": "$70/night",  "stars": 3, "highlight": "clean and practical, great value"},
    {"name": "Boutique Stay",      "price": "$200/night", "stars": 4, "highlight": "stylish rooms, highly rated on booking platforms"},
]
```

### Tool: `search_hotels`

**Signature:**
```python
@mcp.tool()
async def search_hotels(query: str) -> str:
```

**Docstring:**
```
Search for available hotels based on a natural language query.

Args:
    query: A travel query mentioning a destination city,
           e.g. "hotels in Tokyo" or "where to stay in Riga"
```

**Matching logic:**
1. Convert `query` to lowercase
2. Scan `MOCK_HOTELS` keys — check if the city name appears in `query`
3. If a match is found, format and return those hotels
4. If no match, return `FALLBACK_HOTELS` with a note

**Return format:**
```
Found 3 hotels in Tokyo:

1. Park Hyatt Tokyo | ⭐⭐⭐⭐⭐ | $450/night
   → iconic views of Mt. Fuji from upper floors

2. Shinjuku Granbell Hotel | ⭐⭐⭐⭐ | $180/night
   → stylish boutique hotel in Shinjuku entertainment district

3. APA Hotel Shinjuku | ⭐⭐⭐ | $90/night
   → compact and efficient, 2 min walk to Kabukicho
```

---

## Updated `agent/state.py` (Final)

After all three servers are integrated:

```python
class AgentState(TypedDict):
    user_input: str
    intent: Optional[str]
    context: Optional[str]       # RAG: populated for general/hotel/transportation
    weather_data: Optional[str]  # live: populated for weather intent
    flight_data: Optional[str]   # mock: populated for transportation intent
    hotel_data: Optional[str]    # mock: populated for hotel intent
    response: Optional[str]
```

---

## Updated `agent/graph.py` (Final)

```python
def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate tool node based on classified intent."""
    intent = state["intent"]
    if intent == "weather":
        return "call_weather_tool"
    if intent == "transportation":
        return "call_flight_tool"
    if intent == "hotel":
        return "call_hotel_tool"
    return "retrieve_context"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent",   classify_intent)
    graph.add_node("retrieve_context",  retrieve_context_node)
    graph.add_node("call_weather_tool", call_weather_tool)
    graph.add_node("call_flight_tool",  call_flight_tool)
    graph.add_node("call_hotel_tool",   call_hotel_tool)
    graph.add_node("generate_response", generate_response)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges("classify_intent", route_by_intent)
    graph.add_edge("retrieve_context",  "generate_response")
    graph.add_edge("call_weather_tool", "generate_response")
    graph.add_edge("call_flight_tool",  "generate_response")
    graph.add_edge("call_hotel_tool",   "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()
```

Visual flow:
```
START
  ↓
classify_intent
  ↓ (route_by_intent)
  ├── "weather"        → call_weather_tool → generate_response → END
  ├── "transportation" → call_flight_tool  → generate_response → END
  ├── "hotel"          → call_hotel_tool   → generate_response → END
  └── "general"        → retrieve_context  → generate_response → END
```

---

## Updated `generate_response` Prompt (Final)

```python
def generate_response(state: AgentState) -> AgentState:
    context_section = ""
    if state.get("context"):
        context_section = f"\nRelevant travel information:\n{state['context']}\n"

    weather_section = ""
    if state.get("weather_data"):
        weather_section = f"\nLive weather data:\n{state['weather_data']}\n"

    flight_section = ""
    if state.get("flight_data"):
        flight_section = f"\nFlight search results:\n{state['flight_data']}\n"

    hotel_section = ""
    if state.get("hotel_data"):
        hotel_section = f"\nHotel search results:\n{state['hotel_data']}\n"

    prompt = f"""
    intent: {state["intent"]}
    {context_section}
    {weather_section}
    {flight_section}
    {hotel_section}
    question: {state["user_input"]}
    Respond with about 200 words. Include URLs if relevant.
    """

    response = model.invoke(prompt)
    return {**state, "response": response.text}
```

---

## Full API Contract After Step 4

| Query | intent | Data source | Key fields in response |
|---|---|---|---|
| `"Weather in Riga?"` | `weather` | Open-Meteo live | temperature in °C |
| `"Flights Tokyo to NY"` | `transportation` | Mock | airline, price, times |
| `"Hotels in Lima"` | `hotel` | Mock | hotel names, prices, stars |
| `"Food in Fukuoka"` | `general` | ChromaDB RAG | destination knowledge |
