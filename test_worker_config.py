import importlib
import sys
import types
import unittest
from pathlib import Path


class FakeCelery:
    def __init__(self, *args, **kwargs):
        self.conf = {}

    def task(self, *args, **kwargs):
        return lambda fn: fn


class WorkerConfigTest(unittest.TestCase):
    def setUp(self):
        self.original_modules = {
            name: sys.modules.get(name)
            for name in [
                "celery",
                "dotenv",
                "ingestion",
                "ingestion.parser",
                "ingestion.chunker",
                "ingestion.graph_extractor",
                "storage",
                "storage.vector_store",
                "storage.graph_store",
                "worker",
            ]
        }

        celery = types.ModuleType("celery")
        celery.Celery = FakeCelery
        sys.modules["celery"] = celery

        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda *args, **kwargs: None
        sys.modules["dotenv"] = dotenv

        parser = types.ModuleType("ingestion.parser")
        parser.MedicalDocumentParser = object
        chunker = types.ModuleType("ingestion.chunker")
        chunker.HierarchicalChunker = object
        graph_extractor = types.ModuleType("ingestion.graph_extractor")
        graph_extractor.GraphExtractor = object
        sys.modules["ingestion"] = types.ModuleType("ingestion")
        sys.modules["ingestion.parser"] = parser
        sys.modules["ingestion.chunker"] = chunker
        sys.modules["ingestion.graph_extractor"] = graph_extractor

        vector_store = types.ModuleType("storage.vector_store")
        vector_store.VectorStoreManager = object
        graph_store = types.ModuleType("storage.graph_store")
        graph_store.GraphStoreManager = object
        sys.modules["storage"] = types.ModuleType("storage")
        sys.modules["storage.vector_store"] = vector_store
        sys.modules["storage.graph_store"] = graph_store

        sys.modules.pop("worker", None)

    def tearDown(self):
        sys.modules.pop("worker", None)
        for name, module in self.original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_worker_adds_project_root_to_import_path(self):
        worker = importlib.import_module("worker")

        self.assertEqual(worker.PROJECT_ROOT, Path(worker.__file__).resolve().parent)
        self.assertIn(str(worker.PROJECT_ROOT), sys.path)


if __name__ == "__main__":
    unittest.main()
