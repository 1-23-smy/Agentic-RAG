from typing import Any, Dict, List


def _pluralize(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


class TraceCollector:
    """Accumulates the agent's reasoning steps and structured retrieval
    results for a single `aquery` call. A fresh instance is created per
    request (see UniversalRAGAgent.aquery) so concurrent requests never
    share state."""

    def __init__(self) -> None:
        self.steps: List[Dict[str, Any]] = []
        self.sources: List[Dict[str, Any]] = []
        self.graph_triples: List[Dict[str, Any]] = []

    def add_vector_step(self, query: str, sources: List[Dict[str, Any]]) -> None:
        self.steps.append(
            {
                "mode": "vector",
                "query": query,
                "detail": f"Retrieved {_pluralize(len(sources), 'chunk')}.",
            }
        )
        self.sources.extend(sources)

    def add_graph_step(self, entity: str, triples: List[Dict[str, Any]]) -> None:
        self.steps.append(
            {
                "mode": "graph",
                "query": entity,
                "detail": f"Traversed {_pluralize(len(triples), 'relationship')}.",
            }
        )
        self.graph_triples.extend(triples)
