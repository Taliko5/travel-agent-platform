from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import classify_intent, retrieve_context_node, call_weather_tool, generate_response


def route_by_intent(state: AgentState) -> str:
    """Route to the appropriate tool node based on classified intent."""
    if state["intent"] == "weather":
        return "call_weather_tool"
    return "retrieve_context"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify_intent",   classify_intent)
    graph.add_node("retrieve_context",  retrieve_context_node)
    graph.add_node("call_weather_tool", call_weather_tool)
    graph.add_node("generate_response", generate_response)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges("classify_intent", route_by_intent)
    graph.add_edge("retrieve_context",  "generate_response")
    graph.add_edge("call_weather_tool", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()
