from typing import List, Tuple
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import os

from models.schemas import HierarchicalChunk, ExtractedEntity, EntityRelationship

class KnowledgeGraphResponse(BaseModel):
    """Schema for the LLM to output structured Graph data"""
    entities: List[ExtractedEntity] = Field(description="List of medical entities found in the text.")
    relationships: List[EntityRelationship] = Field(description="List of relationships connecting the extracted entities.")

class GraphExtractor:
    def __init__(self, provider: str = "anthropic", model_name: str = "claude-3-5-sonnet-20240620"):
        if provider == "anthropic":
            # Anthropic is generally superior at strict structured output and complex relationship mapping
            self.llm = ChatAnthropic(
                model=model_name, 
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                temperature=0 
            )
        elif provider == "openai":
            self.llm = ChatOpenAI(
                model=model_name, 
                openai_api_key=os.environ.get("OPENAI_API_KEY"),
                temperature=0
            )
        else:
            raise ValueError("Unsupported provider. Use 'anthropic' or 'openai'")

        # Bind the LLM to strictly output our Pydantic schema
        self.structured_llm = self.llm.with_structured_output(KnowledgeGraphResponse)
        
        # Design the Graph Extraction Prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a world-class Expert Medical Data Extractor. 
            Your task is to read chunks of medical texts and extract a comprehensive Knowledge Graph.
            Identify critical entities like: Diseases, Drugs, Symptoms, Genes, Clinical Trials, and Patients.
            Then, identify strict relationships between them (e.g. 'TREATS', 'CAUSES', 'IS_SYMPTOM_OF', 'INTERACTS_WITH').
            
            Be extremely precise. Stick to the text provided. Do not hallucinate external medical knowledge."""),
            ("human", "Extract the knowledge graph from the following text chunk (ID: {chunk_id}):\n\n{text}")
        ])
        
        self.chain = self.prompt | self.structured_llm

    async def extract_knowledge_graph(self, chunks: List[HierarchicalChunk]) -> Tuple[List[ExtractedEntity], List[EntityRelationship]]:
        """
        Iterates over the hierarchical chunks and extracts the GraphRAG triples.
        """
        all_entities = []
        all_relationships = []
        
        print(f"Extracting Knowledge Graph from {len(chunks)} chunks...")
        
        for chunk in chunks:
            try:
                # We skip tables for now to avoid noisy extraction, though they could be parsed differently
                if chunk.metadata.is_table:
                    continue
                    
                response: KnowledgeGraphResponse = await self.chain.ainvoke({
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text
                })
                
                # Append the source chunk ID to all relationships for data lineage / deterministic citations
                for rel in response.relationships:
                    rel.source_chunk_id = chunk.chunk_id
                    
                all_entities.extend(response.entities)
                all_relationships.extend(response.relationships)
                
            except Exception as e:
                print(f"Failed to extract graph from chunk {chunk.chunk_id}. Error: {e}")
                
        print(f"Extraction Complete: Found {len(all_entities)} Entities and {len(all_relationships)} Relationships.")
        return all_entities, all_relationships
