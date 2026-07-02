"""
Unit tests for Step 4 (hotels) — tasks 4.16 to 4.22.

Covers:
  - hotel_server.search_hotels: known city, multi-word city, no match, empty query, all cities
  - nodes.call_hotel_tool: hotel_data written to state, other fields preserved
  - graph.route_by_intent: hotel → call_hotel_tool, others unaffected
"""

import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# hotel_server.search_hotels
# ---------------------------------------------------------------------------

class TestSearchHotels:

    @pytest.mark.asyncio
    async def test_known_city_returns_matching_hotels(self):
        """search_hotels returns hotels for a known city."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("hotels in Tokyo")

        assert "Tokyo" in result
        assert "Park Hyatt Tokyo" in result
        assert "$450/night" in result

    @pytest.mark.asyncio
    async def test_result_contains_found_n_hotels_header(self):
        """search_hotels return value starts with 'Found N hotels in {city}:'."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("where to stay in Riga")

        assert result.startswith("Found 3 hotels in Riga:")

    @pytest.mark.asyncio
    async def test_result_includes_star_rating_and_highlight(self):
        """Each hotel entry contains star rating and highlight text."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("hotels in Lima")

        assert "⭐" in result
        assert "→" in result

    @pytest.mark.asyncio
    async def test_multi_word_city_abu_dhabi_is_matched(self):
        """search_hotels correctly matches multi-word city name 'abu dhabi'."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("hotels in Abu Dhabi")

        assert "Abu Dhabi" in result
        assert "Emirates Palace" in result
        assert "(Showing sample results" not in result

    @pytest.mark.asyncio
    async def test_no_match_returns_fallback_with_note(self):
        """search_hotels returns fallback hotels with note when city is not in mock data."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("hotels in Berlin")

        assert "(Showing sample results — specific destination not found)" in result
        assert "City Center Hotel" in result or "Budget Inn Express" in result or "Boutique Stay" in result

    @pytest.mark.asyncio
    async def test_empty_query_returns_fallback(self):
        """search_hotels returns fallback for an empty query string."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("")

        assert "(Showing sample results — specific destination not found)" in result

    @pytest.mark.asyncio
    async def test_all_six_cities_are_covered(self):
        """Each city defined in MOCK_HOTELS returns matched (non-fallback) results."""
        from mcp_servers.hotel_server import search_hotels, MOCK_HOTELS

        for city in MOCK_HOTELS:
            result = await search_hotels(f"hotels in {city}")
            assert "(Showing sample results" not in result, (
                f"Expected real results for {city}, got fallback"
            )

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self):
        """search_hotels matches city names regardless of query capitalisation."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("HOTELS IN FUKUOKA")

        assert "Dormy Inn Hakata" in result
        assert "(Showing sample results" not in result

    @pytest.mark.asyncio
    async def test_star_count_matches_hotel_rating(self):
        """Five-star hotels show five star emojis; three-star hotels show three."""
        from mcp_servers.hotel_server import search_hotels

        result = await search_hotels("hotels in Kyoto")

        assert "⭐⭐⭐⭐⭐" in result  # Westin Miyako — 5 stars
        assert "⭐⭐" in result       # Piece Hostel — 2 stars


# ---------------------------------------------------------------------------
# nodes.call_hotel_tool
# ---------------------------------------------------------------------------

class TestCallHotelToolNode:

    @pytest.mark.asyncio
    async def test_hotel_data_written_to_state(self):
        """call_hotel_tool writes the hotel string into state['hotel_data']."""
        from agent.nodes import call_hotel_tool

        state = {
            "user_input": "Find me hotels in Riga",
            "intent": "hotel",
            "context": None,
            "weather_data": None,
            "flight_data": None,
            "hotel_data": None,
            "response": None,
        }

        mock_result = "Found 3 hotels in Riga:\n\n1. Grand Hotel Kempinski | ⭐⭐⭐⭐⭐ | $280/night\n   → overlooking Freedom Monument"

        with patch("agent.nodes.search_hotels", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_result
            result = await call_hotel_tool(state)

        assert result["hotel_data"] == mock_result

    @pytest.mark.asyncio
    async def test_search_hotels_called_with_user_input(self):
        """call_hotel_tool passes state['user_input'] directly to search_hotels."""
        from agent.nodes import call_hotel_tool

        state = {
            "user_input": "hotels in Lima",
            "intent": "hotel",
            "context": None,
            "weather_data": None,
            "flight_data": None,
            "hotel_data": None,
            "response": None,
        }

        with patch("agent.nodes.search_hotels", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "Found 3 hotels in Lima:\n..."
            await call_hotel_tool(state)

        mock_search.assert_called_once_with(query="hotels in Lima")

    @pytest.mark.asyncio
    async def test_existing_state_fields_are_preserved(self):
        """call_hotel_tool does not overwrite other state fields."""
        from agent.nodes import call_hotel_tool

        state = {
            "user_input": "hotels in Tokyo",
            "intent": "hotel",
            "context": "some rag context",
            "weather_data": None,
            "flight_data": None,
            "hotel_data": None,
            "response": None,
        }

        with patch("agent.nodes.search_hotels", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "Found 3 hotels in Tokyo:\n..."
            result = await call_hotel_tool(state)

        assert result["user_input"] == "hotels in Tokyo"
        assert result["intent"] == "hotel"
        assert result["context"] == "some rag context"
        assert result["weather_data"] is None
        assert result["flight_data"] is None


# ---------------------------------------------------------------------------
# graph.route_by_intent — hotel routing
# ---------------------------------------------------------------------------

class TestRouteByIntentHotels:

    def _state(self, intent: str, user_input: str = "") -> dict:
        return {
            "intent": intent,
            "user_input": user_input,
            "context": None,
            "weather_data": None,
            "flight_data": None,
            "hotel_data": None,
            "response": None,
        }

    def test_hotel_intent_routes_to_call_hotel_tool(self):
        """route_by_intent returns 'call_hotel_tool' for hotel intent."""
        from agent.graph import route_by_intent

        state = self._state("hotel", "Best hotels in Fukuoka?")
        assert route_by_intent(state) == "call_hotel_tool"

    def test_hotel_routing_independent_of_query_keywords(self):
        """Hotel intent always routes to call_hotel_tool regardless of query wording."""
        from agent.graph import route_by_intent

        for query in ["where to stay in Riga", "accommodation in Lima", "ryokan in Kyoto"]:
            state = self._state("hotel", query)
            assert route_by_intent(state) == "call_hotel_tool", (
                f"Expected call_hotel_tool for query: '{query}'"
            )

    def test_weather_routing_unaffected_by_hotel_change(self):
        """Adding hotel routing does not break the existing weather route."""
        from agent.graph import route_by_intent

        state = self._state("weather", "What is the weather in Tokyo?")
        assert route_by_intent(state) == "call_weather_tool"

    def test_transportation_with_flight_keyword_unaffected(self):
        """Adding hotel routing does not break flight routing for transportation intent."""
        from agent.graph import route_by_intent

        state = self._state("transportation", "Show me flights from Riga to London")
        assert route_by_intent(state) == "call_flight_tool"

    def test_transportation_train_still_uses_rag(self):
        """Non-flight transportation still falls through to retrieve_context."""
        from agent.graph import route_by_intent

        state = self._state("transportation", "Train from Tokyo to Kyoto")
        assert route_by_intent(state) == "retrieve_context"

    def test_general_routes_to_retrieve_context(self):
        """General intent always uses RAG."""
        from agent.graph import route_by_intent

        state = self._state("general", "What food should I try in Lima?")
        assert route_by_intent(state) == "retrieve_context"
