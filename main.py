import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

from retrieval.agent import UniversalRAGAgent, AgentAnswer
from worker import app as celery_app, process_pdf_task
from models.schemas import ReasoningStep, VectorSourceResult, GraphTriple

RAW_DATA_DIR = Path("data/raw")

app = FastAPI(
    title="Universal Agentic RAG API",
    description="A highly scalable Agentic RAG system that uses Graph and Vector Search over massive documents.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    print("Initializing Universal RAG Agent backend...")
    agent = UniversalRAGAgent()
    print("Agent Initialized Successfully!")
except Exception as e:
    print(f"Failed to initialize Agent: {e}")
    agent = None

# In-process registry of in-flight ingestion tasks, keyed by Celery task_id.
# Entries are dropped once the underlying document shows up in Qdrant's
# distinct document_id listing (see list_documents below) — this keeps the
# registry from growing unbounded and avoids a second source of truth once
# a document is actually ready.
_ingestion_registry: Dict[str, dict] = {}


class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    status: str
    reasoning_steps: List[ReasoningStep] = []
    sources: List[VectorSourceResult] = []
    graph_triples: List[GraphTriple] = []

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

class DocumentSummary(BaseModel):
    id: str
    title: str
    status: str

class DocumentListResponse(BaseModel):
    documents: List[DocumentSummary]

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

    _ingestion_registry[task.id] = {"filename": saved_filename, "status": "queued"}

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
        _ingestion_registry.pop(task_id, None)
        return IngestionStatusResponse(
            task_id=task_id,
            status=task.state,
            message="Ingestion complete. You can now ask questions about this document.",
        )

    if task.state == "FAILURE":
        if task_id in _ingestion_registry:
            _ingestion_registry[task_id]["status"] = "failed"
        return IngestionStatusResponse(
            task_id=task_id,
            status=task.state,
            message="Ingestion failed. Please check the worker logs and try again.",
            error=str(task.result),
        )

    if task.state == "STARTED":
        message = "Ingestion is currently running."
        if task_id in _ingestion_registry:
            _ingestion_registry[task_id]["status"] = "ingesting"
    elif task.state == "PENDING":
        message = "Ingestion job is queued and will start shortly."
    else:
        message = f"Ingestion status: {task.state}."

    return IngestionStatusResponse(
        task_id=task_id,
        status=task.state,
        message=message,
    )

@app.get("/documents", response_model=DocumentListResponse)
def list_documents():
    ready_ids = agent.vector_manager.list_document_ids() if agent else []
    ready_set = set(ready_ids)

    documents = [
        DocumentSummary(id=doc_id, title=doc_id, status="ready")
        for doc_id in ready_ids
    ]

    for task_id, entry in list(_ingestion_registry.items()):
        if entry["filename"] in ready_set:
            _ingestion_registry.pop(task_id, None)
            continue
        status = entry["status"]
        if status not in ("failed",):
            task = AsyncResult(task_id, app=celery_app)
            if task.state == "STARTED":
                status = "ingesting"
            elif task.state == "FAILURE":
                status = "failed"
        documents.append(DocumentSummary(id=task_id, title=entry["filename"], status=status))

    return DocumentListResponse(documents=documents)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not agent:
        raise HTTPException(status_code=500, detail="Backend Agent failed to initialize. Check API keys.")

    try:
        result: AgentAnswer = await agent.aquery(request.query)

        return ChatResponse(
            answer=result.answer,
            status="success",
            reasoning_steps=result.reasoning_steps,
            sources=result.sources,
            graph_triples=result.graph_triples,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
