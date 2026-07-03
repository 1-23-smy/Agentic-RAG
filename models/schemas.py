from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChunkMetadata(BaseModel):
    document_id: str
    page_number: Optional[int] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    is_table: bool = False

class HierarchicalChunk(BaseModel):
    chunk_id: str
    parent_id: Optional[str] = None
    level: str  # e.g., 'document', 'chapter', 'section', 'paragraph'
    text: str
    metadata: ChunkMetadata
    summary: Optional[str] = None  # Populated for chapters/sections

class ExtractedEntity(BaseModel):
    entity_name: str
    entity_type: str  # e.g., 'Drug', 'Disease', 'Gene', 'Patient'
    description: Optional[str] = None

class EntityRelationship(BaseModel):
    source_entity: str
    target_entity: str
    relationship_type: str  # e.g., 'TREATS', 'CAUSES', 'IS_SYMPTOM_OF'
    description: str
    source_chunk_id: str


class ReasoningStep(BaseModel):
    mode: str  # "vector" | "graph"
    query: str
    detail: str


class VectorSourceResult(BaseModel):
    doc_id: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    score: float
    snippet: str


class GraphTriple(BaseModel):
    source: str
    rel: str
    target: str
    detail: Optional[str] = None
