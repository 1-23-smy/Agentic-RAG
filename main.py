from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

# Load Env Vars (e.g., GEMINI_API_KEY, QDRANT_URL, NEO4J_URI) before importing Agent
load_dotenv()

from retrieval.agent import UniversalRAGAgent

app = FastAPI(
    title="Universal Agentic RAG API",
    description="A highly scalable Agentic RAG system that uses Graph and Vector Search over massive documents.",
    version="1.0.0"
)

# Initialize global Agent so memory/TCP connections are preserved across requests
try:
    print("Initializing Universal RAG Agent backend...")
    agent = UniversalRAGAgent()
    print("Agent Initialized Successfully!")
except Exception as e:
    print(f"Failed to initialize Agent: {e}")
    agent = None

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    status: str

@app.get("/")
async def root():
    return {"message": "Agentic RAG Backend is Live and Running!"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not agent:
        raise HTTPException(status_code=500, detail="Backend Agent failed to initialize. Check API keys.")
    
    try:
        # ReAct Agents might take 5-10 seconds depending on how many tools they use
        answer = await agent.aquery(request.query)
        
        return ChatResponse(
            answer=answer,
            status="success"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
