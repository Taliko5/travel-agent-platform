"""
Unit tests for agent/graph.py — route_by_intent branching logic.
"""

from agent.graph import route_by_intent


def _state(intent, user_input=""):
    return {
        "user_input": user_input,
        "intent": intent,
        "context": None,
        "weather_data": None,
        "flight_data": None,
        "hotel_data": None,
        "response": None,
    }


class TestRouteByIntent:
    def test_weather_routes_to_weather_tool(self):
        assert route_by_intent(_state("weather")) == "call_weather_tool"

    def test_hotel_routes_to_hotel_tool(self):
        assert route_by_intent(_state("hotel")) == "call_hotel_tool"

    def test_transportation_with_flight_keyword_routes_to_flight_tool(self):
        state = _state("transportation", user_input="Find me a flight to Paris")
        assert route_by_intent(state) == "call_flight_tool"

    def test_transportation_without_flight_keyword_routes_to_retrieve_context(self):
        state = _state("transportation", user_input="How do I get around the city?")
        assert route_by_intent(state) == "retrieve_context"

    def test_other_intent_routes_to_retrieve_context(self):
        assert route_by_intent(_state("chitchat")) == "retrieve_context"

    def test_flight_keyword_is_case_insensitive(self):
        state = _state("transportation", user_input="Book me a FLIGHT please")
        assert route_by_intent(state) == "call_flight_tool"
