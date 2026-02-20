from models.schemas import HierarchicalChunk, ChunkMetadata
from typing import List
import uuid
import re
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

class HierarchicalChunker:
    def __init__(self, target_chunk_size: int = 1000, overlap: int = 200):
        # We split primarily on Markdown headers mapped to our hierarchy
        self.headers_to_split_on = [
            ("#", "chapter"),
            ("##", "section"),
            ("###", "subsection")
        ]
        
        self.markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=self.headers_to_split_on)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=target_chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def chunk_document(self, document_text: str, document_id: str) -> List[HierarchicalChunk]:
        """
        Takes raw markdown from LlamaParse and structures it into a tree of chunks.
        """
        print("Chunking document hierarchically based on markdown headers...")
        
        # 1. Split by Headers (creates the structural metadata backbone)
        header_splits = self.markdown_splitter.split_text(document_text)
        
        hierarchical_chunks = []
        
        # 2. Split the body text under those headers recursively based on character limits
        for hs in header_splits:
            # Extract header metadata injected by MarkdownHeaderTextSplitter
            metadata = hs.metadata
            chapter = metadata.get("chapter")
            section = metadata.get("section")
            subsection = metadata.get("subsection")
            
            # Split the body text further to ensure chunks fit into embedding windows
            body_chunks = self.text_splitter.split_text(hs.page_content)
            
            for content in body_chunks:
                chunk_id = str(uuid.uuid4())
                
                # We determine if it's likely a table by looking for markdown table syntax
                is_table = bool(re.search(r"\|.*\|", content))
                
                meta = ChunkMetadata(
                    document_id=document_id,
                    chapter=chapter,
                    section=section or subsection,
                    is_table=is_table
                )
                
                chunk = HierarchicalChunk(
                    chunk_id=chunk_id,
                    level="paragraph" if not is_table else "table",
                    text=content,
                    metadata=meta
                )
                hierarchical_chunks.append(chunk)

        print(f"Created {len(hierarchical_chunks)} structured hierarchical chunks.")
        return hierarchical_chunks

    def generate_summaries(self, hierarchical_chunks: List[HierarchicalChunk]):
        """
        Bottom-up summarization (RAPTOR approach).
        Will be implemented using LangChain + LLM.
        """
        # TODO: Implement RAPTOR logic combining paragraph chunks into section summaries
        pass
