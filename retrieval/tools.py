from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import json
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import os

# --- VECTOR SEARCH TOOL ---

class VectorSearchInput(BaseModel):
    query: str = Field(description="The specific medical question to search for context (e.g., 'What is the dosage of Aspirin?').")
    search_type: str = Field(default="similarity", description="Either 'similarity' or 'mmr'")

class VectorSearchTool(BaseTool):
    name: str = "vector_search"
    description: str = "Useful for finding specific facts, paragraphs, or tables within the massive volume of medical documents."
    args_schema: Type[BaseModel] = VectorSearchInput
    vector_manager: VectorStoreManager = None

    def __init__(self, vector_manager: VectorStoreManager):
        super().__init__()
        self.vector_manager = vector_manager

    def _run(self, query: str, search_type: str = "similarity") -> str:
        try:
            retriever = self.vector_manager.get_retriever(search_type=search_type, k=4)
            docs = retriever.invoke(query)
            
            if not docs:
                return "No relevant vector documents found."
                
            formatted_docs = []
            for d in docs:
                # We return both the text and the metadata hierarchy so the Agent knows *where* it is
                metadata_str = f"[Doc: {d.metadata.get('document_id')} | Chapter: {d.metadata.get('chapter', 'N/A')} | Section: {d.metadata.get('section', 'N/A')}]"
                formatted_docs.append(f"{metadata_str}\n{d.page_content}")
                
            return "\n\n---\n\n".join(formatted_docs)
        except Exception as e:
            return f"Error executing Vector Search: {str(e)}"


# --- GRAPH SEARCH TOOL ---

class GraphSearchInput(BaseModel):
    entity: str = Field(description="The primary medical entity to investigate (e.g., 'Aspirin' or 'Heart Disease').")
    relationship_focus: Optional[str] = Field(default=None, description="Optional focus (e.g. 'TREATS', 'CAUSES').")

class GraphSearchTool(BaseTool):
    name: str = "graph_search"
    description: str = "Useful for discovering relationships between medical entities (e.g., finding all diseases treated by a drug, or symptoms caused by a condition)."
    args_schema: Type[BaseModel] = GraphSearchInput
    graph_manager: GraphStoreManager = None

    def __init__(self, graph_manager: GraphStoreManager):
        super().__init__()
        self.graph_manager = graph_manager

    def _run(self, entity: str, relationship_focus: Optional[str] = None) -> str:
        try:
            # We construct a Cypher query to find 1st and 2nd degree connections to the entity
            # We use a case-insensitive regex match since LLM capitalization varies
            query = """
            MATCH (source)-[r]-(target)
            WHERE source.id =~ '(?i).*' + $entity + '.*' OR target.id =~ '(?i).*' + $entity + '.*'
            """
            if relationship_focus:
                query += " AND type(r) =~ '(?i)' + $rel_focus + '.*'"

            query += """
            RETURN source.id as Source, type(r) as Relationship, target.id as Target, r.description as Detail, r.source_chunk_id as SourceChunk
            LIMIT 15
            """

            results = self.graph_manager.run_cypher_query(
                query, 
                {"entity": entity, "rel_focus": relationship_focus or ""}
            )

            if not results:
                return f"No complex relationships found in the Knowledge Graph for entity: {entity}."

            # Format the output for the LLM agent to read easily
            output_lines = [f"Found {len(results)} relationships in the knowledge graph for '{entity}':"]
            for r in results:
                line = f"[{r['Source']}] --({r['Relationship']})--> [{r['Target']}]"
                if r['Detail']:
                   line += f"\n   Context: {r['Detail']}"
                if r['SourceChunk']:
                   line += f"\n   Citation ID: {r['SourceChunk']}"
                output_lines.append(line)

            return "\n".join(output_lines)
        except Exception as e:
            return f"Error executing Graph Search: {str(e)}"
