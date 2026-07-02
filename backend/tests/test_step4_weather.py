"""
Unit tests for Step 4 (weather) — tasks 4.1 to 4.8.

Covers:
  - weather_server.get_weather: valid city, unknown city, HTTP error
  - nodes.call_weather_tool: city extraction + weather_data written to state
  - graph.route_by_intent: weather routes to call_weather_tool, others to retrieve_context
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_geo_response(city_name: str, lat: float, lon: float) -> MagicMock:
    """Build a mock httpx response for the geocoding API."""
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {
        "results": [{"name": city_name, "latitude": lat, "longitude": lon}]
    }
    return r


def _mock_geo_empty() -> MagicMock:
    """Build a mock geocoding response that returns no results."""
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {}
    return r


def _mock_forecast_response(temp: float) -> MagicMock:
    """Build a mock httpx response for the forecast API."""
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"current": {"temperature_2m": temp, "weather_code": 1}}
    return r


# ---------------------------------------------------------------------------
# weather_server.get_weather
# ---------------------------------------------------------------------------

class TestGetWeather:

    @pytest.mark.asyncio
    async def test_valid_city_returns_temperature_string(self):
        """get_weather returns 'Current weather in {city}: {temp}°C' for a known city."""
        from mcp_servers.weather_server import get_weather

        geo = _mock_geo_response("Tokyo", 35.6895, 139.6917)
        forecast = _mock_forecast_response(22.5)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[geo, forecast])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_servers.weather_server.httpx.AsyncClient", return_value=mock_client):
            result = await get_weather("Tokyo")

        assert result == "Current weather in Tokyo: 22.5°C"

    @pytest.mark.asyncio
    async def test_unknown_city_returns_not_found_message(self):
        """get_weather returns 'Could not find location: {city}' when geocoding returns no results."""
        from mcp_servers.weather_server import get_weather

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_geo_empty())
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_servers.weather_server.httpx.AsyncClient", return_value=mock_client):
            result = await get_weather("NotARealCity99999")

        assert result == "Could not find location: NotARealCity99999"

    @pytest.mark.asyncio
    async def test_http_error_returns_unavailable_message(self):
        """get_weather returns 'Weather service unavailable' when the API call raises HTTPError."""
        import httpx
        from mcp_servers.weather_server import get_weather

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_servers.weather_server.httpx.AsyncClient", return_value=mock_client):
            result = await get_weather("Tokyo")

        assert result == "Weather service unavailable"

    @pytest.mark.asyncio
    async def test_temperature_value_is_preserved(self):
        """get_weather passes the exact temperature value from the API into the return string."""
        from mcp_servers.weather_server import get_weather

        geo = _mock_geo_response("Lima", -12.0464, -77.0428)
        forecast = _mock_forecast_response(17.3)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[geo, forecast])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("mcp_servers.weather_server.httpx.AsyncClient", return_value=mock_client):
            result = await get_weather("Lima")

        assert "17.3" in result


# ---------------------------------------------------------------------------
# nodes.call_weather_tool
# ---------------------------------------------------------------------------

class TestCallWeatherToolNode:

    @pytest.mark.asyncio
    async def test_weather_data_written_to_state(self):
        """call_weather_tool writes the weather string into state['weather_data']."""
        from agent.nodes import call_weather_tool

        state = {
            "user_input": "What is the weather in Riga right now?",
            "intent": "weather",
            "context": None,
            "weather_data": None,
            "response": None,
        }

        mock_llm_response = MagicMock()
        mock_llm_response.text = "Riga"

        with patch("agent.nodes.model") as mock_model, \
             patch("agent.nodes.get_weather", new_callable=AsyncMock) as mock_get_weather:

            mock_model.invoke.return_value = mock_llm_response
            mock_get_weather.return_value = "Current weather in Riga: 18.0°C"

            result = await call_weather_tool(state)

        assert result["weather_data"] == "Current weather in Riga: 18.0°C"

    @pytest.mark.asyncio
    async def test_existing_state_fields_are_preserved(self):
        """call_weather_tool does not overwrite other state fields."""
        from agent.nodes import call_weather_tool

        state = {
            "user_input": "Weather in Fukuoka?",
            "intent": "weather",
            "context": "some rag context",
            "weather_data": None,
            "response": None,
        }

        mock_llm_response = MagicMock()
        mock_llm_response.text = "Fukuoka"

        with patch("agent.nodes.model") as mock_model, \
             patch("agent.nodes.get_weather", new_callable=AsyncMock) as mock_get_weather:

            mock_model.invoke.return_value = mock_llm_response
            mock_get_weather.return_value = "Current weather in Fukuoka: 21.0°C"

            result = await call_weather_tool(state)

        assert result["user_input"] == "Weather in Fukuoka?"
        assert result["intent"] == "weather"
        assert result["context"] == "some rag context"

    @pytest.mark.asyncio
    async def test_city_is_extracted_from_full_question(self):
        """call_weather_tool uses the LLM to extract the city, not the raw user_input."""
        from agent.nodes import call_weather_tool

        state = {
            "user_input": "Is it raining in Abu Dhabi today?",
            "intent": "weather",
            "context": None,
            "weather_data": None,
            "response": None,
        }

        mock_llm_response = MagicMock()
        mock_llm_response.text = "Abu Dhabi"

        with patch("agent.nodes.model") as mock_model, \
             patch("agent.nodes.get_weather", new_callable=AsyncMock) as mock_get_weather:

            mock_model.invoke.return_value = mock_llm_response
            mock_get_weather.return_value = "Current weather in Abu Dhabi: 38.0°C"

            await call_weather_tool(state)

            # get_weather must be called with the extracted city, not the raw sentence
            mock_get_weather.assert_called_once_with(city="Abu Dhabi")


# ---------------------------------------------------------------------------
# graph.route_by_intent
# ---------------------------------------------------------------------------

class TestRouteByIntent:

    def test_weather_intent_routes_to_call_weather_tool(self):
        """route_by_intent returns 'call_weather_tool' for weather intent."""
        from agent.graph import route_by_intent

        state = {"intent": "weather", "user_input": "", "context": None,
                 "weather_data": None, "response": None}
        assert route_by_intent(state) == "call_weather_tool"

    def test_hotel_intent_routes_to_call_hotel_tool(self):
        """route_by_intent returns 'call_hotel_tool' for hotel intent."""
        from agent.graph import route_by_intent

        state = {"intent": "hotel", "user_input": "", "context": None,
                 "weather_data": None, "response": None}
        assert route_by_intent(state) == "call_hotel_tool"

    def test_transportation_intent_routes_to_retrieve_context(self):
        """route_by_intent returns 'retrieve_context' for transportation intent (pre-4b)."""
        from agent.graph import route_by_intent

        state = {"intent": "transportation", "user_input": "", "context": None,
                 "weather_data": None, "response": None}
        assert route_by_intent(state) == "retrieve_context"

    def test_general_intent_routes_to_retrieve_context(self):
        """route_by_intent returns 'retrieve_context' for general intent."""
        from agent.graph import route_by_intent

        state = {"intent": "general", "user_input": "", "context": None,
                 "weather_data": None, "response": None}
        assert route_by_intent(state) == "retrieve_context"

    def test_unknown_intent_routes_to_retrieve_context(self):
        """route_by_intent falls back to 'retrieve_context' for any unknown intent."""
        from agent.graph import route_by_intent

        state = {"intent": "something_unexpected", "user_input": "", "context": None,
                 "weather_data": None, "response": None}
        assert route_by_intent(state) == "retrieve_context"
