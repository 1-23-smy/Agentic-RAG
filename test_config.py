import os
import unittest
from unittest.mock import patch


class AppConfigTest(unittest.TestCase):
    def test_graph_extractor_config_reads_env_model_id(self):
        from config import get_graph_extractor_config

        with patch.dict(os.environ, {
            "GRAPH_EXTRACTOR_PROVIDER": "openai",
            "GRAPH_EXTRACTOR_MODEL_ID": "gpt-4.1-mini",
        }, clear=True):
            config = get_graph_extractor_config()

        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.model_id, "gpt-4.1-mini")

    def test_retrieval_agent_config_reads_env_model_id(self):
        from config import get_retrieval_agent_config

        with patch.dict(os.environ, {
            "RAG_AGENT_PROVIDER": "anthropic",
            "RAG_AGENT_MODEL_ID": "claude-3-5-sonnet-latest",
        }, clear=True):
            config = get_retrieval_agent_config()

        self.assertEqual(config.provider, "anthropic")
        self.assertEqual(config.model_id, "claude-3-5-sonnet-latest")


if __name__ == "__main__":
    unittest.main()
