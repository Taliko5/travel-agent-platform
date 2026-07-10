# Travel Agent Platform

AI-powered travel planning agent with production-ready infrastructure.

## Stack

- **Backend:** Python, FastAPI, LangGraph, ChromaDB
- **LLM:** Google Gemini (`gemini-3.5-flash`, `gemini-embedding-001`)
- **Tools:** MCP servers — weather (live Open-Meteo), flights (mock), hotels (mock)
- **Infra:** Docker, Kubernetes, GitHub Actions

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python rag/ingest.py                              # one-time: load travel guides into ChromaDB
uvicorn api.main:app --reload --port 8000
```

Set `GOOGLE_API_KEY` in `backend/.env` before running.

## Project Structure

```
backend/
├── agent/
│   ├── state.py            # AgentState TypedDict
│   ├── nodes.py            # classify_intent, call_*_tool, generate_response
│   └── graph.py            # LangGraph workflow + intent routing
├── api/
│   └── main.py             # FastAPI: GET /health, POST /chat
├── mcp_servers/
│   ├── weather_server.py   # live weather via Open-Meteo
│   ├── flight_server.py    # mock flight data
│   └── hotel_server.py     # mock hotel data
├── rag/
│   ├── data/               # travel guide .txt source files
│   ├── ingest.py           # embed + persist to ChromaDB (run once)
│   └── retriever.py        # similarity search
└── tests/
    ├── test_step4_flights.py
    ├── test_step4_hotels.py
    └── test_step4_weather.py

frontend/                         # Step 6 — see openspec/changes/add-chat-frontend
└── src/app/
    ├── page.tsx                  # renders <ChatInterface />
    ├── providers.tsx             # "use client" ChakraProvider wrapper
    └── components/
        ├── ChatInterface.tsx     # orchestrator: state + POST /chat fetch
        ├── SparkleHeader.tsx     # decorative accents (no state)
        ├── MessageList.tsx       # maps messages[] → MessageBubble
        ├── MessageBubble.tsx     # single message + conditional intent label
        └── ChatInput.tsx         # input + star send button
```

Frontend components are split one-per-concern (rather than a single `ChatInterface.tsx`) so a future change — e.g. favoriting a message, or a custom loading indicator — touches one component instead of a file that also owns fetch/state logic.

## API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | `{"status": "ok"}` |
| `/chat` | POST | `{"message": "..."}` → `{"intent": "...", "response": "..."}` |

## Documentation Map

This repo has three separate `.md` systems that serve different purposes — don't confuse them:

| Location | Purpose | Audience | Lifecycle |
|---|---|---|---|
| **`CLAUDE.md`** | Persistent project instructions for Claude Code (commands, architecture, key files, coding patterns) | AI agent (Claude Code) | Long-lived, updated as conventions change |
| **`docs/`** | Human-facing narrative docs — step-by-step build roadmap (`plan.md`) and per-step writeups (`step4.md`–`step7.md`) covering MCP servers, Docker/k8s, frontend, CI/CD | Developers/humans reading how the project was built | Historical record, mostly append-only |
| **`openspec/`** | Spec-driven change management — `changes/` holds in-flight proposals (`proposal.md`, `design.md`, `tasks.md`, `specs/*/spec.md`) before they're archived, `specs/` holds the current source-of-truth specs | AI + humans collaborating on *new* features via the OpenSpec workflow | Working directory — changes move from `changes/` to `specs/` on archive |

In short: `CLAUDE.md` tells the agent how to work in the repo *right now*, `docs/` explains what was built and why (past tense), and `openspec/` is the active workflow for proposing and tracking *upcoming* changes.

## Roadmap

- [x] Steps 1–2: LangGraph agent (intent classification + response generation)
- [x] Step 3: RAG with ChromaDB
- [x] Step 4: MCP servers (weather / flights / hotels)
- [x] Step 5: Docker + docker-compose + k8s manifests
- [ ] Step 6: Frontend (Next.js 14 / TypeScript)
- [ ] Step 7: GitHub Actions CI/CD
- [ ] Step 8: Observability (Grafana, Prometheus, OpenTelemetry)
- [ ] Step 9: AWS deployment (ECS / EKS)
