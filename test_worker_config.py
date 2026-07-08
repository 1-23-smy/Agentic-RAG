import importlib
import os
import sys
import types
import unittest
from pathlib import Path


class FakeCelery:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.conf = {}

    def task(self, *args, **kwargs):
        return lambda fn: fn


class WorkerConfigTest(unittest.TestCase):
    def setUp(self):
        self.original_redis_url = os.environ.get("REDIS_URL")
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
        if self.original_redis_url is None:
            os.environ.pop("REDIS_URL", None)
        else:
            os.environ["REDIS_URL"] = self.original_redis_url

    def test_worker_adds_project_root_to_import_path(self):
        worker = importlib.import_module("worker")

        self.assertEqual(worker.PROJECT_ROOT, Path(worker.__file__).resolve().parent)
        self.assertIn(str(worker.PROJECT_ROOT), sys.path)

    def test_worker_uses_default_redis_url_when_env_not_set(self):
        os.environ.pop("REDIS_URL", None)

        worker = importlib.import_module("worker")

        self.assertEqual(worker.app.kwargs["broker"], "redis://localhost:6379/0")
        self.assertEqual(worker.app.kwargs["backend"], "redis://localhost:6379/0")

    def test_worker_uses_redis_url_env_var_when_set(self):
        os.environ["REDIS_URL"] = "redis://redis:6379/0"

        worker = importlib.import_module("worker")

        self.assertEqual(worker.app.kwargs["broker"], "redis://redis:6379/0")
        self.assertEqual(worker.app.kwargs["backend"], "redis://redis:6379/0")


if __name__ == "__main__":
    unittest.main()
