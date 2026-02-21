import asyncio
from typing import List, Tuple
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import os

from models.schemas import HierarchicalChunk, ExtractedEntity, EntityRelationship

class KnowledgeGraphResponse(BaseModel):
    """Schema for the LLM to output structured Graph data"""
    entities: List[ExtractedEntity] = Field(description="List of key entities, concepts, organizations, people, or technical terms found in the text.")
    relationships: List[EntityRelationship] = Field(description="List of relationships connecting the extracted entities.")

class GraphExtractor:
    def __init__(self, provider: str = "gemini", model_name: str = "gemini-3.1-pro-preview"):
        if provider == "anthropic":
            # Anthropic is generally superior at strict structured output and complex relationship mapping
            self.llm = ChatAnthropic(
                model=model_name, 
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                temperature=0 
            )
        elif provider == "gemini":
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=os.environ.get("GEMINI_API_KEY"),
                temperature=0
            )
        elif provider == "openai":
            self.llm = ChatOpenAI(
                model=model_name, 
                openai_api_key=os.environ.get("OPENAI_API_KEY"),
                temperature=0
            )
        else:
            raise ValueError("Unsupported provider. Use 'gemini', 'anthropic', or 'openai'")

        # Bind the LLM to strictly output our Pydantic schema
        self.structured_llm = self.llm.with_structured_output(KnowledgeGraphResponse)
        
        # Design the Graph Extraction Prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a world-class Expert Information Extractor. 
            Your task is to read chunks of text and extract a comprehensive Knowledge Graph.
            Identify critical entities such as: Key Concepts, People, Organizations, Locations, Technical Terms, Events, or Objects.
            Then, identify strict relationships between them (e.g. 'CREATED_BY', 'CAUSES', 'PART_OF', 'DEPENDS_ON', 'RELATES_TO').
            
            Be extremely precise. Stick strictly to the text provided. Do not hallucinate external knowledge."""),
            ("human", "Extract the knowledge graph from the following text chunk (ID: {chunk_id}):\n\n{text}")
        ])
        
        self.chain = self.prompt | self.structured_llm

    async def extract_knowledge_graph(self, chunks: List[HierarchicalChunk]) -> Tuple[List[ExtractedEntity], List[EntityRelationship]]:
        """
        Iterates over the hierarchical chunks and extracts the GraphRAG triples asynchronously.
        Uses a Semaphore to prevent exceeding LLM rate limits.
        """
        all_entities = []
        all_relationships = []
        
        print(f"Extracting Knowledge Graph from {len(chunks)} chunks concurrently...")
        
        # Limit concurrent API calls to 5 at a time to avoid rate limits (429 Too Many Requests)
        semaphore = asyncio.Semaphore(30)
        
        async def process_single_chunk(chunk, index):
            if chunk.metadata.is_table:
                return None
                
            async with semaphore:
                try:
                    response: KnowledgeGraphResponse = await self.chain.ainvoke({
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text
                    })
                    
                    # Append the source chunk ID to all relationships for deterministic citations
                    for rel in response.relationships:
                        rel.source_chunk_id = chunk.chunk_id
                        
                    if index % 10 == 0 or index == 1:
                        print(f"  -> Extracted {index}/{len(chunks)} chunks so far...")
                        
                    return response
                except Exception as e:
                    print(f"Failed to extract graph from chunk {chunk.chunk_id}. Error: {e}")
                    return None

        # Kick off all tasks concurrently
        tasks = [process_single_chunk(chunk, i) for i, chunk in enumerate(chunks, 1)]
        results = await asyncio.gather(*tasks)
        
        # Aggregate the results
        for res in results:
            if res:
                all_entities.extend(res.entities)
                all_relationships.extend(res.relationships)
        print(f"Extraction Complete: Found {len(all_entities)} Entities and {len(all_relationships)} Relationships.")
        return all_entities, all_relationships
