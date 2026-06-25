from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from agent.graph import build_graph


app = FastAPI(title="travel agent API", version="0.1.0")
graph = build_graph()

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    intent: str
    response: str
    

@app.get("/health")
def health_check():
    return {"status":"ok", "version":"0.1.0"}

@app.get("/")
def root():
    return {"message":"travel agent API"}
    
    
@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = graph.invoke({
        "user_input": request.message,
        "intent":None,
        "response":None,
    })
    return ChatResponse(
        intent=result["intent"],
        response=result["response"]
    )
    