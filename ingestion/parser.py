import os
from typing import List, Optional
from llama_parse import LlamaParse
from models.schemas import ChunkMetadata, HierarchicalChunk

class MedicalDocumentParser:
    def __init__(self):
        # LlamaParse API Key must be set in the environment
        self.api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        if not self.api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY is not set in the environment.")
            
        # Initialize LlamaParse in markdown mode which preserves tables and headers well
        self.parser = LlamaParse(
            api_key=self.api_key,
            result_type="markdown",
            verbose=True,
            language="en"
        )

    async def parse_document(self, file_path: str) -> str:
        """
        Parses a massive PDF using LlamaParse to extract structured markdown.
        Markdown is critical because headers (##) denote the hierarchy (Chapters/Sections)
        and markdown tables preserve tabular relationships.
        """
        print(f"Starting LlamaParse for document: {file_path}")
        
        try:
            # LlamaParse can take time for massive documents. Ideally run this asynchronously.
            # load_data returns a list of Document objects from llama-index-core
            documents = await self.parser.aload_data(file_path)
            
            # Combine all pages into a single large markdown string
            full_markdown = "\n\n".join([doc.text for doc in documents])
            
            print(f"Successfully extracted {len(full_markdown)} characters of structured markdown.")
            return full_markdown
            
        except Exception as e:
            print(f"Error parsing document {file_path}: {e}")
            raise e
