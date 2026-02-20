import os
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager

def test_storage_connections():
    print("--- Testing Database Connectors Initialization ---")
    
    # 1. Test Neo4j
    try:
        neo4j_manager = GraphStoreManager()
        print("Neo4j GraphStoreManager initialized successfully using environment variables.")
        # Test basic connection ping
        neo4j_manager.driver.verify_connectivity()
        print("Neo4j Driver verified connectivity to AuraDB!")
        neo4j_manager.close()
    except Exception as e:
        print(f"Neo4j Initialization/Connection Failed: {e}")

    # 2. Test Qdrant
    try:
        # Note: In a real run, this attempts to connect to localhost:6333
        # and also initializes the OpenAI embeddings model which expects OPENAI_API_KEY
        qdrant_manager = VectorStoreManager(collection_name="test_medscan")
        print(f"Qdrant VectorStoreManager initialized successfully and connected to {os.environ.get('QDRANT_URL')}.")
    except Exception as e:
        print(f"Qdrant Initialization Failed (Likely missing or invalid OPENAI_API_KEY for embeddings): {e}")

if __name__ == "__main__":
    test_storage_connections()
