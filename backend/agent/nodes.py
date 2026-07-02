from agent.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from rag.retriever import retrieve_context
from mcp_servers.weather_server import get_weather

load_dotenv()

model = ChatGoogleGenerativeAI(model="gemini-3.5-flash", thinking_level="low")

def classify_intent(state: AgentState)-> AgentState:
    """Classify the user's input into a category."""
    
    valid_intents = ["transportation", "hotel", "weather", "general"]

    prompt = f"""
    Classify the following user question into one of these categories:
    {", ".join(valid_intents)}

    
    question:{state["user_input"]}
    
    Respond with only the category name, one word, lowercase.
    """
    
    response = model.invoke(prompt)
    raw_intent = response.text.strip().lower()
    intent = next(
        (valid for valid in valid_intents if valid in raw_intent),
        "general"  # どれにも当たらなければ "general" にフォールバック
    )
    
    return {
        **state,
        "intent":intent
    }
    
def retrieve_context_node(state: AgentState) -> AgentState:
    """Retrieve relevant travel context from ChromaDB."""
    context = retrieve_context(state["user_input"])
    return {
        **state,
        "context": context,
    }


async def call_weather_tool(state: AgentState) -> AgentState:
    """Extract city name from user input, then fetch live weather."""
    extraction = model.invoke(
        f"Extract only the city name from this question. Reply with the city name only, nothing else.\n\nQuestion: {state['user_input']}"
    )
    city = extraction.text.strip()
    weather = await get_weather(city=city)
    return {
        **state,
        "weather_data": weather,
    }


def generate_response(state: AgentState) -> AgentState:
    """Generate a response based on the classified intent and user's question."""

    context_section = ""
    if state.get("context"):
        context_section = f"\nRelevant travel information:\n{state['context']}\n"

    weather_section = ""
    if state.get("weather_data"):
        weather_section = f"\nLive weather data:\n{state['weather_data']}\n"

    prompt = f"""
    intent: {state["intent"]}
    {context_section}
    {weather_section}
    question: {state["user_input"]}
    Respond with about 200 words. Include URLs if relevant.
    """

    response = model.invoke(prompt)

    return {
        **state,
        "response": response.text,
    }