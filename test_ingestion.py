import asyncio
import os
from dotenv import load_dotenv

# Ensure environment variables are loaded for testing
load_dotenv()

from ingestion.parser import MedicalDocumentParser
from ingestion.chunker import HierarchicalChunker
from ingestion.graph_extractor import GraphExtractor

async def run_pipeline_test():
    print("--- Testing Ingestion Pipeline Components Compilation ---")
    
    # 1. Test Chunking Logic with Dummy Text
    chunker = HierarchicalChunker(target_chunk_size=500, overlap=50)
    
    dummy_markdown = """
    # Chapter 1: Cardiology
    ## Section A: Medications
    Aspirin is commonly prescribed for patients suffering from mild to severe heart-related headaches.
    
    It is crucial to monitor patient vitals continually.
    
    | Drug | Dosage | Frequency |
    |---|---|---|
    | Aspirin | 50mg | Daily |
    | Tylenol | 500mg | As needed |
    """
    
    chunks = chunker.chunk_document(dummy_markdown, document_id="doc_mock_001")
    for idx, c in enumerate(chunks):
        print(f"\nChunk {idx+1}:")
        print(f"   Level: {c.level}")
        print(f"   Chapter: {c.metadata.chapter}")
        print(f"   Section: {c.metadata.section}")
        print(f"   Is Table: {c.metadata.is_table}")
        print(f"   Text Snippet: {c.text[:50]}...")

    # 2. Test Graph Extractor Initialization
    try:
        # Assuming ANTHROPIC_API_KEY is available or at least mocked
        extractor = GraphExtractor(provider="anthropic")
        print("\nGraph Extractor successfully initialized the LangChain LLM Structured Chain.")
    except Exception as e:
        print(f"\nGraph Extractor init warning (normal if API key is blank): {e}")

if __name__ == "__main__":
    asyncio.run(run_pipeline_test())
