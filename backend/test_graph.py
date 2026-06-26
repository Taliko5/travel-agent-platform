from agent.graph import build_graph
from agent.state import AgentState
from dotenv import load_dotenv

load_dotenv()  

initial_state: AgentState = {
    "user_input": "show me the possible route from tokyo to NY",
    "intent": None,
    "response": None,
}
graph = build_graph()

print(graph.invoke(initial_state))