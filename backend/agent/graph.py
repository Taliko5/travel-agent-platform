from langgraph.graph import StateGraph, START, END
from agent.state import AgentState
from agent.nodes import classify_intent, generate_response

def build_graph():
    graph =StateGraph(AgentState)
    
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("generate_response",generate_response)
    
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", "generate_response")
    graph.add_edge("generate_response", END)
    
    return graph.compile()