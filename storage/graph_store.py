import os
import re
from neo4j import GraphDatabase
from typing import List
from models.schemas import ExtractedEntity, EntityRelationship

class GraphStoreManager:
    def __init__(self):
        self.uri = os.environ.get("NEO4J_URI")
        self.user = os.environ.get("NEO4J_USERNAME")
        self.password = os.environ.get("NEO4J_PASSWORD")
        self.database = os.environ.get("NEO4J_DATABASE", "neo4j")
        
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Neo4j connection details are missing from the environment.")

        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        self.driver.close()

    def _format_entity_label(self, entity_type: str) -> str:
        """Neo4j Labels conventionally use PascalCase with no spaces or special characters."""
        clean_type = re.sub(r'[^a-zA-Z0-9\s]', ' ', entity_type)
        return "".join(word.capitalize() for word in clean_type.split())

    def _format_relationship_type(self, relationship_type: str) -> str:
        """Neo4j Relationships conventionally use UPPER_SNAKE_CASE."""
        clean_type = re.sub(r'[^a-zA-Z0-9\s]', ' ', relationship_type)
        return re.sub(r'\s+', '_', clean_type.strip()).upper()

    def ingest_knowledge_graph(self, entities: List[ExtractedEntity], relationships: List[EntityRelationship]):
        """
        Takes the extracted GraphRAG entities and loops them into the Neo4j database natively.
        Uses UNWIND for efficient batch insertion.
        """
        print(f"Ingesting {len(entities)} Entities and {len(relationships)} Relationships into Neo4j...")
        
        with self.driver.session(database=self.database) as session:
            # 1. Merge Entities Strategy (prevents duplicates)
            for entity in entities:
                label = self._format_entity_label(entity.entity_type)
                query = f"""
                MERGE (e:{label} {{id: $name}})
                ON CREATE SET e.description = $description, e.type = $type
                ON MATCH SET e.description = COALESCE(e.description, $description)
                """
                session.run(query, name=entity.entity_name, description=entity.description, type=entity.entity_type)

            # 2. Merge Relationships Strategy
            for rel in relationships:
                rel_type = self._format_relationship_type(rel.relationship_type)
                query = f"""
                MATCH (source {{id: $source_name}})
                MATCH (target {{id: $target_name}})
                MERGE (source)-[r:{rel_type}]->(target)
                ON CREATE SET r.description = $description, r.source_chunk_id = $chunk_id
                """
                try:
                    session.run(query, 
                                source_name=rel.source_entity, 
                                target_name=rel.target_entity, 
                                description=rel.description,
                                chunk_id=rel.source_chunk_id)
                except Exception as e:
                    print(f"Warning: Could not link {rel.source_entity} and {rel.target_entity}. They may not have been created properly. Error: {e}")

        print("Neo4j Ingestion Complete.")

    def run_cypher_query(self, query: str, parameters: dict = None):
        """Helper to run raw cypher queries, useful for the Graph Search Agent Tool."""
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
