import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model_id: str


def get_graph_extractor_config() -> LLMConfig:
    return LLMConfig(
        provider=os.environ.get("GRAPH_EXTRACTOR_PROVIDER", "gemini"),
        model_id=os.environ.get("GRAPH_EXTRACTOR_MODEL_ID", "gemini-3.5-flash"),
    )


def get_retrieval_agent_config() -> LLMConfig:
    return LLMConfig(
        provider=os.environ.get("RAG_AGENT_PROVIDER", "gemini"),
        model_id=os.environ.get("RAG_AGENT_MODEL_ID", "gemini-2.5-flash"),
    )
