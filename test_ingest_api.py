import asyncio
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


STUBBED_MODULES = [
    "fastapi",
    "pydantic",
    "dotenv",
    "uvicorn",
    "celery",
    "celery.result",
    "retrieval",
    "retrieval.agent",
    "worker",
]
MISSING = object()


def install_main_import_stubs():
    fastapi = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class FastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda fn: fn

        def post(self, *args, **kwargs):
            return lambda fn: fn

    fastapi.FastAPI = FastAPI
    fastapi.HTTPException = HTTPException
    fastapi.UploadFile = object
    fastapi.File = lambda *args, **kwargs: None
    sys.modules["fastapi"] = fastapi

    pydantic = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    pydantic.BaseModel = BaseModel
    sys.modules["pydantic"] = pydantic

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

    uvicorn = types.ModuleType("uvicorn")
    uvicorn.run = lambda *args, **kwargs: None
    sys.modules["uvicorn"] = uvicorn

    celery = types.ModuleType("celery")
    celery_result = types.ModuleType("celery.result")
    celery_result.AsyncResult = object
    sys.modules["celery"] = celery
    sys.modules["celery.result"] = celery_result

    retrieval = types.ModuleType("retrieval")
    retrieval_agent = types.ModuleType("retrieval.agent")

    class UniversalRAGAgent:
        async def aquery(self, query):
            return f"answer: {query}"

    retrieval_agent.UniversalRAGAgent = UniversalRAGAgent
    sys.modules["retrieval"] = retrieval
    sys.modules["retrieval.agent"] = retrieval_agent

    worker = types.ModuleType("worker")
    worker.app = object()
    worker.process_pdf_task = Mock()
    worker.process_pdf_task.delay.return_value = types.SimpleNamespace(id="task-123")
    sys.modules["worker"] = worker


class FakeUploadFile:
    def __init__(self, filename, content=b"%PDF-1.4"):
        self.filename = filename
        self.file = tempfile.SpooledTemporaryFile()
        self.file.write(content)
        self.file.seek(0)


class IngestApiTest(unittest.TestCase):
    def setUp(self):
        self.original_modules = {
            name: sys.modules.get(name, MISSING)
            for name in [*STUBBED_MODULES, "main"]
        }
        install_main_import_stubs()
        sys.modules.pop("main", None)
        self.main = importlib.import_module("main")

    def tearDown(self):
        sys.modules.pop("main", None)
        for name, module in self.original_modules.items():
            if module is MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_upload_rejects_non_pdf(self):
        upload = FakeUploadFile("notes.txt")
        self.addCleanup(upload.file.close)

        with tempfile.TemporaryDirectory() as tmpdir:
            self.main.RAW_DATA_DIR = Path(tmpdir)
            with self.assertRaises(self.main.HTTPException) as ctx:
                asyncio.run(self.main.upload_pdf(upload))

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "Only PDF files can be uploaded.")

    def test_upload_saves_pdf_and_enqueues_task(self):
        upload = FakeUploadFile("Patient Report.pdf")
        self.addCleanup(upload.file.close)

        with tempfile.TemporaryDirectory() as tmpdir:
            self.main.RAW_DATA_DIR = Path(tmpdir)
            response = asyncio.run(self.main.upload_pdf(upload))

        self.assertEqual(response.task_id, "task-123")
        self.assertEqual(response.status, "queued")
        self.assertTrue(response.filename.endswith("_Patient_Report.pdf"))
        saved_path = self.main.process_pdf_task.delay.call_args.args[0]
        self.assertTrue(saved_path.endswith(response.filename))

    def test_status_endpoint_maps_success_state(self):
        result = types.SimpleNamespace(
            state="SUCCESS",
            result="Success: Patient Report.pdf",
        )

        with patch.object(self.main, "AsyncResult", return_value=result):
            response = self.main.get_ingestion_status("task-123")

        self.assertEqual(response.task_id, "task-123")
        self.assertEqual(response.status, "SUCCESS")
        self.assertEqual(
            response.message,
            "Ingestion complete. You can now ask questions about this document.",
        )

    def test_status_endpoint_maps_failure_state(self):
        result = types.SimpleNamespace(
            state="FAILURE",
            result=RuntimeError("parse failed"),
        )

        with patch.object(self.main, "AsyncResult", return_value=result):
            response = self.main.get_ingestion_status("task-123")

        self.assertEqual(response.status, "FAILURE")
        self.assertEqual(response.message, "Ingestion failed. Please check the worker logs and try again.")
        self.assertEqual(response.error, "parse failed")


if __name__ == "__main__":
    unittest.main()
