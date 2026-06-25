from agent.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
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
    
def generate_response(state: AgentState) -> AgentState:
    """Generate a response based on the classified intent and user's question."""
    
    prompt = f"""
    intent: {state["intent"]}
    question: {state["user_input"]}
    Respond with about 200 words. Include URLs if relevant.
    """
    
    response = model.invoke(prompt)
    
    return {
        **state,
        "response": response.text
    }