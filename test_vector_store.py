import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def install_stubs():
    # storage.vector_store imports these at module load time; stub them so
    # the test doesn't need real HF models / a running Qdrant instance.
    hf = types.ModuleType("langchain_huggingface")
    hf.HuggingFaceEmbeddings = MagicMock(return_value=MagicMock())
    sys.modules["langchain_huggingface"] = hf

    lq = types.ModuleType("langchain_qdrant")
    lq.QdrantVectorStore = MagicMock()
    sys.modules["langchain_qdrant"] = lq

    qc = types.ModuleType("qdrant_client")
    qc.QdrantClient = MagicMock()
    http = types.ModuleType("qdrant_client.http")
    http_models = types.ModuleType("qdrant_client.http.models")
    http_models.Distance = MagicMock(COSINE="Cosine")
    http_models.VectorParams = MagicMock()
    sys.modules["qdrant_client"] = qc
    sys.modules["qdrant_client.http"] = http
    sys.modules["qdrant_client.http.models"] = http_models


class VectorStoreManagerTest(unittest.TestCase):
    def setUp(self):
        install_stubs()
        sys.modules.pop("storage.vector_store", None)
        import storage.vector_store as vs_module
        self.vs_module = vs_module

    def test_similarity_search_with_score_delegates_to_qdrant_store(self):
        manager = self.vs_module.VectorStoreManager.__new__(self.vs_module.VectorStoreManager)
        manager.collection_name = "test_coll"
        manager.client = MagicMock()
        manager.embeddings = MagicMock()

        fake_store = MagicMock()
        fake_store.similarity_search_with_score.return_value = [("doc", 0.9)]

        with patch.object(self.vs_module, "QdrantVectorStore", return_value=fake_store) as ctor:
            result = manager.similarity_search_with_score("warfarin", k=4)

        ctor.assert_called_once_with(
            client=manager.client, collection_name="test_coll", embedding=manager.embeddings
        )
        fake_store.similarity_search_with_score.assert_called_once_with("warfarin", k=4)
        self.assertEqual(result, [("doc", 0.9)])

    def test_list_document_ids_dedupes_across_scroll_pages(self):
        manager = self.vs_module.VectorStoreManager.__new__(self.vs_module.VectorStoreManager)
        manager.collection_name = "test_coll"
        manager.client = MagicMock()

        page1_points = [
            types.SimpleNamespace(payload={"document_id": "a.pdf"}),
            types.SimpleNamespace(payload={"document_id": "b.pdf"}),
        ]
        page2_points = [
            types.SimpleNamespace(payload={"document_id": "a.pdf"}),
        ]
        manager.client.scroll.side_effect = [
            (page1_points, "offset-1"),
            (page2_points, None),
        ]

        result = manager.list_document_ids()

        self.assertEqual(sorted(result), ["a.pdf", "b.pdf"])
        self.assertEqual(manager.client.scroll.call_count, 2)


if __name__ == "__main__":
    unittest.main()
