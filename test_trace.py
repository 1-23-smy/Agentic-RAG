import unittest

from retrieval.trace import TraceCollector


class TraceCollectorTest(unittest.TestCase):
    def test_add_vector_step_records_step_and_sources(self):
        trace = TraceCollector()

        trace.add_vector_step(
            query="warfarin interactions",
            sources=[
                {
                    "doc_id": "abc123_report.pdf",
                    "chapter": "Ch 3",
                    "section": "2.1",
                    "score": 0.91,
                    "snippet": "Concomitant amiodarone use requires...",
                }
            ],
        )

        self.assertEqual(len(trace.steps), 1)
        self.assertEqual(trace.steps[0]["mode"], "vector")
        self.assertEqual(trace.steps[0]["query"], "warfarin interactions")
        self.assertIn("Retrieved 1 chunk", trace.steps[0]["detail"])
        self.assertEqual(len(trace.sources), 1)
        self.assertEqual(trace.sources[0]["doc_id"], "abc123_report.pdf")

    def test_add_graph_step_records_step_and_triples(self):
        trace = TraceCollector()

        trace.add_graph_step(
            entity="Warfarin",
            triples=[
                {"source": "Warfarin", "rel": "INTERACTS_WITH", "target": "Amiodarone", "detail": None}
            ],
        )

        self.assertEqual(len(trace.steps), 1)
        self.assertEqual(trace.steps[0]["mode"], "graph")
        self.assertIn("Traversed 1 relationship", trace.steps[0]["detail"])
        self.assertEqual(len(trace.graph_triples), 1)
        self.assertEqual(trace.graph_triples[0]["target"], "Amiodarone")

    def test_pluralizes_counts_correctly(self):
        trace = TraceCollector()
        trace.add_vector_step(query="q", sources=[])
        self.assertIn("Retrieved 0 chunks", trace.steps[0]["detail"])


if __name__ == "__main__":
    unittest.main()
