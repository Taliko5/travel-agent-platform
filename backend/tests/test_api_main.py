"""
Unit tests for api/main.py — /health, /, /chat, and CORS.

`api.main.graph` is mocked directly (an AsyncMock) rather than the underlying
agent nodes — agent routing logic is already covered by test_graph_routing.py
and the existing Step 4 test files. build_graph() only wires StateGraph
nodes/edges at import time — it never invokes a node — so importing api.main
requires no GOOGLE_API_KEY.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api.main import app

    return TestClient(app)


class TestHealthAndRoot:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.1.0"}

    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "travel agent API"}


class TestChatEndpoint:
    def test_chat_returns_graph_result(self, client):
        with patch("api.main.graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={"intent": "weather", "response": "It's sunny in Tokyo."}
            )
            response = client.post(
                "/chat", json={"message": "What's the weather in Tokyo?"}
            )

        assert response.status_code == 200
        assert response.json() == {
            "intent": "weather",
            "response": "It's sunny in Tokyo.",
        }

    def test_chat_passes_message_into_initial_state(self, client):
        with patch("api.main.graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={"intent": "chitchat", "response": "Hi!"}
            )
            client.post("/chat", json={"message": "Hello there"})

            called_state = mock_graph.ainvoke.call_args[0][0]

        assert called_state["user_input"] == "Hello there"
        assert called_state["intent"] is None
        assert called_state["response"] is None

    def test_chat_requires_message_field(self, client):
        response = client.post("/chat", json={})
        assert response.status_code == 422


class TestCORS:
    def test_allows_configured_frontend_origin(self, client):
        with patch("api.main.graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={"intent": "chitchat", "response": "Hi!"}
            )
            response = client.post(
                "/chat",
                json={"message": "Hi"},
                headers={"Origin": "http://localhost:3000"},
            )

        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )

    def test_does_not_allow_unconfigured_origin(self, client):
        with patch("api.main.graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={"intent": "chitchat", "response": "Hi!"}
            )
            response = client.post(
                "/chat",
                json={"message": "Hi"},
                headers={"Origin": "http://evil.example.com"},
            )

        assert (
            response.headers.get("access-control-allow-origin")
            != "http://evil.example.com"
        )

    def test_configured_origin_is_used_when_env_var_set(self, monkeypatch):
        # Exercises the real _cors_allowed_origins() parsing against a fresh
        # app/TestClient rather than api.main's module-level app: that app is
        # already built (and shared by every test in this file via the
        # `client` fixture), and re-importing api.main to pick up a changed
        # env var would re-run its OTel provider setup — a reload this test
        # doesn't need and shouldn't risk.
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.testclient import TestClient
        from api.main import _cors_allowed_origins

        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://example-frontend.test")

        configured_app = FastAPI()
        configured_app.add_middleware(
            CORSMiddleware,
            allow_origins=_cors_allowed_origins(),
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @configured_app.get("/ping")
        def ping():
            return {"ok": True}

        configured_client = TestClient(configured_app)
        response = configured_client.get(
            "/ping", headers={"Origin": "https://example-frontend.test"}
        )

        assert (
            response.headers.get("access-control-allow-origin")
            == "https://example-frontend.test"
        )
