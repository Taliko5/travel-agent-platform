from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import classify_intent, retrieve_context_node, call_weather_tool, call_flight_tool, call_hotel_tool, generate_response


FLIGHT_KEYWORDS = {"flight", "flights", "fly", "flying", "airline", "airlines", "airport", "plane", "airfare"}

def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate tool node based on classified intent."""
    intent = state["intent"]
    if intent == "weather":
        return "call_weather_tool"
    if intent == "transportation":
        words = set(state["user_input"].lower().split())
        if words & FLIGHT_KEYWORDS:
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
