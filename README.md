# Travel Agent Platform

AI-powered travel planning agent built with production-ready infrastructure.

## Tech Stack

### Backend
- Python / FastAPI
- LangGraph (AI Agent)
- RAG (Retrieval Augmented Generation)
- MCP Server

### Frontend
- Next.js 14 / TypeScript

### Infrastructure
- Docker / Kubernetes
- AWS ECS / EKS
- GitHub Actions CI/CD
- Grafana / Prometheus / OpenTelemetry

## Architecture

(後で図を追加)

## Getting Started

### Prerequisites
- Python 3.13+
- Node.js 18+
- Docker

### Backend

\```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
\```

## Project Structure

\```
backend/
├── agent/
│   ├── state.py       # AgentState definition (TypedDict)
│   ├── nodes.py        # classify_intent, generate_response
│   └── graph.py        # LangGraph workflow assembly
├── api/
│   └── main.py         # FastAPI app (/health, /chat)
├── rag/
│   ├── data/            # Travel guide source documents (.txt)
│   ├── ingest.py        # Embeds documents and stores them in ChromaDB
│   ├── retriever.py     # Semantic search over the vector store
│   └── chroma_db/        # Persisted vector store (gitignored)
└── venv/
\```

## Features Implemented

### Agent (LangGraph)
- Intent classification node using Gemini (`gemini-3.5-flash`)
- Response generation node
- Stateful graph execution via `StateGraph`

### API (FastAPI)
- `GET /health` - health check endpoint
- `POST /chat` - accepts a user message, returns classified intent + generated response

### RAG (Retrieval Augmented Generation)
- Travel guide documents embedded using `gemini-embedding-001`
- Vector storage via ChromaDB (persisted locally)
- Semantic search retrieves relevant travel context based on user queries (not keyword-based)

## Tech Stack
- **Backend**: Python, FastAPI
- **Agent Framework**: LangGraph, LangChain
- **LLM**: Google Gemini (`gemini-3.5-flash`)
- **Embeddings**: Google Gemini (`gemini-embedding-001`)
- **Vector Store**: ChromaDB

## Setup

\```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create a .env file with:
# GOOGLE_API_KEY=your_key_here

# Ingest travel data into the vector store (run once)
python rag/ingest.py

# Start the API server
uvicorn api.main:app --reload --port 8000
\```

## Roadmap
- [x] Step 1-2: LangGraph agent (intent classification + response generation)
- [x] Step 3: RAG implementation
- [ ] Step 4: Custom MCP servers (flight/hotel/weather tools)
- [ ] Step 5: Dockerization
- [ ] Step 6: CI/CD with GitHub Actions
- [ ] Step 7: Observability (Grafana, Prometheus, OpenTelemetry)
- [ ] Step 8: AWS deployment (ECS / EKS)