import multiprocessing
multiprocessing.set_start_method("spawn", force=True)  # MUST be first

import asyncio
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

app = Celery(
    'rag_ingestion_worker',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1
    # removed solo pool and concurrency=1
)

PROCESSED_DATA_DIR = "data/processed"

def get_or_create_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

async def async_process_document(file_path: str):
    from ingestion.parser import MedicalDocumentParser
    from ingestion.chunker import HierarchicalChunker
    from ingestion.graph_extractor import GraphExtractor
    from storage.vector_store import VectorStoreManager
    from storage.graph_store import GraphStoreManager

    print(f"\n{'='*50}\n🚀 Worker Started Processing: {file_path}\n{'='*50}")

    parser = MedicalDocumentParser()
    chunker = HierarchicalChunker(target_chunk_size=2000, overlap=200)
    extractor = GraphExtractor()
    vector_store = VectorStoreManager()
    graph_store = GraphStoreManager()

    print("\n[Step 1/5] Extracting semantic markdown from document...")
    markdown_content = await parser.parse_document(file_path)

    print("\n[Step 2/5] Performing Hierarchical Chunking...")
    doc_id = os.path.basename(file_path)
    chunks = chunker.chunk_document(markdown_content, document_id=doc_id)
    print(f"Created {len(chunks)} contextual chunks.")

    print("\n[Step 3/5] Extracting Knowledge Graph entities and relationships...")
    entities, relationships = await extractor.extract_knowledge_graph(chunks)

    print("\n[Step 4/5] Ingesting Chunks to Qdrant...")
    await vector_store.ingest_chunks(chunks)

    print("\n[Step 5/5] Ingesting Graph Triples to Neo4j...")
    graph_store.ingest_knowledge_graph(entities, relationships)
    graph_store.close()

    filename = os.path.basename(file_path)
    if not os.path.exists(PROCESSED_DATA_DIR):
        os.makedirs(PROCESSED_DATA_DIR)
    os.rename(file_path, os.path.join(PROCESSED_DATA_DIR, filename))

    print(f"\n✅ Successfully processed '{doc_id}'.")
    return f"Success: {doc_id}"

@app.task(name="process_pdf_task", bind=True, max_retries=3)
def process_pdf_task(self, file_path: str):
    if not os.path.exists(file_path):
        return f"Error: File {file_path} not found."

    try:
        loop = get_or_create_loop()
        result = loop.run_until_complete(async_process_document(file_path))
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)