from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

from agent.graph import build_graph # noqa: E402


app = FastAPI(title="travel agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
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
async def chat(request: ChatRequest):
    result = await graph.ainvoke({
        "user_input": request.message,
        "intent":None,
        "response":None,
        "flight_data": None,
        "weather_data": None,
        "hotel_data":None,
    })
    return ChatResponse(
        intent=result["intent"],
        response=result["response"]
    )
    