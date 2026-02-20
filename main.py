from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Agentic RAG API",
    description="Backend API for the scalable 3000+ page Medical Agentic RAG System",
    version="0.1.0"
)

class QueryRequest(BaseModel):
    query: str
    session_id: str = "default"

class QueryResponse(BaseModel):
    answer: str
    sources: list

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Agentic RAG Engine is running"}

@app.post("/api/chat", response_model=QueryResponse)
async def chat_endpoint(request: QueryRequest):
    # TODO: Connect to LangGraph Agent Orchestrator
    
    return QueryResponse(
        answer=f"Echoing back your query for now: {request.query}. Agent logic goes here.",
        sources=[]
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
