import re
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

# Load Env Vars (e.g., GEMINI_API_KEY, QDRANT_URL, NEO4J_URI) before importing Agent
load_dotenv()

from retrieval.agent import UniversalRAGAgent
from worker import app as celery_app, process_pdf_task

RAW_DATA_DIR = Path("data/raw")

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

class IngestionUploadResponse(BaseModel):
    task_id: str
    filename: str
    status: str
    message: str

class IngestionStatusResponse(BaseModel):
    task_id: str
    status: str
    message: str
    error: Optional[str] = None

def _safe_pdf_filename(filename: str) -> str:
    original_name = Path(filename).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._")
    if not safe_name:
        safe_name = "uploaded.pdf"
    return f"{uuid4().hex}_{safe_name}"

@app.get("/")
async def root():
    return {"message": "Agentic RAG Backend is Live and Running!"}

@app.post("/ingest/upload", response_model=IngestionUploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files can be uploaded.")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    saved_filename = _safe_pdf_filename(filename)
    saved_path = RAW_DATA_DIR / saved_filename

    try:
        file.file.seek(0)
        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        task = process_pdf_task.delay(str(saved_path))
    except HTTPException:
        raise
    except Exception as e:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to upload PDF for ingestion: {e}") from e

    return IngestionUploadResponse(
        task_id=task.id,
        filename=saved_filename,
        status="queued",
        message="PDF uploaded. Ingestion has started in the background.",
    )

@app.get("/ingest/status/{task_id}", response_model=IngestionStatusResponse)
def get_ingestion_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "SUCCESS":
        return IngestionStatusResponse(
            task_id=task_id,
            status=task.state,
            message="Ingestion complete. You can now ask questions about this document.",
        )

    if task.state == "FAILURE":
        return IngestionStatusResponse(
            task_id=task_id,
            status=task.state,
            message="Ingestion failed. Please check the worker logs and try again.",
            error=str(task.result),
        )

    if task.state == "STARTED":
        message = "Ingestion is currently running."
    elif task.state == "PENDING":
        message = "Ingestion job is queued and will start shortly."
    else:
        message = f"Ingestion status: {task.state}."

    return IngestionStatusResponse(
        task_id=task_id,
        status=task.state,
        message=message,
    )

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
