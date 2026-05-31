import asyncio
import os
import glob
from dotenv import load_dotenv

# Load environmental configurations
load_dotenv()

from ingestion.parser import MedicalDocumentParser
from ingestion.chunker import HierarchicalChunker
from ingestion.graph_extractor import GraphExtractor
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager

# Configuration
RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"

async def process_document(file_path: str, parser: MedicalDocumentParser, chunker: HierarchicalChunker, 
                           extractor: GraphExtractor, vector_store: VectorStoreManager, graph_store: GraphStoreManager):
    print(f"\n{'='*50}\n🚀 Processing: {file_path}\n{'='*50}")
    
    # 1. Parsing (LlamaParse via LlamaCloud)
    print("\n[Step 1/5] Extracting semantic markdown from document...")
    markdown_content = await parser.parse_document(file_path)
    
    # 2. Hierarchical Chunking
    print("\n[Step 2/5] Performing Hierarchical Chunking...")
    # Assuming the document ID is the filename
    doc_id = os.path.basename(file_path)
    chunks = chunker.chunk_document(markdown_content, document_id=doc_id)
    print(f"Created {len(chunks)} contextual chunks.")

    # 3. Knowledge Graph Extraction (GraphRAG via Gemini)
    print("\n[Step 3/5] Extracting Knowledge Graph entities and relationships...")
    entities, relationships = await extractor.extract_knowledge_graph(chunks)

    # 4. Ingest to Vector Database (Qdrant)
    print("\n[Step 4/5] Ingesting Chunks to Qdrant (Vector DB)...")
    await vector_store.ingest_chunks(chunks)

    # 5. Ingest to Graph Database (Neo4j)
    print("\n[Step 5/5] Ingesting GraphRAG Triples to Neo4j (Graph DB)...")
    graph_store.ingest_knowledge_graph(entities, relationships)
    
    print(f"\n✅ Successfully processed and indexed '{doc_id}' into the RAG Pipeline.")

async def main():
    print("Initializing Agentic RAG Ingestion Pipeline...")
    
    # Initialize Core Components
    try:
        parser = MedicalDocumentParser()
        chunker = HierarchicalChunker(target_chunk_size=2000, overlap=200)
        extractor = GraphExtractor()
        
        vector_store = VectorStoreManager()
        graph_store = GraphStoreManager()
    except Exception as e:
        print(f"Failed to initialize pipeline components: {e}")
        return

    # Scan for PDFs
    pdf_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.pdf"))
    
    if not pdf_files:
        print(f"\n⚠️ No PDFs found in '{RAW_DATA_DIR}/'. Please drop your medical documents there and run this script again.")
        graph_store.close()
        return

    print(f"\nFound {len(pdf_files)} documents to process.")

    for file_path in pdf_files:
        try:
            await process_document(file_path, parser, chunker, extractor, vector_store, graph_store)
            
            # Move processed file to avoid re-processing in the future
            filename = os.path.basename(file_path)
            os.rename(file_path, os.path.join(PROCESSED_DATA_DIR, filename))
        except Exception as e:
            print(f"\n❌ Error processing {file_path}: {e}")

    # Cleanup
    graph_store.close()
    print("\n🎉 All documents have been successfully ingested! You can now start the FastAPI backend and ask questions.")

if __name__ == "__main__":
    if not os.path.exists(RAW_DATA_DIR):
        os.makedirs(RAW_DATA_DIR)
    if not os.path.exists(PROCESSED_DATA_DIR):
        os.makedirs(PROCESSED_DATA_DIR)
        
    asyncio.run(main())
