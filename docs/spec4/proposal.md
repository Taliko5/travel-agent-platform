# Step 4 Proposal: MCP Server (Weather Tool)

## What We Are Building

A standalone MCP (Model Context Protocol) server that provides real-time weather data for any city in the world. The server runs as a **separate process** from the FastAPI backend and exposes one tool: `get_weather(city)`.

The agent calls this tool when a user's question is classified as `weather` intent.

## Why MCP Instead of a Simple Function

The previous steps added RAG (retrieval from local data). MCP solves a different problem: **real-time external data** that cannot be stored in a vector database because it changes every hour.

| Approach | What it solves | Limitation |
|---|---|---|
| RAG (ChromaDB) | Static destination knowledge | Cannot answer "what is the weather right now?" |
| LLM general knowledge | Common facts | Knowledge cutoff; no live data |
| MCP tool (this step) | Live external API data | Requires network; API availability |

Additionally, MCP is the right architectural choice (not just a LangChain `@tool`) because:

- The tool runs as a **separate process** — it can be reused by Claude Desktop, Claude Code, and future agents without copying code
- Follows the official [Model Context Protocol](https://modelcontextprotocol.io) standard, which is rapidly becoming the industry convention for AI tool integration
- Decouples tool maintenance from agent maintenance — a different team could own the weather server

## Technology Choices

### MCP SDK: FastMCP (via `mcp[cli]`)

FastMCP is the official high-level wrapper in the MCP Python SDK. It provides a Flask-style decorator API (`@mcp.tool()`) that generates the full MCP protocol boilerplate automatically.

Alternative considered: raw `mcp.server.Server` — rejected because it requires manual protocol handling with no benefit at this scale.

### Weather API: Open-Meteo

- **No API key required** — zero setup friction
- **Global coverage** — works for Tokyo, Lima, Riga, and all cities in our RAG dataset
- **Two-step design:** geocoding API converts city name to coordinates, then forecast API returns weather data
- Free tier: 10,000 requests/day — sufficient for development and demo

Alternative considered: OpenWeatherMap — requires API key registration; adds setup overhead.

### HTTP Client: httpx (AsyncClient)

The MCP tool is `async def` so it needs an async HTTP client. `httpx` is already in the project's requirements and is the standard async HTTP library for Python.

## What This Looks Like to the User

**Before Step 4:**
> "What's the weather like in Lima?"
> → LLM guesses based on training data: "Lima has a desert climate with mild temperatures..."

**After Step 4:**
> "What's the weather like in Lima?"
> → Agent calls MCP weather tool → gets live temperature
> → "The current temperature in Lima is 17°C."

## Scope of This Step

**In scope:**
- `weather_server.py` — one tool: `get_weather(city)`, live data via Open-Meteo
- `flight_server.py` — one tool: `search_flights(query)`, mocked data
- `hotel_server.py` — one tool: `search_hotels(query)`, mocked data
- Integration of all three into the LangGraph agent via conditional routing
- Standalone test of each MCP server

**Out of scope:**
- Real flight API integration (Amadeus, Skyscanner) — requires paid credentials
- Real hotel API integration (Booking.com) — requires paid credentials
- User profile MCP server
- Authentication/authorization on the MCP servers

---

## Why Mock Data for Flights and Hotels

Real flight and hotel APIs (Amadeus, Skyscanner, Booking.com) require paid subscriptions or commercial agreements. Mock data is the right choice for now for several reasons:

**For demonstration:**
Mock data is predictable and lets you validate the agent's routing, prompting, and response generation for flight and hotel queries without network dependencies or API rate limits.

**For future extensibility:**
The tool interface (`search_flights(query)`, `search_hotels(query)`) is intentionally designed to be a drop-in replacement. Swapping mock data for a real API call requires changing only the internals of the tool function — the MCP server, agent node, state field, and graph routing remain untouched.