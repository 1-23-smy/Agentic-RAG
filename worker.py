import asyncio
import os
from celery import Celery
from dotenv import load_dotenv

# Load environmental configurations
load_dotenv()

from ingestion.parser import MedicalDocumentParser
from ingestion.chunker import HierarchicalChunker
from ingestion.graph_extractor import GraphExtractor
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager

# Configure Celery to use Redis as the Message Broker
app = Celery(
    'rag_ingestion_worker',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Optional: Configure Celery settings
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # macOS Objective-C/MPS-backed ML libraries can crash in Celery's default fork pool.
    worker_pool='solo',
    worker_concurrency=1,
    worker_prefetch_multiplier=1
)

PROCESSED_DATA_DIR = "data/processed"

async def async_process_document(file_path: str):
    """The actual async ingestion pipeline logic extracted from ingest_all.py"""
    print(f"\n{'='*50}\n🚀 Worker Started Processing: {file_path}\n{'='*50}")
    
    try:
        # Initialize Core Components inside the worker process safely
        parser = MedicalDocumentParser()
        chunker = HierarchicalChunker(target_chunk_size=2000, overlap=200)
        extractor = GraphExtractor()
        vector_store = VectorStoreManager()
        graph_store = GraphStoreManager()

        # 1. Parsing
        print("\n[Step 1/5] Extracting semantic markdown from document...")
        markdown_content = await parser.parse_document(file_path)
        
        # 2. Hierarchical Chunking
        print("\n[Step 2/5] Performing Hierarchical Chunking...")
        doc_id = os.path.basename(file_path)
        chunks = chunker.chunk_document(markdown_content, document_id=doc_id)
        print(f"Created {len(chunks)} contextual chunks.")

        # 3. Knowledge Graph Extraction
        print("\n[Step 3/5] Extracting Knowledge Graph entities and relationships...")
        entities, relationships = await extractor.extract_knowledge_graph(chunks)

        # 4. Ingest to Vector Database
        print("\n[Step 4/5] Ingesting Chunks to Qdrant...")
        await vector_store.ingest_chunks(chunks)

        # 5. Ingest to Graph Database
        print("\n[Step 5/5] Ingesting Graph Triples to Neo4j...")
        graph_store.ingest_knowledge_graph(entities, relationships)
        
        # Cleanup
        graph_store.close()
        
        # Move processed file
        filename = os.path.basename(file_path)
        if not os.path.exists(PROCESSED_DATA_DIR):
            os.makedirs(PROCESSED_DATA_DIR)
        os.rename(file_path, os.path.join(PROCESSED_DATA_DIR, filename))

        print(f"\n✅ Worker Successfully processed and indexed '{doc_id}'.")
        return f"Success: {doc_id}"

    except Exception as e:
        print(f"\n❌ Error processing {file_path}: {e}")
        raise e

@app.task(name="process_pdf_task", bind=True, max_retries=3)
def process_pdf_task(self, file_path: str):
    """
    Celery task that wraps the async ingestion pipeline.
    This is the function you call via .delay() to throw work onto the Redis queue.
    """
    if not os.path.exists(file_path):
        return f"Error: File {file_path} not found."

    # Run the async pipeline within the synchronous Celery worker wrapper
    result = asyncio.run(async_process_document(file_path))
    return result
