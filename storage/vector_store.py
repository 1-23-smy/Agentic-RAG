import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from models.schemas import HierarchicalChunk
from typing import List

class VectorStoreManager:
    def __init__(self, collection_name: str = "medical_bge_chunks"):
        self.collection_name = collection_name
        
        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.client = QdrantClient(url=qdrant_url)
        
        # Use local, state-of-the-art open source embeddings (BAAI/bge-small-en-v1.5)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-en-v1.5",
            # Optional: Add model_kwargs={"device": "mps"} or "cpu" / "cuda" if performance profiling is needed
        )

        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """Creates the Qdrant collection if it doesn't already exist."""
        collections = self.client.get_collections().collections
        if not any(col.name == self.collection_name for col in collections):
            print(f"Creating Qdrant collection: {self.collection_name}")
            # bge-small-en-v1.5 dimension is 384
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )

    async def ingest_chunks(self, chunks: List[HierarchicalChunk]):
        """
        Embeds and stores the unified text chunks and their rich hierarchical metadata into Qdrant.
        """
        if not chunks:
            return

        print(f"Ingesting {len(chunks)} chunks into Qdrant...")
        
        texts = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "chunk_id": chunk.chunk_id,
                "parent_id": chunk.parent_id,
                "level": chunk.level,
                "document_id": chunk.metadata.document_id,
                "chapter": chunk.metadata.chapter,
                "section": chunk.metadata.section,
                "is_table": chunk.metadata.is_table,
            }
            for chunk in chunks
        ]

        # Use Langchain's Qdrant wrapper to handle batching and inserting
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
        )
        
        vector_store.add_texts(texts=texts, metadatas=metadatas)
        print("Qdrant Ingestion Complete.")

    def get_retriever(self, search_type="similarity", k=5):
        """Returns a LangChain retriever interface for the Agent to use."""
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
        )
        return vector_store.as_retriever(search_type=search_type, search_kwargs={"k": k})
