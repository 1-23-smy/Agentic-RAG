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

        def add_middleware(self, *args, **kwargs):
            pass

    fastapi.FastAPI = FastAPI
    fastapi.HTTPException = HTTPException
    fastapi.UploadFile = object
    fastapi.File = lambda *args, **kwargs: None
    sys.modules["fastapi"] = fastapi

    fastapi_middleware = types.ModuleType("fastapi.middleware")
    fastapi_middleware_cors = types.ModuleType("fastapi.middleware.cors")
    fastapi_middleware_cors.CORSMiddleware = object
    fastapi.middleware = fastapi_middleware
    fastapi.middleware.cors = fastapi_middleware_cors
    sys.modules["fastapi.middleware"] = fastapi_middleware
    sys.modules["fastapi.middleware.cors"] = fastapi_middleware_cors

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

    class AgentAnswer:
        def __init__(self, answer, reasoning_steps=None, sources=None, graph_triples=None):
            self.answer = answer
            self.reasoning_steps = reasoning_steps or []
            self.sources = sources or []
            self.graph_triples = graph_triples or []

    class UniversalRAGAgent:
        async def aquery(self, query):
            return AgentAnswer(answer=f"answer: {query}")

    retrieval_agent.UniversalRAGAgent = UniversalRAGAgent
    retrieval_agent.AgentAnswer = AgentAnswer
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

    def test_chat_endpoint_returns_reasoning_trace_and_sources(self):
        self.main.agent = types.SimpleNamespace(
            aquery=lambda q: _async_result(self.main.AgentAnswer(
                answer="Warfarin interacts with amiodarone.",
                reasoning_steps=[{"mode": "vector", "query": "warfarin", "detail": "Retrieved 1 chunk."}],
                sources=[{"doc_id": "d1", "chapter": "Ch 1", "section": "1", "score": 0.9, "snippet": "..."}],
                graph_triples=[],
            ))
        )

        response = asyncio.run(self.main.chat_endpoint(self.main.ChatRequest(query="q")))

        self.assertEqual(response.answer, "Warfarin interacts with amiodarone.")
        self.assertEqual(len(response.reasoning_steps), 1)
        self.assertEqual(len(response.sources), 1)
        self.assertEqual(response.graph_triples, [])

    def test_list_documents_merges_ready_and_in_flight(self):
        self.main._ingestion_registry.clear()
        self.main._ingestion_registry["task-1"] = {"filename": "queued_doc.pdf", "status": "queued"}
        self.main.agent = types.SimpleNamespace(
            vector_manager=types.SimpleNamespace(list_document_ids=lambda: ["ready_doc.pdf"])
        )

        with patch.object(self.main, "AsyncResult", return_value=types.SimpleNamespace(state="PENDING")):
            response = self.main.list_documents()

        ids = {d.id for d in response.documents}
        self.assertIn("ready_doc.pdf", ids)
        self.assertIn("task-1", ids)
        ready = next(d for d in response.documents if d.id == "ready_doc.pdf")
        self.assertEqual(ready.status, "ready")
        queued = next(d for d in response.documents if d.id == "task-1")
        self.assertEqual(queued.status, "queued")


def _async_result(value):
    async def _coro(*args, **kwargs):
        return value
    return _coro()


if __name__ == "__main__":
    unittest.main()
