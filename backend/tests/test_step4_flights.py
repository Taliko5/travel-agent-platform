"""
Unit tests for Step 4 (flights) — tasks 4.9 to 4.15.

Covers:
  - flight_server.search_flights: known pair, reverse pair, single city, no match, empty query
  - nodes.call_flight_tool: flight_data written to state, other fields preserved
  - graph.route_by_intent: flight keywords → call_flight_tool, non-flight transportation → retrieve_context
"""

import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# flight_server.search_flights
# ---------------------------------------------------------------------------

class TestSearchFlights:

    @pytest.mark.asyncio
    async def test_known_pair_returns_matching_flights(self):
        """search_flights returns flights for a known city pair."""
        from mcp_servers.flight_server import search_flights

        result = await search_flights("flights from Tokyo to New York")

        assert "Tokyo" in result
        assert "New York" in result
        assert "ANA" in result
        assert "NH009" in result
        assert "$850" in result

    @pytest.mark.asyncio
    async def test_result_contains_found_n_flights_header(self):
        """search_flights return value starts with 'Found N flights:'."""
        from mcp_servers.flight_server import search_flights

        result = await search_flights("Tokyo to London")

        assert result.startswith("Found 3 flights:")

    @pytest.mark.asyncio
    async def test_result_format_includes_dep_arr_price(self):
        """Each flight line contains Dep, Arr, and Price labels."""
        from mcp_servers.flight_server import search_flights

        result = await search_flights("flights from Fukuoka to Tokyo")

        assert "Dep:" in result
        assert "Arr:" in result
        assert "Price:" in result

    @pytest.mark.asyncio
    async def test_reverse_pair_is_matched(self):
        """search_flights matches when origin/destination appear in reversed order in query."""
        from mcp_servers.flight_server import search_flights

        result = await search_flights("I'm travelling from London to Riga")

        assert "Riga" in result or "London" in result
        assert "airBaltic" in result or "Ryanair" in result or "Wizz Air" in result

    @pytest.mark.asyncio
    async def test_no_match_returns_fallback_with_note(self):
        """search_flights returns fallback flights with the 'specific route not found' note when no city pair matches."""
        from mcp_servers.flight_server import search_flights

        result = await search_flights("flights from Berlin to Sydney")

        assert "(Showing sample results — specific route not found)" in result
        assert "Generic Air" in result or "Budget Fly" in result or "Star Travel" in result

    @pytest.mark.asyncio
    async def test_empty_query_returns_fallback(self):
        """search_flights returns fallback for an empty query string."""
        from mcp_servers.flight_server import search_flights

        result = await search_flights("")

        assert "(Showing sample results — specific route not found)" in result

    @pytest.mark.asyncio
    async def test_all_six_city_pairs_are_covered(self):
        """Each city pair defined in MOCK_FLIGHTS returns matched (non-fallback) results."""
        from mcp_servers.flight_server import search_flights, MOCK_FLIGHTS

        for (origin, destination) in MOCK_FLIGHTS:
            result = await search_flights(f"flights from {origin} to {destination}")
            assert "(Showing sample results" not in result, (
                f"Expected real results for {origin} → {destination}, got fallback"
            )

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self):
        """search_flights matches city names regardless of query capitalisation."""
        from mcp_servers.flight_server import search_flights

        result = await search_flights("FLIGHTS FROM TOKYO TO NEW YORK")

        assert "ANA" in result
        assert "(Showing sample results" not in result


# ---------------------------------------------------------------------------
# nodes.call_flight_tool
# ---------------------------------------------------------------------------

class TestCallFlightToolNode:

    @pytest.mark.asyncio
    async def test_flight_data_written_to_state(self):
        """call_flight_tool writes the flight string into state['flight_data']."""
        from agent.nodes import call_flight_tool

        state = {
            "user_input": "Show me flights from Tokyo to New York",
            "intent": "transportation",
            "context": None,
            "weather_data": None,
            "flight_data": None,
            "response": None,
        }

        mock_result = "Found 3 flights:\n\n1. ANA NH009 | Tokyo → New York | Dep: 11:00 | Arr: 10:05+1 | Price: $850"

        with patch("agent.nodes.search_flights", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_result
            result = await call_flight_tool(state)

        assert result["flight_data"] == mock_result

    @pytest.mark.asyncio
    async def test_search_flights_called_with_user_input(self):
        """call_flight_tool passes state['user_input'] directly to search_flights."""
        from agent.nodes import call_flight_tool

        state = {
            "user_input": "flights from Riga to London",
            "intent": "transportation",
            "context": None,
            "weather_data": None,
            "flight_data": None,
            "response": None,
        }

        with patch("agent.nodes.search_flights", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "Found 3 flights:\n..."
            await call_flight_tool(state)

        mock_search.assert_called_once_with(query="flights from Riga to London")

    @pytest.mark.asyncio
    async def test_existing_state_fields_are_preserved(self):
        """call_flight_tool does not overwrite other state fields."""
        from agent.nodes import call_flight_tool

        state = {
            "user_input": "flights from Lima to Miami",
            "intent": "transportation",
            "context": "some rag context",
            "weather_data": None,
            "flight_data": None,
            "response": None,
        }

        with patch("agent.nodes.search_flights", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "Found 3 flights:\n..."
            result = await call_flight_tool(state)

        assert result["user_input"] == "flights from Lima to Miami"
        assert result["intent"] == "transportation"
        assert result["context"] == "some rag context"
        assert result["weather_data"] is None


# ---------------------------------------------------------------------------
# graph.route_by_intent — flight routing
# ---------------------------------------------------------------------------

class TestRouteByIntentFlights:

    def _state(self, intent: str, user_input: str = "") -> dict:
        return {
            "intent": intent,
            "user_input": user_input,
            "context": None,
            "weather_data": None,
            "flight_data": None,
            "response": None,
        }

    def test_transportation_with_flight_keyword_routes_to_flight_tool(self):
        """route_by_intent sends transportation intent to call_flight_tool when query mentions flights."""
        from agent.graph import route_by_intent

        for keyword in ["flight", "flights", "fly", "flying", "airline", "airlines", "airport", "plane", "airfare"]:
            state = self._state("transportation", f"I want to {keyword} from Tokyo to London")
            assert route_by_intent(state) == "call_flight_tool", (
                f"Expected call_flight_tool for keyword '{keyword}'"
            )

    def test_transportation_without_flight_keyword_routes_to_retrieve_context(self):
        """route_by_intent sends transportation intent to retrieve_context when no flight keywords present."""
        from agent.graph import route_by_intent

        state = self._state("transportation", "How do I get from Kyoto to Tokyo by train?")
        assert route_by_intent(state) == "retrieve_context"

    def test_transportation_bus_query_routes_to_retrieve_context(self):
        """route_by_intent uses RAG for bus/train transportation queries."""
        from agent.graph import route_by_intent

        state = self._state("transportation", "Is there a bus from Riga to Tallinn?")
        assert route_by_intent(state) == "retrieve_context"

    def test_weather_still_routes_to_weather_tool(self):
        """Adding flight routing does not break the existing weather route."""
        from agent.graph import route_by_intent

        state = self._state("weather", "What is the weather in Tokyo?")
        assert route_by_intent(state) == "call_weather_tool"

    def test_hotel_routes_to_call_hotel_tool(self):
        """Hotel intent routes to call_hotel_tool (wired in 4.20)."""
        from agent.graph import route_by_intent

        state = self._state("hotel", "Best hotels in Fukuoka?")
        assert route_by_intent(state) == "call_hotel_tool"

    def test_general_routes_to_retrieve_context(self):
        """General intent always uses RAG."""
        from agent.graph import route_by_intent

        state = self._state("general", "What food should I try in Lima?")
        assert route_by_intent(state) == "retrieve_context"
