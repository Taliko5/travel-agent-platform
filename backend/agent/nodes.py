from functools import lru_cache
from agent.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from rag.retriever import retrieve_context
from mcp_servers.weather_server import get_weather
from mcp_servers.flight_server import search_flights
from mcp_servers.hotel_server import search_hotels
from observability.metrics import intent_classification_count

load_dotenv()

VALID_INTENTS = ["transportation", "hotel", "weather", "general"]


@lru_cache(maxsize=1)
def get_model():
    return ChatGoogleGenerativeAI(model="gemini-3.5-flash", thinking_level="low")


def classify_intent(state: AgentState) -> AgentState:
    """Classify the user's input into a category."""

    prompt = f"""
    Classify the following user question into one of these categories:
    {", ".join(VALID_INTENTS)}


    question:{state["user_input"]}

    Respond with only the category name, one word, lowercase.
    """

    response = get_model().invoke(prompt)
    raw_intent = response.text.strip().lower()
    matched = next((valid for valid in VALID_INTENTS if valid in raw_intent), None)

    # Fall back to "general" when the response matches none of the valid intents.
    # The `fallback` label separates a genuine general question from a "general"
    # produced by a failing classifier — the two are indistinguishable from the
    # resolved intent alone, which is how classifier degradation goes unnoticed.
    fallback = matched is None
    intent = matched if matched is not None else "general"

    intent_classification_count.add(
        1, {"intent": intent, "fallback": "true" if fallback else "false"}
    )

    return {**state, "intent": intent}


def retrieve_context_node(state: AgentState) -> AgentState:
    """Retrieve relevant travel context from ChromaDB."""
    context = retrieve_context(state["user_input"])
    return {
        **state,
        "context": context,
    }


async def call_weather_tool(state: AgentState) -> AgentState:
    """Extract city name from user input, then fetch live weather."""
    extraction = get_model().invoke(
        f"Extract only the city name from this question. Reply with the city name only, nothing else.\n\nQuestion: {state['user_input']}"
    )
    city = extraction.text.strip()
    weather = await get_weather(city=city)
    return {
        **state,
        "weather_data": weather,
    }


async def call_flight_tool(state: AgentState) -> AgentState:
    """Call the mock flight search tool."""
    flights = await search_flights(query=state["user_input"])
    return {
        **state,
        "flight_data": flights,
    }


async def call_hotel_tool(state: AgentState) -> AgentState:
    """Call the mock hotel search tool."""
    hotels = await search_hotels(query=state["user_input"])
    return {
        **state,
        "hotel_data": hotels,
    }


def generate_response(state: AgentState) -> AgentState:
    """Generate a response based on the classified intent and user's question."""

    context_section = ""
    if state.get("context"):
        context_section = f"\nRelevant travel information:\n{state['context']}\n"

    weather_section = ""
    if state.get("weather_data"):
        weather_section = f"\nLive weather data:\n{state['weather_data']}\n"

    flight_section = ""
    if state.get("flight_data"):
        flight_section = f"\nFlight search results:\n{state['flight_data']}\n"

    hotel_section = ""
    if state.get("hotel_data"):
        hotel_section = f"\nHotel search results:\n{state['hotel_data']}\n"

    prompt = f"""
    intent: {state["intent"]}
    {context_section}
    {weather_section}
    {flight_section}
    {hotel_section}
    question: {state["user_input"]}
    Respond with about 200 words. Include URLs if relevant.
    """

    response = get_model().invoke(prompt)

    return {
        **state,
        "response": response.text,
    }
