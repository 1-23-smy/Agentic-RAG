import unittest
from unittest.mock import MagicMock

from retrieval.trace import TraceCollector
from retrieval.tools import VectorSearchTool, GraphSearchTool


class FakeDoc:
    def __init__(self, page_content, metadata):
        self.page_content = page_content
        self.metadata = metadata


class VectorSearchToolTest(unittest.TestCase):
    def test_run_records_sources_on_trace_and_returns_llm_text(self):
        trace = TraceCollector()
        vector_manager = MagicMock()
        vector_manager.similarity_search_with_score.return_value = [
            (
                FakeDoc(
                    "Concomitant amiodarone use requires a dose reduction.",
                    {"document_id": "abc_report.pdf", "chapter": "Ch 3", "section": "2.1"},
                ),
                0.912345,
            )
        ]

        tool = VectorSearchTool(vector_manager=vector_manager, trace=trace)
        result = tool._run(query="warfarin interactions")

        self.assertIn("abc_report.pdf", result)
        self.assertIn("Concomitant amiodarone", result)
        self.assertEqual(len(trace.sources), 1)
        self.assertEqual(trace.sources[0]["doc_id"], "abc_report.pdf")
        self.assertEqual(trace.sources[0]["score"], 0.91)
        self.assertEqual(len(trace.steps), 1)
        self.assertEqual(trace.steps[0]["mode"], "vector")

    def test_run_with_no_results_still_records_a_step(self):
        trace = TraceCollector()
        vector_manager = MagicMock()
        vector_manager.similarity_search_with_score.return_value = []

        tool = VectorSearchTool(vector_manager=vector_manager, trace=trace)
        result = tool._run(query="nonexistent")

        self.assertEqual(result, "No relevant vector documents found.")
        self.assertEqual(len(trace.steps), 1)
        self.assertEqual(trace.sources, [])


class GraphSearchToolTest(unittest.TestCase):
    def test_run_records_triples_on_trace_and_returns_llm_text(self):
        trace = TraceCollector()
        graph_manager = MagicMock()
        graph_manager.run_cypher_query.return_value = [
            {
                "Source": "Warfarin",
                "Relationship": "INTERACTS_WITH",
                "Target": "Amiodarone",
                "Detail": "Potentiates anticoagulant effect",
                "SourceChunk": "chunk-1",
            }
        ]

        tool = GraphSearchTool(graph_manager=graph_manager, trace=trace)
        result = tool._run(entity="Warfarin")

        self.assertIn("Warfarin", result)
        self.assertEqual(len(trace.graph_triples), 1)
        self.assertEqual(trace.graph_triples[0]["target"], "Amiodarone")
        self.assertEqual(len(trace.steps), 1)
        self.assertEqual(trace.steps[0]["mode"], "graph")


if __name__ == "__main__":
    unittest.main()
