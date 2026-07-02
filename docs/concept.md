# Concept: Travel Agent Platform

## What This Is

An AI-powered travel planning assistant built as a **production-ready platform**

A user asks a travel question in natural language. The system classifies their intent, retrieves relevant destination knowledge, and generates a grounded, helpful response — all via a REST API.

## Why It Exists

**Purpose:** The goal is not just a working chatbot, but a system that shows end-to-end production thinking: agent orchestration, data retrieval, custom tooling, containerization, CI/CD, observability, and cloud deployment.


## Core Value Proposition

| For the user | For the system |
|---|---|
| Fast, accurate travel answers with destination context | LangGraph, RAG, MCP, Docker, K8s, CI/CD, observability — all integrated |
| Intent-aware responses (flights vs hotels vs weather) | Each layer is independently testable and replaceable |

## Key Design Principles

**1. Understand before generate**
The agent classifies user intent before generating a response. This prevents generic answers and allows intent-specific tooling in future steps.

**2. Ground responses in real data (RAG)**
LLM general knowledge alone is unreliable for travel specifics. A vector store of curated destination guides provides factual grounding, reducing hallucination risk.

**3. Extend via MCP, not hardcoding**
External data sources (weather, flights, hotels) are accessed through MCP servers — separate processes with a standard protocol. This decouples tools from the agent and allows reuse across multiple AI applications.

**4. Defense in depth for LLM outputs**
LLM responses are instructed AND post-processed (`.strip().lower()`, allowlist filtering) because LLMs are non-deterministic. Prompts set intent; code enforces it.

**5. Production shape from day one**
The project follows production conventions (venv, requirements.txt, .env, Pydantic models, FastAPI, Docker, CI) even while incomplete. Each step adds a layer that a real system would need.

## What It Is Not

- Not a production travel booking system
- Not a multi-tenant SaaS product
- Not a fully autonomous agent (no memory, no multi-turn state persistence yet)
