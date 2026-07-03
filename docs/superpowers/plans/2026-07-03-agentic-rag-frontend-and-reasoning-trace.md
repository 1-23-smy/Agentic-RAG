# Agentic RAG — Reasoning-Trace Backend + Next.js Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit UI (`ui/app.py`) with a Next.js 16 + Tailwind v4 frontend styled from the "Agentic RAG" Claude Design System (project `1be284c1-1dff-42a4-beed-07d41d7c585e`), and extend the FastAPI backend so the UI's reasoning-trace timeline, inline citations, sources inspector, and sidebar document library are backed by real agent data instead of mocks.

**Architecture:** Backend: `UniversalRAGAgent.aquery` currently discards everything except the final LLM message. It's refactored to build a fresh `TraceCollector` + fresh tool instances + fresh `create_react_agent` graph per call (avoids shared mutable state across concurrent requests), so `VectorSearchTool`/`GraphSearchTool` can record structured steps/sources/triples as a side channel while still returning the same plain-text tool output the LLM already relies on. `/chat` returns `{answer, status, reasoning_steps, sources, graph_triples}`. A new `GET /documents` endpoint merges Qdrant's distinct `document_id`s (status "ready") with an in-process registry of in-flight Celery ingestion tasks (status "queued"/"ingesting"/"failed"). Frontend: a new `frontend/` Next.js App Router project, single client-rendered page, components ported 1:1 from the design system's `ui_kits/agentic-rag/*` and `components/**/*.jsx` (inline-style props converted to Tailwind v4 arbitrary-value classes referencing the design tokens verbatim, so `styles.css`'s CSS custom properties remain the single source of truth for color/type/spacing/radius/motion).

**Tech Stack:** Backend: FastAPI, LangGraph `create_react_agent`, LangChain, Qdrant (`langchain-qdrant`), Neo4j, pytest/unittest (existing style). Frontend: Next.js 16 (App Router), TypeScript, Node 24, Tailwind CSS v4, shadcn/ui (Radix + `class-variance-authority`), pnpm, `next-themes`, `react-markdown`, `sonner`, `lucide-react`.

## Global Constraints

- No streaming chat responses, no multi-file upload, no persistent/localStorage chat sessions — matches `docs/superpowers/specs/2026-07-03-nextjs-frontend-design.md`.
- Frontend talks directly to FastAPI via `fetch` using `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`); no Next.js API-route proxying.
- `frontend/` is a new top-level directory sibling to `ingestion/`, `retrieval/`, `storage/`. The existing `ui/` (Streamlit) directory is deleted once the Next.js app is verified working (Task 16).
- Design tokens (`tokens/*.css`, `styles.css` from the Claude Design project) are ported verbatim — do not invent new colors, spacing, or radii. Reference tokens via Tailwind arbitrary values, e.g. `bg-[var(--surface-card)]`.
- Two themes only: light (default token scope) and dark (`[data-theme="dark"]` scope), toggled via `next-themes`. The design system's third "minimal" theme scope is ported into `globals.css` but not wired to a UI toggle in this pass (YAGNI — not in the original spec; token file can stay for a future pass).
- No automated frontend test suite (matches original spec — YAGNI, no prior frontend tests to mirror). Verification is manual `pnpm dev` against the real backend.
- Backend changes get unit tests in the existing `unittest` + heavy-stubbing style used by `test_ingest_api.py`.
- Inline citation markers the agent already emits in prose (`[Doc ID | Chapter | Section]`) are rendered as plain markdown text via `react-markdown` — do NOT attempt to regex-parse them into `Citation` pill components inline in the answer body. The reliable, structured citation UI is the Sources panel (`sources` / `graph_triples` from the API response), which is real data. This bound is intentional: parsing free-form LLM prose into structured citation components is brittle and out of scope.

---

## Part A — Backend: structured reasoning trace, sources, and document list

### Task 1: `TraceCollector` + response schema models

**Files:**
- Create: `retrieval/trace.py`
- Modify: `models/schemas.py`
- Test: `test_trace.py`

**Interfaces:**
- Produces: `retrieval.trace.TraceCollector` with methods `add_vector_step(query: str, sources: list[dict]) -> None` and `add_graph_step(entity: str, triples: list[dict]) -> None`, and properties `steps: list[dict]`, `sources: list[dict]`, `graph_triples: list[dict]`.
- Produces: `models.schemas.ReasoningStep`, `models.schemas.VectorSourceResult`, `models.schemas.GraphTriple` pydantic models, consumed by Task 4 (`AgentAnswer`) and Task 5 (`ChatResponse`).

- [ ] **Step 1: Write the failing test**

```python
# test_trace.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_trace.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'retrieval.trace'`

- [ ] **Step 3: Write minimal implementation**

```python
# retrieval/trace.py
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
```

```python
# models/schemas.py — append to the end of the existing file
class ReasoningStep(BaseModel):
    mode: str  # "vector" | "graph"
    query: str
    detail: str


class VectorSourceResult(BaseModel):
    doc_id: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    score: float
    snippet: str


class GraphTriple(BaseModel):
    source: str
    rel: str
    target: str
    detail: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test_trace.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add retrieval/trace.py models/schemas.py test_trace.py
git commit -m "feat: add TraceCollector and reasoning-trace response schemas"
```

---

### Task 2: `VectorStoreManager` — scored search + distinct document listing

**Files:**
- Modify: `storage/vector_store.py`
- Test: `test_vector_store.py`

**Interfaces:**
- Consumes: `TraceCollector` is not used here — this task only adds retrieval primitives.
- Produces: `VectorStoreManager.similarity_search_with_score(query: str, k: int = 4) -> list[tuple[Document, float]]`, consumed by Task 3. `VectorStoreManager.list_document_ids() -> list[str]`, consumed by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# test_vector_store.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_vector_store.py -v`
Expected: FAIL — `AttributeError: type object 'VectorStoreManager' has no attribute 'similarity_search_with_score'`

- [ ] **Step 3: Write minimal implementation**

Add to `storage/vector_store.py` (after `get_retriever`):

```python
    def similarity_search_with_score(self, query: str, k: int = 4):
        """Like get_retriever(...).invoke(query) but also returns each
        chunk's similarity score, needed for the Sources panel."""
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
        )
        return vector_store.similarity_search_with_score(query, k=k)

    def list_document_ids(self) -> List[str]:
        """Returns the distinct document_id values ingested into this
        collection, used to populate the sidebar document library."""
        seen = set()
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                with_payload=["document_id"],
                limit=256,
                offset=offset,
            )
            for point in points:
                doc_id = point.payload.get("document_id")
                if doc_id:
                    seen.add(doc_id)
            if offset is None:
                break
        return sorted(seen)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test_vector_store.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add storage/vector_store.py test_vector_store.py
git commit -m "feat: add scored similarity search and distinct document listing"
```

---

### Task 3: Instrument `VectorSearchTool` and `GraphSearchTool` to record structured trace data

**Files:**
- Modify: `retrieval/tools.py`
- Test: `test_tools.py`

**Interfaces:**
- Consumes: `retrieval.trace.TraceCollector` (Task 1), `VectorStoreManager.similarity_search_with_score` (Task 2).
- Produces: `VectorSearchTool(vector_manager, trace)` and `GraphSearchTool(graph_manager, trace)` — both now take a required `trace: TraceCollector` constructor arg. Consumed by Task 4.

- [ ] **Step 1: Write the failing test**

```python
# test_tools.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_tools.py -v`
Expected: FAIL — `TypeError: VectorSearchTool.__init__() missing 1 required positional argument: 'trace'` (or `similarity_search_with_score` not called, since `_run` still uses `get_retriever`)

- [ ] **Step 3: Write minimal implementation**

Replace `retrieval/tools.py` contents:

```python
from typing import Optional, Type, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager
from retrieval.trace import TraceCollector

# --- VECTOR SEARCH TOOL ---

class VectorSearchInput(BaseModel):
    query: str = Field(description="The specific question or keyword to search for context (e.g., 'What is the theory?', or 'Overview/Introduction' for summaries).")
    search_type: str = Field(default="similarity", description="Either 'similarity' or 'mmr'")

class VectorSearchTool(BaseTool):
    name: str = "vector_search"
    description: str = "Useful for finding specific facts, OR retrieving general overviews/summaries of what the document is about."
    args_schema: Type[BaseModel] = VectorSearchInput
    vector_manager: VectorStoreManager = None
    trace: TraceCollector = None

    def __init__(self, vector_manager: VectorStoreManager, trace: TraceCollector):
        super().__init__()
        self.vector_manager = vector_manager
        self.trace = trace

    def _run(self, query: str, search_type: str = "similarity") -> str:
        try:
            results = self.vector_manager.similarity_search_with_score(query, k=4)

            if not results:
                self.trace.add_vector_step(query=query, sources=[])
                return "No relevant vector documents found."

            formatted_docs = []
            structured_sources = []
            for doc, score in results:
                doc_id = doc.metadata.get("document_id")
                chapter = doc.metadata.get("chapter")
                section = doc.metadata.get("section")
                metadata_str = f"[Doc: {doc_id} | Chapter: {chapter or 'N/A'} | Section: {section or 'N/A'}]"
                formatted_docs.append(f"{metadata_str}\n{doc.page_content}")
                structured_sources.append({
                    "doc_id": doc_id,
                    "chapter": chapter,
                    "section": section,
                    "score": round(float(score), 2),
                    "snippet": doc.page_content[:280],
                })

            self.trace.add_vector_step(query=query, sources=structured_sources)
            return "\n\n---\n\n".join(formatted_docs)
        except Exception as e:
            return f"Error executing Vector Search: {str(e)}"


# --- GRAPH SEARCH TOOL ---

class GraphSearchInput(BaseModel):
    entity: str = Field(description="The primary entity or concept to investigate (e.g., 'Albert Einstein', 'Revenue 2023', or 'Quantum Mechanics').")
    relationship_focus: Optional[str] = Field(default=None, description="Optional focus (e.g. 'CREATED', 'CAUSED').")

class GraphSearchTool(BaseTool):
    name: str = "graph_search"
    description: str = "Useful for discovering complex relationships between entities (e.g., finding connections, causes, networks, or traits)."
    args_schema: Type[BaseModel] = GraphSearchInput
    graph_manager: GraphStoreManager = None
    trace: TraceCollector = None

    def __init__(self, graph_manager: GraphStoreManager, trace: TraceCollector):
        super().__init__()
        self.graph_manager = graph_manager
        self.trace = trace

    def _run(self, entity: str, relationship_focus: Optional[str] = None) -> str:
        try:
            query = """
            MATCH (source)-[r]-(target)
            WHERE source.id =~ '(?i).*' + $entity + '.*' OR target.id =~ '(?i).*' + $entity + '.*'
            """
            if relationship_focus:
                query += " AND type(r) =~ '(?i)' + $rel_focus + '.*'"

            query += """
            RETURN source.id as Source, type(r) as Relationship, target.id as Target, r.description as Detail, r.source_chunk_id as SourceChunk
            LIMIT 15
            """

            results = self.graph_manager.run_cypher_query(
                query,
                {"entity": entity, "rel_focus": relationship_focus or ""}
            )

            if not results:
                self.trace.add_graph_step(entity=entity, triples=[])
                return f"No complex relationships found in the Knowledge Graph for entity: {entity}."

            output_lines = [f"Found {len(results)} relationships in the knowledge graph for '{entity}':"]
            structured_triples = []
            for r in results:
                line = f"[{r['Source']}] --({r['Relationship']})--> [{r['Target']}]"
                if r['Detail']:
                    line += f"\n   Context: {r['Detail']}"
                if r['SourceChunk']:
                    line += f"\n   Citation ID: {r['SourceChunk']}"
                output_lines.append(line)
                structured_triples.append({
                    "source": r["Source"],
                    "rel": r["Relationship"],
                    "target": r["Target"],
                    "detail": r["Detail"],
                })

            self.trace.add_graph_step(entity=entity, triples=structured_triples)
            return "\n".join(output_lines)
        except Exception as e:
            return f"Error executing Graph Search: {str(e)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test_tools.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add retrieval/tools.py test_tools.py
git commit -m "feat: instrument search tools to record structured reasoning trace"
```

---

### Task 4: Refactor `UniversalRAGAgent.aquery` to return structured `AgentAnswer`

**Files:**
- Modify: `retrieval/agent.py`
- Test: `test_agent_query.py`

**Interfaces:**
- Consumes: `TraceCollector` (Task 1), `VectorSearchTool`/`GraphSearchTool` with required `trace` arg (Task 3).
- Produces: `retrieval.agent.AgentAnswer` dataclass `{answer: str, reasoning_steps: list[dict], sources: list[dict], graph_triples: list[dict]}`. `UniversalRAGAgent.aquery(question: str) -> AgentAnswer`. Consumed by Task 5 (`main.py`).

Each call now builds a **fresh** `TraceCollector`, fresh tool instances, and a fresh `create_react_agent` graph (reusing the already-constructed `self.llm`, `self.vector_manager`, `self.graph_manager`). This keeps concurrent requests from ever sharing trace state — a global `agent` object is reused across FastAPI requests (see `main.py`), so per-request state must not live on shared tool instances.

- [ ] **Step 1: Write the failing test**

```python
# test_agent_query.py
import asyncio
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def install_stubs():
    langgraph_prebuilt = types.ModuleType("langgraph.prebuilt")
    langgraph_prebuilt.create_react_agent = MagicMock()
    sys.modules["langgraph.prebuilt"] = types.ModuleType("langgraph.prebuilt")
    sys.modules["langgraph.prebuilt"].create_react_agent = langgraph_prebuilt.create_react_agent

    for mod_name, attr in [
        ("langchain_anthropic", "ChatAnthropic"),
        ("langchain_openai", "ChatOpenAI"),
        ("langchain_google_genai", "ChatGoogleGenerativeAI"),
    ]:
        mod = types.ModuleType(mod_name)
        setattr(mod, attr, MagicMock())
        sys.modules[mod_name] = mod

    core_messages = types.ModuleType("langchain_core.messages")
    core_messages.HumanMessage = lambda content: types.SimpleNamespace(content=content)
    sys.modules["langchain_core.messages"] = core_messages

    storage_vs = types.ModuleType("storage.vector_store")
    storage_vs.VectorStoreManager = MagicMock()
    sys.modules["storage.vector_store"] = storage_vs

    storage_gs = types.ModuleType("storage.graph_store")
    storage_gs.GraphStoreManager = MagicMock()
    sys.modules["storage.graph_store"] = storage_gs

    config_mod = types.ModuleType("config")
    config_mod.get_retrieval_agent_config = MagicMock(
        return_value=types.SimpleNamespace(provider="gemini", model_id="gemini-2.5-flash")
    )
    sys.modules["config"] = config_mod


class AgentQueryTest(unittest.TestCase):
    def setUp(self):
        install_stubs()
        sys.modules.pop("retrieval.agent", None)
        sys.modules.pop("retrieval.tools", None)
        sys.modules.pop("retrieval.trace", None)
        import retrieval.agent as agent_module
        self.agent_module = agent_module

    def test_aquery_returns_answer_with_reasoning_steps_and_sources(self):
        agent = self.agent_module.UniversalRAGAgent.__new__(self.agent_module.UniversalRAGAgent)
        agent.llm = MagicMock()
        agent.vector_manager = MagicMock()
        agent.graph_manager = MagicMock()

        async def fake_astream(inputs, stream_mode="values"):
            yield {"messages": [types.SimpleNamespace(content="Warfarin interacts with amiodarone [DOC-1].", pretty_print=lambda: None)]}

        fake_executor = MagicMock()
        fake_executor.astream = fake_astream

        def fake_create_react_agent(llm, tools, prompt):
            # Simulate the vector tool recording a source, as the real
            # LangGraph tool-calling loop would via tool._run(...).
            tools[0].trace.add_vector_step(query="warfarin", sources=[{
                "doc_id": "d1", "chapter": "Ch 1", "section": "1", "score": 0.9, "snippet": "..."
            }])
            return fake_executor

        with patch.object(self.agent_module, "create_react_agent", side_effect=fake_create_react_agent):
            result = asyncio.run(agent.aquery("Which drugs interact with warfarin?"))

        self.assertEqual(result.answer, "Warfarin interacts with amiodarone [DOC-1].")
        self.assertEqual(len(result.reasoning_steps), 1)
        self.assertEqual(result.reasoning_steps[0]["mode"], "vector")
        self.assertEqual(len(result.sources), 1)
        self.assertEqual(result.sources[0]["doc_id"], "d1")
        self.assertEqual(result.graph_triples, [])

    def test_concurrent_queries_do_not_share_trace_state(self):
        agent = self.agent_module.UniversalRAGAgent.__new__(self.agent_module.UniversalRAGAgent)
        agent.llm = MagicMock()
        agent.vector_manager = MagicMock()
        agent.graph_manager = MagicMock()

        call_count = {"n": 0}

        def fake_create_react_agent(llm, tools, prompt):
            call_count["n"] += 1
            n = call_count["n"]

            async def fake_astream(inputs, stream_mode="values"):
                tools[0].trace.add_vector_step(query=f"q{n}", sources=[])
                yield {"messages": [types.SimpleNamespace(content=f"answer-{n}", pretty_print=lambda: None)]}

            executor = MagicMock()
            executor.astream = fake_astream
            return executor

        with patch.object(self.agent_module, "create_react_agent", side_effect=fake_create_react_agent):
            r1, r2 = asyncio.run(asyncio.gather(agent.aquery("q1"), agent.aquery("q2")))

        self.assertEqual({r1.answer, r2.answer}, {"answer-1", "answer-2"})
        self.assertEqual(len(r1.reasoning_steps), 1)
        self.assertEqual(len(r2.reasoning_steps), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_agent_query.py -v`
Expected: FAIL — `AttributeError: 'UniversalRAGAgent' object has no attribute 'aquery'` returns a plain string, not an `AgentAnswer`, and `create_react_agent` isn't called per-request

- [ ] **Step 3: Write minimal implementation**

Replace `retrieval/agent.py` contents:

```python
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager
from retrieval.tools import VectorSearchTool, GraphSearchTool
from retrieval.trace import TraceCollector
from config import get_retrieval_agent_config

AGENT_PROMPT = """You are a highly advanced Universal Research Agent. 
CRITICAL INSTRUCTION: The user has ALREADY uploaded and ingested a massive database of documents into your memory. 
NEVER ask the user to provide a document or context. NEVER say you don't have access to the document.

When the user asks ANY question, YOU MUST IMMEDIATELY use your tools to scour the database for answers:
1. vector_search: Use this to track down specific facts, definitions, or broad document summaries.
   -> Rule: If the user asks a completely general question like "What is this document about?", YOU MUST use vector_search with the query "Introduction" or "Overview".
2. graph_search: Use this if the query involves complex networks or relationships (e.g., finding connections between concepts, people, or events that might be pages apart).

Always evaluate thoughtfully if the context you received from the tools is sufficient to answer the user's question precisely and accurately. 
If not, think about what you are missing and use another tool to search again before giving your final answer.
When generating your final answer, ALWAYS cite your sources using the [Doc ID | Chapter | Section] or [Citation ID] provided by the tools to ensure zero hallucination."""


@dataclass
class AgentAnswer:
    answer: str
    reasoning_steps: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    graph_triples: List[Dict[str, Any]] = field(default_factory=list)


class UniversalRAGAgent:
    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None):
        llm_config = get_retrieval_agent_config()
        provider = provider or llm_config.provider
        model_name = model_name or llm_config.model_id

        self.vector_manager = VectorStoreManager()
        self.graph_manager = GraphStoreManager()

        if provider == "anthropic":
            self.llm = ChatAnthropic(
                model=model_name,
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                temperature=0.2
            )
        elif provider == "gemini":
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=os.environ.get("GEMINI_API_KEY"),
                temperature=0.2
            )
        else:
            self.llm = ChatOpenAI(
                model=model_name,
                openai_api_key=os.environ.get("OPENAI_API_KEY"),
                temperature=0.2
            )

    async def aquery(self, user_question: str) -> AgentAnswer:
        """
        Builds a fresh trace-aware tool/agent graph for this call and
        executes it. A fresh TraceCollector + tool instances are created
        per call (rather than reused from __init__) so that concurrent
        requests against the single shared UniversalRAGAgent instance
        never mix each other's reasoning trace / sources.
        """
        print(f"\n[Agent] Receiving Query: {user_question}")

        trace = TraceCollector()
        tools = [
            VectorSearchTool(vector_manager=self.vector_manager, trace=trace),
            GraphSearchTool(graph_manager=self.graph_manager, trace=trace),
        ]
        agent_executor = create_react_agent(self.llm, tools, prompt=AGENT_PROMPT)

        inputs = {"messages": [HumanMessage(content=user_question)]}

        final_message = ""
        async for s in agent_executor.astream(inputs, stream_mode="values"):
            message = s["messages"][-1]
            message.pretty_print()
            final_content = message.content
            if isinstance(final_content, list):
                text_parts = []
                for item in final_content:
                    if isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                    elif isinstance(item, str):
                        text_parts.append(item)
                final_message = "".join(text_parts)
            else:
                final_message = str(final_content)

        return AgentAnswer(
            answer=final_message,
            reasoning_steps=trace.steps,
            sources=trace.sources,
            graph_triples=trace.graph_triples,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test_agent_query.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add retrieval/agent.py test_agent_query.py
git commit -m "refactor: build trace-aware agent graph per query, return AgentAnswer"
```

---

### Task 5: `main.py` — CORS, structured `/chat` response, `/documents` endpoint

**Files:**
- Modify: `main.py`
- Test: `test_ingest_api.py` (extend existing file with new test cases)

**Interfaces:**
- Consumes: `retrieval.agent.AgentAnswer` (Task 4), `VectorStoreManager.list_document_ids` (Task 2), `models.schemas.ReasoningStep`/`VectorSourceResult`/`GraphTriple` (Task 1).
- Produces: `ChatResponse` now includes `reasoning_steps`, `sources`, `graph_triples`. New `GET /documents` returns `DocumentListResponse` `{documents: list[DocumentSummary]}` where `DocumentSummary = {id: str, title: str, status: str}`, consumed by the frontend Sidebar (Task 13).

- [ ] **Step 1: Write the failing test**

Add to `test_ingest_api.py` (extend `install_main_import_stubs` and add new test methods — full replacement below to keep the file consistent):

```python
# test_ingest_api.py — replace install_main_import_stubs's retrieval.agent stub and add new tests
```

Concretely, change the stub inside `install_main_import_stubs`:

```python
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
```

And add these test methods to `IngestApiTest`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_ingest_api.py -v`
Expected: FAIL — `AttributeError: module 'main' has no attribute '_ingestion_registry'` / `list_documents` / `response.reasoning_steps`

- [ ] **Step 3: Write minimal implementation**

Replace `main.py` contents:

```python
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

from retrieval.agent import UniversalRAGAgent, AgentAnswer
from worker import app as celery_app, process_pdf_task

RAW_DATA_DIR = Path("data/raw")

app = FastAPI(
    title="Universal Agentic RAG API",
    description="A highly scalable Agentic RAG system that uses Graph and Vector Search over massive documents.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    print("Initializing Universal RAG Agent backend...")
    agent = UniversalRAGAgent()
    print("Agent Initialized Successfully!")
except Exception as e:
    print(f"Failed to initialize Agent: {e}")
    agent = None

# In-process registry of in-flight ingestion tasks, keyed by Celery task_id.
# Entries are dropped once the underlying document shows up in Qdrant's
# distinct document_id listing (see list_documents below) — this keeps the
# registry from growing unbounded and avoids a second source of truth once
# a document is actually ready.
_ingestion_registry: Dict[str, dict] = {}


class ReasoningStep(BaseModel):
    mode: str
    query: str
    detail: str


class VectorSourceResult(BaseModel):
    doc_id: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    score: float
    snippet: str


class GraphTriple(BaseModel):
    source: str
    rel: str
    target: str
    detail: Optional[str] = None


class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    status: str
    reasoning_steps: List[ReasoningStep] = []
    sources: List[VectorSourceResult] = []
    graph_triples: List[GraphTriple] = []

class IngestionUploadResponse(BaseModel):
    task_id: str
    filename: str
    status: str
    message: str

class IngestionStatusResponse(BaseModel):
    task_id: str
    status: str
    message: str
    error: Optional[str] = None

class DocumentSummary(BaseModel):
    id: str
    title: str
    status: str

class DocumentListResponse(BaseModel):
    documents: List[DocumentSummary]

def _safe_pdf_filename(filename: str) -> str:
    original_name = Path(filename).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._")
    if not safe_name:
        safe_name = "uploaded.pdf"
    return f"{uuid4().hex}_{safe_name}"

@app.get("/")
async def root():
    return {"message": "Agentic RAG Backend is Live and Running!"}

@app.post("/ingest/upload", response_model=IngestionUploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files can be uploaded.")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    saved_filename = _safe_pdf_filename(filename)
    saved_path = RAW_DATA_DIR / saved_filename

    try:
        file.file.seek(0)
        with saved_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        task = process_pdf_task.delay(str(saved_path))
    except HTTPException:
        raise
    except Exception as e:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to upload PDF for ingestion: {e}") from e

    _ingestion_registry[task.id] = {"filename": saved_filename, "status": "queued"}

    return IngestionUploadResponse(
        task_id=task.id,
        filename=saved_filename,
        status="queued",
        message="PDF uploaded. Ingestion has started in the background.",
    )

@app.get("/ingest/status/{task_id}", response_model=IngestionStatusResponse)
def get_ingestion_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "SUCCESS":
        _ingestion_registry.pop(task_id, None)
        return IngestionStatusResponse(
            task_id=task_id,
            status=task.state,
            message="Ingestion complete. You can now ask questions about this document.",
        )

    if task.state == "FAILURE":
        if task_id in _ingestion_registry:
            _ingestion_registry[task_id]["status"] = "failed"
        return IngestionStatusResponse(
            task_id=task_id,
            status=task.state,
            message="Ingestion failed. Please check the worker logs and try again.",
            error=str(task.result),
        )

    if task.state == "STARTED":
        message = "Ingestion is currently running."
        if task_id in _ingestion_registry:
            _ingestion_registry[task_id]["status"] = "ingesting"
    elif task.state == "PENDING":
        message = "Ingestion job is queued and will start shortly."
    else:
        message = f"Ingestion status: {task.state}."

    return IngestionStatusResponse(
        task_id=task_id,
        status=task.state,
        message=message,
    )

@app.get("/documents", response_model=DocumentListResponse)
def list_documents():
    ready_ids = agent.vector_manager.list_document_ids() if agent else []
    ready_set = set(ready_ids)

    documents = [
        DocumentSummary(id=doc_id, title=doc_id, status="ready")
        for doc_id in ready_ids
    ]

    for task_id, entry in list(_ingestion_registry.items()):
        if entry["filename"] in ready_set:
            _ingestion_registry.pop(task_id, None)
            continue
        status = entry["status"]
        if status not in ("failed",):
            task = AsyncResult(task_id, app=celery_app)
            if task.state == "STARTED":
                status = "ingesting"
            elif task.state == "FAILURE":
                status = "failed"
        documents.append(DocumentSummary(id=task_id, title=entry["filename"], status=status))

    return DocumentListResponse(documents=documents)

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not agent:
        raise HTTPException(status_code=500, detail="Backend Agent failed to initialize. Check API keys.")

    try:
        result: AgentAnswer = await agent.aquery(request.query)

        return ChatResponse(
            answer=result.answer,
            status="success",
            reasoning_steps=result.reasoning_steps,
            sources=result.sources,
            graph_triples=result.graph_triples,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test_ingest_api.py -v`
Expected: PASS (all tests, including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add main.py test_ingest_api.py
git commit -m "feat: add CORS, structured chat response, and /documents endpoint"
```

---

## Part B — Frontend: Next.js app styled from the Claude Design System

### Task 6: Scaffold the Next.js 16 project and install dependencies

**Files:**
- Create: `frontend/` (via `create-next-app`, then dependency installs — generated files are not hand-authored, so this task is commands + expected outcomes, not literal file contents)
- Create: `frontend/.env.example`
- Modify: `.gitignore` (ensure `frontend/node_modules`, `frontend/.next`, `frontend/.env.local` are ignored — check `.gitignore` first; Next.js's own `.gitignore` template usually covers this)

- [ ] **Step 1: Scaffold the app**

Run from the repo root:

```bash
pnpm create next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias "@/*" --use-pnpm
```

Expected: `frontend/` created with `app/`, `package.json` (Next.js 16, React, Tailwind v4), `tsconfig.json`, `next.config.ts`, `.gitignore` (already ignores `node_modules`, `.next`, `.env*.local`).

- [ ] **Step 2: Initialize shadcn/ui**

```bash
cd frontend && pnpm dlx shadcn@latest init -y
```

Expected: creates `frontend/components.json`, `frontend/lib/utils.ts` (exports `cn()`), adds `tailwindcss-animate`-equivalent v4 setup to `app/globals.css`.

- [ ] **Step 3: Install remaining dependencies**

```bash
cd frontend && pnpm add next-themes react-markdown sonner lucide-react class-variance-authority
```

Expected: `frontend/package.json` dependencies include `next-themes`, `react-markdown`, `sonner`, `lucide-react`, `class-variance-authority`.

- [ ] **Step 4: Add env files**

```
# frontend/.env.example
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

```bash
cd frontend && cp .env.example .env.local
```

- [ ] **Step 5: Verify the scaffold boots**

```bash
cd frontend && pnpm dev &
sleep 3 && curl -sf http://localhost:3000 > /dev/null && echo "OK" ; kill %1
```

Expected: `OK` printed (default Next.js starter page responds).

- [ ] **Step 6: Commit**

```bash
git add frontend/.gitignore frontend/package.json frontend/pnpm-lock.yaml frontend/tsconfig.json frontend/next.config.ts frontend/components.json frontend/app frontend/lib frontend/.env.example
git commit -m "chore: scaffold Next.js 16 + Tailwind v4 + shadcn/ui frontend"
```

---

### Task 7: Port design tokens into `globals.css`

**Files:**
- Modify: `frontend/app/globals.css`

**Interfaces:**
- Produces: CSS custom properties (`--surface-page`, `--accent`, `--text-strong`, `--space-*`, `--radius-*`, `--shadow-*`, `--font-*`, etc. — the full token set from the Claude Design project's `tokens/*.css`) available globally, referenced by every component task below via Tailwind arbitrary values.

- [ ] **Step 1: Replace `frontend/app/globals.css`**

Keep whatever `@import "tailwindcss";` line shadcn's init added at the top, then append (verbatim, byte-for-byte from the Claude Design project's `tokens/fonts.css`, `tokens/colors.css`, `tokens/typography.css`, `tokens/spacing.css`, `tokens/radius.css`, `tokens/elevation.css`, `tokens/theme-minimal.css`, `tokens/motion.css`, `tokens/base.css` — already fetched into this session; reproduce their exact contents here) after the Tailwind import line. The token content is identical to what was fetched via `DesignSync.get_file` for each of those nine files in this session — copy each file's CSS body in, in that import order, each preceded by a `/* tokens/<name>.css */` comment. Do not alter selectors, values, or property names.

- [ ] **Step 2: Verify tokens resolve**

```bash
cd frontend && pnpm dev &
sleep 3
curl -s http://localhost:3000 | grep -q "Bricolage" || echo "check globals.css @import url for fonts"
kill %1
```

Add a temporary `<div style={{ background: "var(--accent)" }}>` to `app/page.tsx`, load `http://localhost:3000` in a browser, confirm the div renders cobalt blue (`#1D54F0`), then remove the temporary div.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "feat: port Agentic RAG design tokens into frontend globals.css"
```

---

### Task 8: `lib/types.ts` and `lib/api.ts` — typed API client

**Files:**
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/api.ts`

**Interfaces:**
- Consumes: backend response shapes from Task 5 (`ChatResponse`, `DocumentListResponse`, `IngestionUploadResponse`, `IngestionStatusResponse`).
- Produces: `sendChatMessage`, `uploadPdf`, `getIngestionStatus`, `listDocuments`, and the `ApiError` class, consumed by every stateful component task below (13, 14, 15).

- [ ] **Step 1: Write `frontend/lib/types.ts`**

```typescript
export type RetrievalMode = "vector" | "graph";

export interface ReasoningStep {
  mode: RetrievalMode;
  query: string;
  detail: string;
}

export interface VectorSourceResult {
  doc_id: string;
  chapter: string | null;
  section: string | null;
  score: number;
  snippet: string;
}

export interface GraphTriple {
  source: string;
  rel: string;
  target: string;
  detail: string | null;
}

export interface ChatResponse {
  answer: string;
  status: string;
  reasoning_steps: ReasoningStep[];
  sources: VectorSourceResult[];
  graph_triples: GraphTriple[];
}

export interface IngestionUploadResponse {
  task_id: string;
  filename: string;
  status: string;
  message: string;
}

export interface IngestionStatusResponse {
  task_id: string;
  status: string;
  message: string;
  error?: string;
}

export type DocumentStatus = "queued" | "ingesting" | "ready" | "failed";

export interface DocumentSummary {
  id: string;
  title: string;
  status: DocumentStatus;
}

export interface DocumentListResponse {
  documents: DocumentSummary[];
}

export type MessageRole = "user" | "assistant" | "error";

export interface ChatMessage {
  role: MessageRole;
  content: string;
  reasoningSteps?: ReasoningStep[];
  sources?: VectorSourceResult[];
  graphTriples?: GraphTriple[];
}
```

- [ ] **Step 2: Write `frontend/lib/api.ts`**

```typescript
import type {
  ChatResponse,
  DocumentListResponse,
  IngestionStatusResponse,
  IngestionUploadResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(
      "Failed to connect to the backend. Is the FastAPI server running on port 8000?"
    );
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export function sendChatMessage(query: string): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export function uploadPdf(file: File): Promise<IngestionUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<IngestionUploadResponse>("/ingest/upload", {
    method: "POST",
    body: formData,
  });
}

export function getIngestionStatus(taskId: string): Promise<IngestionStatusResponse> {
  return request<IngestionStatusResponse>(`/ingest/status/${taskId}`);
}

export function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/documents");
}
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat: add typed API client for chat, upload, status, and documents"
```

---

### Task 9: Form primitives — `Button`, `IconButton`, `Input`, `Textarea`

**Files:**
- Create: `frontend/components/ui/button.tsx`
- Create: `frontend/components/ui/icon-button.tsx`
- Create: `frontend/components/ui/input.tsx`
- Create: `frontend/components/ui/textarea.tsx`

**Interfaces:**
- Produces: `<Button variant="solid"|"soft"|"outline"|"ghost"|"danger" size="sm"|"md"|"lg" iconLeft iconRight loading fullWidth>`, `<IconButton label size="sm"|"md"|"lg" active>`, `<Input label hint error iconLeft>`, `<Textarea label hint>`. Ported 1:1 from the Claude Design project's `components/forms/{Button,IconButton,Input,Textarea}.jsx` (already fetched into this session) — same props, same visual values, converted from inline `style={{...}}` objects to Tailwind arbitrary-value className strings referencing the Task 7 tokens (e.g. `background: "var(--accent)"` → `bg-[var(--accent)]`), and from JS prop defaults to a TypeScript `interface` + `React.forwardRef`. Consumed by Tasks 12, 13, 15.

- [ ] **Step 1: Write `frontend/components/ui/button.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonVariant = "solid" | "soft" | "outline" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
  loading?: boolean;
  fullWidth?: boolean;
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-[var(--text-xs)] gap-1.5 h-[30px]",
  md: "px-3.5 py-2 text-[var(--text-sm)] gap-2 h-[38px]",
  lg: "px-[1.125rem] py-[0.6875rem] text-[var(--text-md)] gap-2 h-[46px]",
};

const variantClasses: Record<ButtonVariant, string> = {
  solid: "bg-[var(--accent)] text-[var(--text-on-accent)] border border-transparent hover:bg-[var(--accent-hover)]",
  soft: "bg-[var(--accent-soft)] text-[var(--accent-soft-text)] border border-transparent hover:bg-[color-mix(in_oklab,var(--accent-soft)_70%,var(--accent))]",
  outline: "bg-[var(--surface-card)] text-[var(--text-strong)] border border-[var(--border-default)] hover:bg-[var(--surface-sunken)] hover:border-[var(--border-strong)]",
  ghost: "bg-transparent text-[var(--text-body)] border border-transparent hover:bg-[var(--surface-sunken)]",
  danger: "bg-[var(--danger-500)] text-white border border-transparent hover:bg-[var(--danger-600)]",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = "solid",
      size = "md",
      iconLeft,
      iconRight,
      loading = false,
      fullWidth = false,
      disabled,
      className,
      type = "button",
      ...rest
    },
    ref
  ) => {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        className={cn(
          "inline-flex items-center justify-center whitespace-nowrap rounded-[var(--radius-control)] font-semibold tracking-[var(--track-snug)] transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] active:scale-[0.994] active:translate-y-[0.5px]",
          sizeClasses[size],
          variantClasses[variant],
          fullWidth && "w-full",
          isDisabled ? "cursor-not-allowed opacity-55" : "cursor-pointer",
          className
        )}
        {...rest}
      >
        {loading && (
          <span
            aria-hidden="true"
            className="h-[0.85em] w-[0.85em] animate-spin rounded-full border-2 border-current border-t-transparent"
          />
        )}
        {!loading && iconLeft}
        {children && <span>{children}</span>}
        {iconRight}
      </button>
    );
  }
);
Button.displayName = "Button";
```

- [ ] **Step 2: Write `frontend/components/ui/icon-button.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

type IconButtonSize = "sm" | "md" | "lg";

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  size?: IconButtonSize;
  label: string;
  active?: boolean;
}

const dims: Record<IconButtonSize, string> = {
  sm: "w-[30px] h-[30px]",
  md: "w-9 h-9",
  lg: "w-[42px] h-[42px]",
};

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ children, size = "md", label, active = false, disabled, className, ...rest }, ref) => (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      className={cn(
        "inline-flex items-center justify-center rounded-[var(--radius-md)] border border-transparent p-0 transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] active:scale-[0.94]",
        dims[size],
        active
          ? "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]"
          : "bg-transparent text-[var(--text-muted)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text-strong)]",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        className
      )}
      {...rest}
    >
      {children}
    </button>
  )
);
IconButton.displayName = "IconButton";
```

- [ ] **Step 3: Write `frontend/components/ui/input.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  iconLeft?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, error, iconLeft, id, className, ...rest }, ref) => {
    const fieldId = id ?? (label ? `in-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
    return (
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label htmlFor={fieldId} className="font-[var(--fw-semibold)] text-[var(--text-xs)] text-[var(--text-body)]">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {iconLeft && (
            <span aria-hidden="true" className="pointer-events-none absolute left-[0.6875rem] inline-flex text-[var(--text-faint)]">
              {iconLeft}
            </span>
          )}
          <input
            ref={ref}
            id={fieldId}
            className={cn(
              "w-full rounded-[var(--radius-control)] border bg-[var(--surface-card)] py-2 px-3 text-[var(--text-sm)] text-[var(--text-strong)] outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:border-[var(--border-strong)] focus:border-[var(--border-focus)] focus:shadow-[var(--ring)]",
              error ? "border-[var(--danger-500)]" : "border-[var(--border-default)]",
              iconLeft && "pl-9",
              className
            )}
            {...rest}
          />
        </div>
        {(hint || error) && (
          <span className={cn("text-[var(--text-xs)]", error ? "text-[var(--danger-600)]" : "text-[var(--text-muted)]")}>
            {error || hint}
          </span>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
```

- [ ] **Step 4: Write `frontend/components/ui/textarea.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, hint, rows = 3, id, className, ...rest }, ref) => {
    const fieldId = id ?? (label ? `ta-${label.replace(/\s+/g, "-").toLowerCase()}` : undefined);
    return (
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label htmlFor={fieldId} className="font-[var(--fw-semibold)] text-[var(--text-xs)] text-[var(--text-body)]">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={fieldId}
          rows={rows}
          className={cn(
            "w-full resize-y rounded-[var(--radius-control)] border border-[var(--border-default)] bg-[var(--surface-card)] py-2.5 px-3 text-[var(--text-sm)] text-[var(--text-strong)] outline-none transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] hover:border-[var(--border-strong)] focus:border-[var(--border-focus)] focus:shadow-[var(--ring)]",
            className
          )}
          {...rest}
        />
        {hint && <span className="text-[var(--text-xs)] text-[var(--text-muted)]">{hint}</span>}
      </div>
    );
  }
);
Textarea.displayName = "Textarea";
```

- [ ] **Step 5: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/ui/button.tsx frontend/components/ui/icon-button.tsx frontend/components/ui/input.tsx frontend/components/ui/textarea.tsx
git commit -m "feat: port Button, IconButton, Input, Textarea from design system"
```

---

### Task 10: Display primitives — `Badge`, `Card`, `Citation`, `RetrievalBadge`, `DocumentChip`

**Files:**
- Create: `frontend/components/ui/badge.tsx`
- Create: `frontend/components/ui/card.tsx`
- Create: `frontend/components/citation.tsx`
- Create: `frontend/components/retrieval-badge.tsx`
- Create: `frontend/components/document-chip.tsx`

**Interfaces:**
- Consumes: `frontend/lib/types.ts` (`RetrievalMode`, `DocumentStatus`) from Task 8.
- Produces: `<Badge tone size dot>`, `<Card elevation padded interactive>`, `<Citation docId chapter section marker mode onClick>`, `<RetrievalBadge mode label count size>`, `<DocumentChip title status active onClick>`. Ported 1:1 (same conversion rules as Task 9) from the design system's `components/display/{Badge,Card,Citation,RetrievalBadge,DocumentChip}.jsx`, already fetched into this session. Consumed by Tasks 12, 13, 14.

- [ ] **Step 1: Write `frontend/components/ui/badge.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

type BadgeTone = "neutral" | "accent" | "vector" | "graph" | "success" | "warning" | "danger";
type BadgeVariant = "soft" | "solid" | "outline";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  variant?: BadgeVariant;
  size?: "sm" | "md";
  dot?: boolean;
}

const toneClasses: Record<BadgeTone, Record<BadgeVariant, string>> = {
  neutral: {
    soft: "bg-[var(--ink-100)] text-[var(--ink-700)]",
    solid: "bg-[var(--ink-800)] text-white",
    outline: "bg-transparent text-[var(--text-body)] border-[var(--border-default)]",
  },
  accent: {
    soft: "bg-[var(--accent-soft)] text-[var(--accent-soft-text)]",
    solid: "bg-[var(--accent)] text-white",
    outline: "bg-transparent text-[var(--accent-soft-text)] border-[var(--signal-300)]",
  },
  vector: {
    soft: "bg-[var(--mode-vector-soft)] text-[var(--mode-vector-text)]",
    solid: "bg-[var(--vector-600)] text-white",
    outline: "bg-transparent text-[var(--mode-vector-text)] border-[var(--vector-300)]",
  },
  graph: {
    soft: "bg-[var(--mode-graph-soft)] text-[var(--mode-graph-text)]",
    solid: "bg-[var(--graph-600)] text-white",
    outline: "bg-transparent text-[var(--mode-graph-text)] border-[var(--graph-300)]",
  },
  success: {
    soft: "bg-[var(--success-50)] text-[var(--success-600)]",
    solid: "bg-[var(--success-500)] text-white",
    outline: "bg-transparent text-[var(--success-600)] border-[var(--success-500)]",
  },
  warning: {
    soft: "bg-[var(--warning-50)] text-[var(--warning-600)]",
    solid: "bg-[var(--warning-500)] text-white",
    outline: "bg-transparent text-[var(--warning-600)] border-[var(--warning-500)]",
  },
  danger: {
    soft: "bg-[var(--danger-50)] text-[var(--danger-600)]",
    solid: "bg-[var(--danger-500)] text-white",
    outline: "bg-transparent text-[var(--danger-600)] border-[var(--danger-500)]",
  },
};

export function Badge({ children, tone = "neutral", variant = "soft", size = "md", dot = false, className, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-full)] border border-transparent font-semibold tracking-[var(--track-snug)]",
        size === "sm" ? "px-[0.4375rem] py-[0.0625rem] text-[var(--text-2xs)]" : "px-2 py-[0.1875rem] text-[var(--text-xs)]",
        toneClasses[tone][variant],
        className
      )}
      {...rest}
    >
      {dot && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />}
      {children}
    </span>
  );
}
```

- [ ] **Step 2: Write `frontend/components/ui/card.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevation?: "none" | "xs" | "sm" | "md" | "lg";
  padded?: boolean;
  interactive?: boolean;
}

const shadowClasses: Record<NonNullable<CardProps["elevation"]>, string> = {
  none: "shadow-none",
  xs: "shadow-[var(--shadow-xs)]",
  sm: "shadow-[var(--shadow-sm)]",
  md: "shadow-[var(--shadow-md)]",
  lg: "shadow-[var(--shadow-lg)]",
};

export function Card({ children, elevation = "sm", padded = true, interactive = false, className, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-card)] border border-[var(--border-subtle)] bg-[var(--surface-card)]",
        shadowClasses[elevation],
        padded && "p-[var(--pad-card)]",
        interactive && "cursor-pointer transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
        className
      )}
      {...rest}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/components/citation.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface CitationProps {
  docId?: string;
  chapter?: string | null;
  section?: string | null;
  marker?: number;
  mode?: RetrievalMode;
  onClick?: () => void;
  className?: string;
}

export function Citation({ docId, chapter, section, marker, mode = "vector", onClick, className }: CitationProps) {
  const isGraph = mode === "graph";
  const parts = [docId, chapter, section].filter(Boolean) as string[];

  return (
    <span
      role={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap align-baseline font-medium text-[var(--text-2xs)] font-[var(--font-mono)] transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
        marker != null
          ? "h-[1.15rem] min-w-[1.15rem] justify-center rounded-[var(--radius-full)] px-1.5"
          : "rounded-[var(--radius-sm)] py-0.5 pl-1.5 pr-[0.4375rem]",
        isGraph
          ? "text-[var(--mode-graph-text)] bg-[var(--mode-graph-soft)] border border-[var(--graph-300)]"
          : "text-[var(--mode-vector-text)] bg-[var(--mode-vector-soft)] border border-[var(--vector-300)]",
        onClick ? "cursor-pointer hover:border-[var(--border-strong)] hover:bg-[var(--surface-sunken)]" : "cursor-default",
        className
      )}
    >
      {marker != null ? (
        <span>{marker}</span>
      ) : (
        <>
          <span aria-hidden="true" className="h-[5px] w-[5px] shrink-0 rounded-full bg-current opacity-85" />
          {parts.map((p, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="opacity-40">·</span>}
              <span>{p}</span>
            </React.Fragment>
          ))}
        </>
      )}
    </span>
  );
}
```

- [ ] **Step 4: Write `frontend/components/retrieval-badge.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface RetrievalBadgeProps {
  mode?: RetrievalMode;
  label?: string;
  count?: number;
  size?: "sm" | "md";
  className?: string;
}

export function RetrievalBadge({ mode = "vector", label, count, size = "md", className }: RetrievalBadgeProps) {
  const isGraph = mode === "graph";
  const text = label ?? (isGraph ? "Graph search" : "Vector search");
  const iconSize = size === "sm" ? 11 : 13;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-full)] border font-semibold font-[var(--font-mono)]",
        size === "sm" ? "px-2 py-0.5 text-[var(--text-2xs)]" : "px-2.5 py-1 text-[var(--text-xs)]",
        isGraph
          ? "text-[var(--mode-graph-text)] bg-[var(--mode-graph-soft)] border-[var(--graph-300)]"
          : "text-[var(--mode-vector-text)] bg-[var(--mode-vector-soft)] border-[var(--vector-300)]",
        className
      )}
    >
      {isGraph ? (
        <svg width={iconSize} height={iconSize} viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <circle cx="3.5" cy="4" r="2" fill="currentColor" />
          <circle cx="12.5" cy="5" r="2" fill="currentColor" />
          <circle cx="7.5" cy="12" r="2" fill="currentColor" />
          <path d="M4.8 5.4 6.2 10.6M9.4 6.2 5.6 11M11 6.6 8.7 10.7" stroke="currentColor" strokeWidth="1.1" />
        </svg>
      ) : (
        <svg width={iconSize} height={iconSize} viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <circle cx="3" cy="4" r="1.5" /><circle cx="8.5" cy="2.5" r="1.5" />
          <circle cx="13" cy="6" r="1.5" /><circle cx="5" cy="9.5" r="1.5" />
          <circle cx="11" cy="11.5" r="1.5" /><circle cx="7" cy="13.5" r="1.5" />
        </svg>
      )}
      <span>{text}</span>
      {count != null && <span className="opacity-70">· {count}</span>}
    </span>
  );
}
```

- [ ] **Step 5: Write `frontend/components/document-chip.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";
import type { DocumentStatus } from "@/lib/types";

export interface DocumentChipProps {
  title: string;
  status?: DocumentStatus;
  active?: boolean;
  onClick?: () => void;
  className?: string;
}

const statusConf: Record<DocumentStatus, { label: string; color: string; dot: string; pulse: boolean }> = {
  queued: { label: "Queued", color: "text-[var(--text-muted)]", dot: "bg-[var(--ink-400)]", pulse: false },
  ingesting: { label: "Ingesting", color: "text-[var(--warning-600)]", dot: "bg-[var(--warning-500)]", pulse: true },
  ready: { label: "Ready", color: "text-[var(--success-600)]", dot: "bg-[var(--success-500)]", pulse: false },
  failed: { label: "Failed", color: "text-[var(--danger-600)]", dot: "bg-[var(--danger-500)]", pulse: false },
};

export function DocumentChip({ title, status = "ready", active = false, onClick, className }: DocumentChipProps) {
  const conf = statusConf[status];
  return (
    <div
      role={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 rounded-[var(--radius-md)] border p-2.5 transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
        active ? "bg-[var(--accent-soft)] border-[var(--signal-300)]" : "bg-[var(--surface-card)] border-[var(--border-subtle)]",
        onClick && "cursor-pointer hover:border-[var(--border-strong)] hover:shadow-[var(--shadow-sm)]",
        className
      )}
    >
      <span className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-[color-mix(in_oklab,var(--danger-500)_20%,transparent)] bg-[var(--danger-50)] font-bold text-[8px] tracking-[0.04em] text-[var(--danger-600)] font-[var(--font-mono)]">
        PDF
      </span>
      <div className="min-w-0 flex-1">
        <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[var(--text-sm)] font-semibold text-[var(--text-strong)]">
          {title}
        </div>
        <div className="mt-0.5 flex items-center gap-2">
          <span className={cn("inline-flex items-center gap-1 text-[var(--text-2xs)] font-medium font-[var(--font-mono)]", conf.color)}>
            <span className={cn("h-1.5 w-1.5 rounded-full", conf.dot, conf.pulse && "animate-pulse")} />
            {conf.label}
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/ui/badge.tsx frontend/components/ui/card.tsx frontend/components/citation.tsx frontend/components/retrieval-badge.tsx frontend/components/document-chip.tsx
git commit -m "feat: port Badge, Card, Citation, RetrievalBadge, DocumentChip from design system"
```

---

### Task 11: Feedback primitives — `Spinner`, `Alert`, and `sonner` toaster wiring

**Files:**
- Create: `frontend/components/ui/spinner.tsx`
- Create: `frontend/components/ui/alert.tsx`
- Modify: `frontend/app/layout.tsx` (mount `<Toaster />` from `sonner`)

**Interfaces:**
- Produces: `<Spinner size label mode>`, `<Alert tone title onDismiss>`, and a mounted `sonner` toaster consumed by Task 15's network-error handling.

- [ ] **Step 1: Write `frontend/components/ui/spinner.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface SpinnerProps {
  size?: number;
  label?: string;
  mode?: RetrievalMode | "signal";
  className?: string;
}

const colorVar: Record<string, string> = {
  vector: "var(--vector-500)",
  graph: "var(--graph-500)",
  signal: "var(--accent)",
};

export function Spinner({ size = 18, label, mode = "signal", className }: SpinnerProps) {
  const color = colorVar[mode] ?? colorVar.signal;
  const borderWidth = Math.max(2, Math.round(size / 9));
  const ring = (
    <span
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        borderWidth,
        borderColor: `color-mix(in oklab, ${color} 24%, transparent)`,
        borderTopColor: color,
      }}
      className="inline-block shrink-0 animate-spin rounded-full border-solid"
    />
  );

  if (!label) return <span className={className}>{ring}</span>;

  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      {ring}
      <span className="text-[var(--text-sm)] font-medium text-[var(--text-muted)]">{label}</span>
    </span>
  );
}
```

- [ ] **Step 2: Write `frontend/components/ui/alert.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

type AlertTone = "info" | "success" | "warning" | "danger";

export interface AlertProps {
  tone?: AlertTone;
  title?: string;
  children?: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

const toneConf: Record<AlertTone, { bg: string; bd: string; fg: string; path: string }> = {
  info: { bg: "bg-[var(--accent-soft)]", bd: "border-[var(--signal-200)]", fg: "text-[var(--accent-soft-text)]", path: "M12 8h.01M11 12h1v4h1" },
  success: { bg: "bg-[var(--success-50)]", bd: "border-[color-mix(in_oklab,var(--success-500)_35%,transparent)]", fg: "text-[var(--success-600)]", path: "M20 6 9 17l-5-5" },
  warning: { bg: "bg-[var(--warning-50)]", bd: "border-[color-mix(in_oklab,var(--warning-500)_35%,transparent)]", fg: "text-[var(--warning-600)]", path: "M12 9v4M12 17h.01" },
  danger: { bg: "bg-[var(--danger-50)]", bd: "border-[color-mix(in_oklab,var(--danger-500)_35%,transparent)]", fg: "text-[var(--danger-600)]", path: "M15 9l-6 6M9 9l6 6" },
};

export function Alert({ tone = "info", title, children, onDismiss, className }: AlertProps) {
  const conf = toneConf[tone];
  return (
    <div role="status" className={cn("flex items-start gap-2.5 rounded-[var(--radius-md)] border p-3.5", conf.bg, conf.bd, className)}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={cn("mt-px shrink-0", conf.fg)} stroke="currentColor" aria-hidden="true">
        <circle cx="12" cy="12" r="9" opacity={tone === "success" || tone === "danger" ? 0 : 0.4} />
        <path d={conf.path} />
      </svg>
      <div className="min-w-0 flex-1">
        {title && <div className={cn("text-[var(--text-sm)] font-semibold", conf.fg)}>{title}</div>}
        {children && <div className={cn("text-[var(--text-sm)] text-[var(--text-body)]", title && "mt-0.5")}>{children}</div>}
      </div>
      {onDismiss && (
        <button onClick={onDismiss} aria-label="Dismiss" className={cn("shrink-0 rounded-[var(--radius-xs)] p-0.5", conf.fg)}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Mount the toaster**

In `frontend/app/layout.tsx`, import and render `<Toaster />` from `sonner` inside `<body>`, alongside whatever `ThemeProvider` shadcn's init scaffolded (or add one per Task 15 if not present yet — this step only needs the toaster mount point to exist).

- [ ] **Step 4: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ui/spinner.tsx frontend/components/ui/alert.tsx frontend/app/layout.tsx
git commit -m "feat: port Spinner, Alert from design system; mount sonner toaster"
```

---

### Task 12: Chat primitives — `AgentStep`, `MessageBubble`, `UploadZone`

**Files:**
- Create: `frontend/components/agent-step.tsx`
- Create: `frontend/components/message-bubble.tsx`
- Create: `frontend/components/upload-zone.tsx`

**Interfaces:**
- Consumes: `frontend/lib/types.ts` `ReasoningStep` (Task 8).
- Produces: `<AgentStep mode query detail status last>`, `<MessageBubble role sources>` (children = markdown answer or user text), `<UploadZone title hint dragging onSelect>`. Ported 1:1 from `components/chat/{AgentStep,MessageBubble,UploadZone}.jsx`. Consumed by Tasks 14, 15.

- [ ] **Step 1: Write `frontend/components/agent-step.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";
import type { RetrievalMode } from "@/lib/types";

export interface AgentStepProps {
  mode?: RetrievalMode;
  query?: string;
  detail?: string;
  status?: "done" | "running";
  last?: boolean;
}

export function AgentStep({ mode = "vector", query, detail, status = "done", last = false }: AgentStepProps) {
  const isGraph = mode === "graph";
  const accent = isGraph ? "text-[var(--mode-graph-text)]" : "text-[var(--mode-vector-text)]";
  const dotBorder = isGraph ? "border-[var(--mode-graph-text)]" : "border-[var(--mode-vector-text)]";
  const rail = isGraph ? "bg-[var(--graph-300)]" : "bg-[var(--vector-300)]";
  const running = status === "running";

  return (
    <div className="flex gap-3">
      <div className="flex shrink-0 flex-col items-center">
        <span
          className={cn(
            "mt-[3px] h-3 w-3 rounded-full border-2",
            dotBorder,
            running ? "bg-transparent animate-pulse" : isGraph ? "bg-[var(--mode-graph-text)]" : "bg-[var(--mode-vector-text)]"
          )}
        />
        {!last && <span className={cn("mt-1 min-h-[14px] w-0.5 flex-1 opacity-50", rail)} />}
      </div>
      <div className={cn("min-w-0", !last && "pb-3")}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("text-[var(--text-2xs)] font-semibold uppercase tracking-[var(--track-caps)] font-[var(--font-mono)]", accent)}>
            {isGraph ? "graph_search" : "vector_search"}
          </span>
          {query && (
            <code className="rounded-[var(--radius-xs)] bg-[var(--surface-sunken)] px-1.5 py-0.5 text-[var(--text-xs)] text-[var(--text-body)] font-[var(--font-mono)]">
              {query}
            </code>
          )}
        </div>
        {detail && <p className="mt-1 text-[var(--text-xs)] text-[var(--text-muted)]">{detail}</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/components/message-bubble.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface MessageBubbleProps {
  role: "user" | "assistant";
  children: React.ReactNode;
  sources?: React.ReactNode;
  className?: string;
}

export function MessageBubble({ role, children, sources, className }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className={cn("flex justify-end", className)}>
        <div className="max-w-[78%] rounded-[var(--radius-lg)] rounded-br-[var(--radius-xs)] border border-[var(--signal-100)] bg-[var(--accent-soft)] px-3.5 py-2.5 text-[var(--text-md)] font-medium text-[var(--accent-soft-text)]">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex gap-3", className)}>
      <div className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--ink-950)]" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="2" fill="var(--vector-300)" />
          <circle cx="8" cy="8" r="6" stroke="var(--signal-400)" strokeWidth="1.2" strokeDasharray="2 2.2" />
        </svg>
      </div>
      <div className="min-w-0 flex-1 pt-[3px]">
        <div className="text-[var(--text-md)] leading-[var(--lh-relaxed)] text-[var(--text-body)]">{children}</div>
        {sources && <div className="mt-3">{sources}</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/components/upload-zone.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface UploadZoneProps {
  title?: string;
  hint?: string;
  dragging?: boolean;
  onSelect?: () => void;
  className?: string;
}

export function UploadZone({
  title = "Drop a PDF to ingest",
  hint = "or click to browse · one PDF at a time",
  dragging = false,
  onSelect,
  className,
}: UploadZoneProps) {
  return (
    <div
      role="button"
      onClick={onSelect}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-[var(--radius-lg)] border-[1.5px] border-dashed p-9 text-center transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)] cursor-pointer",
        dragging ? "border-[var(--signal-400)] bg-[var(--accent-soft)]" : "border-[var(--border-default)] bg-[var(--surface-sunken)]",
        className
      )}
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-card)] text-[var(--accent)] shadow-[var(--shadow-xs)]" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 16V4M12 4 7 9M12 4l5 5" />
          <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
        </svg>
      </span>
      <div>
        <div className="text-[var(--text-md)] font-semibold text-[var(--text-strong)]">{title}</div>
        <div className="mt-0.5 text-[var(--text-xs)] text-[var(--text-muted)] font-[var(--font-mono)]">{hint}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/agent-step.tsx frontend/components/message-bubble.tsx frontend/components/upload-zone.tsx
git commit -m "feat: port AgentStep, MessageBubble, UploadZone from design system"
```

---

### Task 13: `Sidebar` — wordmark, new-conversation, document library wired to `GET /documents`

**Files:**
- Create: `frontend/components/wordmark.tsx`
- Create: `frontend/components/sidebar.tsx`
- Create: `frontend/hooks/use-document-list.ts`

**Interfaces:**
- Consumes: `listDocuments` (Task 8), `DocumentChip` (Task 10), `Button`/`IconButton` (Task 9).
- Produces: `useDocumentList()` hook returning `{ documents: DocumentSummary[], refresh: () => void }`, polling `GET /documents` every 4s while any document is `"queued"`/`"ingesting"`. `<Sidebar activeDocId onSelectDoc onNew onUploadClick />`. Consumed by Task 15.

- [ ] **Step 1: Write `frontend/hooks/use-document-list.ts`**

```typescript
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { listDocuments } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";

const POLL_INTERVAL_MS = 4000;

export function useDocumentList() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const { documents: docs } = await listDocuments();
      setDocuments(docs);
    } catch {
      // Sidebar polling failures are silent — the chat/upload flows
      // already surface connection errors via toasts.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      await refresh();
      if (cancelled) return;
      timeoutRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    };

    tick();

    return () => {
      cancelled = true;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [refresh]);

  return { documents, refresh };
}
```

- [ ] **Step 2: Write `frontend/components/wordmark.tsx`**

```tsx
export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
        <circle cx="16" cy="16" r="14" stroke="var(--signal-500)" strokeWidth="1.5" strokeDasharray="3 3" />
        <circle cx="16" cy="16" r="3.4" fill="var(--vector-500)" />
        <circle cx="7" cy="10" r="2.2" fill="var(--graph-500)" />
        <circle cx="25" cy="12" r="2.2" fill="var(--graph-500)" />
        <path d="M9 11l5 4M23 12l-4 3" stroke="var(--graph-300)" strokeWidth="1.1" />
      </svg>
      <span className="text-[17px] font-[var(--fw-extra)] tracking-[-0.03em] text-[var(--text-strong)] font-[var(--font-display)]">
        Agentic<span className="text-[var(--accent)]">RAG</span>
      </span>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/components/sidebar.tsx`**

```tsx
"use client";

import { Plus, Settings } from "lucide-react";
import { Wordmark } from "@/components/wordmark";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { DocumentChip } from "@/components/document-chip";
import { useDocumentList } from "@/hooks/use-document-list";

export interface SidebarProps {
  activeDocId: string | null;
  onSelectDoc: (id: string) => void;
  onNew: () => void;
  onUploadClick: () => void;
}

export function Sidebar({ activeDocId, onSelectDoc, onNew, onUploadClick }: SidebarProps) {
  const { documents } = useDocumentList();
  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <aside className="flex h-full w-[288px] shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--surface-card)]">
      <div className="flex items-center justify-between px-4 pb-3 pt-4">
        <Wordmark />
        <IconButton label="Settings"><Settings size={17} /></IconButton>
      </div>

      <div className="px-4 pb-3.5">
        <Button variant="solid" fullWidth iconLeft={<Plus size={16} />} onClick={onNew}>
          New conversation
        </Button>
      </div>

      <div className="flex items-center justify-between px-4 pb-2">
        <span className="ar-eyebrow">Documents · {readyCount} ready</span>
        <IconButton label="Upload PDF" onClick={onUploadClick}><Plus size={16} /></IconButton>
      </div>

      <div className="flex flex-1 flex-col gap-1.5 overflow-y-auto px-3 pb-3">
        {documents.map((d) => (
          <DocumentChip
            key={d.id}
            title={d.title}
            status={d.status}
            active={d.id === activeDocId}
            onClick={() => onSelectDoc(d.id)}
          />
        ))}
      </div>
    </aside>
  );
}
```

`.ar-eyebrow` is defined in `tokens/base.css` (ported in Task 7) as `font: var(--type-eyebrow); text-transform: uppercase; letter-spacing: var(--track-caps); color: var(--text-muted);` — reused verbatim as a global utility class rather than re-declared inline, matching how the design system itself defines it once in `base.css`.

- [ ] **Step 4: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/hooks/use-document-list.ts frontend/components/wordmark.tsx frontend/components/sidebar.tsx
git commit -m "feat: add Sidebar with document library polling GET /documents"
```

---

### Task 14: `ReasoningTrace` and `SourcesPanel` — wired to real `/chat` response data

**Files:**
- Create: `frontend/components/reasoning-trace.tsx`
- Create: `frontend/components/sources-panel.tsx`

**Interfaces:**
- Consumes: `ReasoningStep`, `VectorSourceResult`, `GraphTriple` (Task 8); `AgentStep`, `Citation`, `RetrievalBadge`, `Card` (Tasks 12, 10).
- Produces: `<ReasoningTrace steps running />`, `<SourcesPanel open onClose sources graphTriples />`. Consumed by Task 15.

- [ ] **Step 1: Write `frontend/components/reasoning-trace.tsx`**

```tsx
"use client";

import { useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { AgentStep } from "@/components/agent-step";
import type { ReasoningStep } from "@/lib/types";

export interface ReasoningTraceProps {
  steps: ReasoningStep[];
  running: boolean;
}

export function ReasoningTrace({ steps, running }: ReasoningTraceProps) {
  const [open, setOpen] = useState(true);

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface-card)]">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 border-none bg-transparent px-3.5 py-2.5 text-[12px] font-semibold uppercase tracking-[var(--track-caps)] text-[var(--text-body)] font-[var(--font-mono)]"
      >
        <Sparkles size={14} />
        <span>{running ? "Agent reasoning" : `Reasoning trace · ${steps.length} steps`}</span>
        <span className={cn("ml-auto transition-transform duration-[var(--dur-fast)]", open && "rotate-180")}>
          <ChevronDown size={15} />
        </span>
      </button>
      {open && (
        <div className="px-4 pb-3.5 pt-1">
          {steps.map((s, i) => (
            <AgentStep
              key={i}
              mode={s.mode}
              query={s.query}
              detail={s.detail}
              status={running && i === steps.length - 1 ? "running" : "done"}
              last={i === steps.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/components/sources-panel.tsx`**

```tsx
"use client";

import { PanelLeftClose } from "lucide-react";
import { RetrievalBadge } from "@/components/retrieval-badge";
import { Citation } from "@/components/citation";
import { Card } from "@/components/ui/card";
import type { VectorSourceResult, GraphTriple } from "@/lib/types";

export interface SourcesPanelProps {
  open: boolean;
  onClose: () => void;
  sources: VectorSourceResult[];
  graphTriples: GraphTriple[];
}

export function SourcesPanel({ open, onClose, sources, graphTriples }: SourcesPanelProps) {
  if (!open) return null;

  return (
    <aside className="flex h-full w-[340px] shrink-0 flex-col border-l border-[var(--border-subtle)] bg-[var(--surface-card)]">
      <div className="flex items-center justify-between border-b border-[var(--border-subtle)] px-[18px] py-4">
        <span className="text-[var(--text-sm)] font-semibold text-[var(--text-strong)]">Sources</span>
        <button onClick={onClose} aria-label="Close" className="border-none bg-transparent leading-none text-[var(--text-muted)]">
          <PanelLeftClose size={17} />
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-[18px] overflow-y-auto p-4">
        {sources.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <RetrievalBadge mode="vector" count={sources.length} />
            {sources.map((s, i) => (
              <Card key={i} elevation="xs" className="p-3">
                <div className="mb-1.5 flex items-center justify-between">
                  <Citation docId={s.doc_id} chapter={s.chapter} section={s.section} mode="vector" />
                  <span className="text-[11px] font-medium text-[var(--text-faint)] font-[var(--font-mono)]">{s.score}</span>
                </div>
                <p className="text-[12.5px] leading-[1.5] text-[var(--text-body)]">{s.snippet}</p>
              </Card>
            ))}
          </section>
        )}

        {graphTriples.length > 0 && (
          <section className="flex flex-col gap-2.5">
            <RetrievalBadge mode="graph" count={graphTriples.length} />
            <Card elevation="xs" className="flex flex-col gap-2 p-3">
              {graphTriples.map((g, i) => (
                <div key={i} className="flex flex-wrap items-center gap-1.5 text-[12px] text-[var(--text-body)] font-[var(--font-mono)]">
                  <span className="font-semibold text-[var(--graph-700)]">{g.source}</span>
                  <span className="text-[var(--text-faint)]">—({g.rel})→</span>
                  <span className="font-semibold text-[var(--graph-700)]">{g.target}</span>
                </div>
              ))}
            </Card>
          </section>
        )}
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Type-check**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/reasoning-trace.tsx frontend/components/sources-panel.tsx
git commit -m "feat: add ReasoningTrace and SourcesPanel wired to real chat response data"
```

---

### Task 15: `ChatApp` — top-level state, composer, empty state, upload flow, theme toggle, page composition

**Files:**
- Create: `frontend/components/empty-state.tsx`
- Create: `frontend/components/composer.tsx`
- Create: `frontend/components/theme-toggle.tsx`
- Create: `frontend/components/chat-app.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/layout.tsx` (wrap in `next-themes` `ThemeProvider` if Task 11 didn't already, `data-theme` attribute strategy)

**Interfaces:**
- Consumes: `sendChatMessage`, `uploadPdf`, `getIngestionStatus`, `ApiError` (Task 8); `Sidebar` (Task 13); `ReasoningTrace`, `SourcesPanel` (Task 14); `MessageBubble`, `UploadZone` (Task 12); `Button`, `Textarea`, `IconButton` (Task 9); `Alert`, `Spinner` (Task 11); `ChatMessage` type (Task 8).
- Produces: the fully composed `/` route.

- [ ] **Step 1: Write `frontend/components/empty-state.tsx`**

```tsx
import { UploadZone } from "@/components/upload-zone";

export interface EmptyStateProps {
  hasDocs: boolean;
  onUploadClick: () => void;
  onSuggestionClick: (text: string) => void;
}

const SUGGESTIONS = [
  "What is this document about?",
  "Summarize the key findings.",
  "Which entities are connected to the primary outcome?",
];

export function EmptyState({ hasDocs, onUploadClick, onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-[22px] p-8 text-center">
      <div className="max-w-[520px]">
        <div className="ar-eyebrow mb-3 block text-center">Universal Agentic RAG</div>
        <h1 className="text-[42px] tracking-[-0.03em] text-[var(--text-strong)] font-[var(--font-display)] font-[var(--fw-extra)]">
          Ask across every page.
        </h1>
        <p className="mt-3 text-[var(--text-md)] text-[var(--text-muted)]">
          Upload a PDF and interrogate it. The agent routes between vector and graph search to return cited, zero-hallucination answers.
        </p>
      </div>
      {!hasDocs ? (
        <div className="w-full max-w-[460px]"><UploadZone onSelect={onUploadClick} /></div>
      ) : (
        <div className="flex max-w-[560px] flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => onSuggestionClick(s)}
              className="ar-chip-interactive rounded-[var(--radius-full)] border border-[var(--border-default)] bg-[var(--surface-card)] px-3.5 py-2 text-[13px] font-medium text-[var(--text-body)] transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/components/composer.tsx`**

```tsx
"use client";

import { useEffect, useRef } from "react";
import { Paperclip, Send } from "lucide-react";
import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";

export interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onAttachClick: () => void;
  disabled?: boolean;
}

export function Composer({ value, onChange, onSend, onAttachClick, disabled = false }: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 160)}px`;
    }
  }, [value]);

  const submit = () => {
    if (value.trim() && !disabled) onSend();
  };

  const canSend = value.trim().length > 0 && !disabled;

  return (
    <div className="flex justify-center px-6 pb-5 pt-3">
      <div className="flex w-full max-w-[760px] items-end gap-2 rounded-[var(--radius-xl)] border border-[var(--border-default)] bg-[var(--surface-card)] py-2 pl-3.5 pr-2 shadow-[var(--shadow-sm)]">
        <IconButton label="Attach PDF" onClick={onAttachClick}><Paperclip size={18} /></IconButton>
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={1}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask a complex question about your documents…"
          className="max-h-40 flex-1 resize-none border-none bg-transparent py-1.5 text-[15px] text-[var(--text-strong)] outline-none"
        />
        <button
          onClick={submit}
          disabled={!canSend}
          aria-label="Send"
          className={cn(
            "flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[var(--radius-lg)] border-none text-white transition-[background-color,border-color,color,box-shadow,transform] duration-[var(--dur-fast)] ease-[var(--ease-standard)]",
            canSend ? "cursor-pointer bg-[var(--accent)]" : "cursor-default bg-[var(--ink-200)]"
          )}
        >
          <Send size={17} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/components/theme-toggle.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { IconButton } from "@/components/ui/icon-button";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="h-9 w-9" />;

  const isDark = theme === "dark";
  return (
    <IconButton label={isDark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setTheme(isDark ? "light" : "dark")}>
      {isDark ? <Sun size={17} /> : <Moon size={17} />}
    </IconButton>
  );
}
```

- [ ] **Step 4: Write `frontend/components/chat-app.tsx`**

```tsx
"use client";

import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import { FileText, Layers } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Sidebar } from "@/components/sidebar";
import { SourcesPanel } from "@/components/sources-panel";
import { ReasoningTrace } from "@/components/reasoning-trace";
import { MessageBubble } from "@/components/message-bubble";
import { Citation } from "@/components/citation";
import { EmptyState } from "@/components/empty-state";
import { Composer } from "@/components/composer";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { sendChatMessage, uploadPdf, getIngestionStatus, ApiError } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

const STATUS_POLL_INTERVAL_MS = 3000;

export function ChatApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [showSources, setShowSources] = useState(true);
  const [activeIngestionFilename, setActiveIngestionFilename] = useState<string | null>(null);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const hasChat = messages.length > 0 || isSending;
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

  const pollIngestionStatus = useCallback((taskId: string, filename: string) => {
    const poll = async () => {
      try {
        const status = await getIngestionStatus(taskId);
        if (status.status === "SUCCESS") {
          toast.success("Ingestion complete. You can now ask questions about this document.");
          setActiveIngestionFilename(null);
          return;
        }
        if (status.status === "FAILURE") {
          toast.error(status.error ?? "Ingestion failed. Please check the worker logs and try again.");
          setActiveIngestionFilename(null);
          return;
        }
        setTimeout(poll, STATUS_POLL_INTERVAL_MS);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to check ingestion status.");
        setActiveIngestionFilename(null);
      }
    };
    setActiveIngestionFilename(filename);
    setTimeout(poll, STATUS_POLL_INTERVAL_MS);
  }, []);

  const handleFileSelected = useCallback(
    async (file: File) => {
      if (activeIngestionFilename) return;
      try {
        const { task_id, filename } = await uploadPdf(file);
        pollIngestionStatus(task_id, filename);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to upload PDF.");
      }
    },
    [activeIngestionFilename, pollIngestionStatus]
  );

  const ask = useCallback(async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || isSending) return;

    setMessages((m) => [...m, { role: "user", content: trimmed }]);
    setInput("");
    setIsSending(true);

    try {
      const response = await sendChatMessage(trimmed);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: response.answer,
          reasoningSteps: response.reasoning_steps,
          sources: response.sources,
          graphTriples: response.graph_triples,
        },
      ]);
      setShowSources(true);
    } catch (err) {
      if (err instanceof ApiError && err.status == null) {
        toast.error(err.message);
      }
      setMessages((m) => [
        ...m,
        { role: "error", content: err instanceof ApiError ? err.message : "Something went wrong." },
      ]);
    } finally {
      setIsSending(false);
    }
  }, [isSending]);

  const resetChat = () => setMessages([]);

  return (
    <div className="flex h-full bg-[var(--surface-page)]">
      <Sidebar
        activeDocId={activeDocId}
        onSelectDoc={setActiveDocId}
        onNew={resetChat}
        onUploadClick={() => fileInputRef.current?.click()}
      />
      <input
        ref={fileInputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFileSelected(file);
          e.target.value = "";
        }}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--surface-card)] px-5">
          <div className="flex min-w-0 items-center gap-2">
            <FileText size={16} />
            <span className="overflow-hidden text-ellipsis whitespace-nowrap text-[14px] font-semibold text-[var(--text-strong)]">
              {activeIngestionFilename ? `Ingesting ${activeIngestionFilename}…` : "Agentic RAG"}
            </span>
          </div>
          <div className="flex items-center gap-2.5">
            <ThemeToggle />
            <Button variant="outline" size="sm" iconLeft={<Layers size={15} />} onClick={() => setShowSources((s) => !s)}>
              {showSources ? "Hide sources" : "Show sources"}
            </Button>
          </div>
        </header>

        {!hasChat ? (
          <EmptyState hasDocs={false} onUploadClick={() => fileInputRef.current?.click()} onSuggestionClick={ask} />
        ) : (
          <div className="flex-1 overflow-y-auto px-6 pb-2 pt-[26px]">
            <div className="mx-auto flex max-w-[760px] flex-col gap-[22px]">
              {messages.map((m, i) =>
                m.role === "user" ? (
                  <MessageBubble key={i} role="user">{m.content}</MessageBubble>
                ) : m.role === "error" ? (
                  <MessageBubble key={i} role="assistant">
                    <span className="text-[var(--danger-600)]">{m.content}</span>
                  </MessageBubble>
                ) : (
                  <div key={i} className="flex flex-col gap-3.5">
                    {m.reasoningSteps && m.reasoningSteps.length > 0 && (
                      <ReasoningTrace steps={m.reasoningSteps} running={false} />
                    )}
                    <MessageBubble
                      role="assistant"
                      sources={
                        m.sources && m.sources.length > 0 ? (
                          <div className="flex flex-wrap gap-1.5">
                            {m.sources.map((s, si) => (
                              <Citation key={si} docId={s.doc_id} chapter={s.chapter} section={s.section} mode="vector" />
                            ))}
                          </div>
                        ) : undefined
                      }
                    >
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    </MessageBubble>
                  </div>
                )
              )}
              {isSending && (
                <div className="flex flex-col gap-3.5">
                  <div className="pl-[42px]"><Spinner label="Synthesizing answer…" /></div>
                </div>
              )}
            </div>
          </div>
        )}

        <Composer
          value={input}
          onChange={setInput}
          onSend={() => ask(input)}
          onAttachClick={() => fileInputRef.current?.click()}
          disabled={isSending}
        />
      </main>

      <SourcesPanel
        open={showSources && hasChat && !!lastAssistant}
        onClose={() => setShowSources(false)}
        sources={lastAssistant?.sources ?? []}
        graphTriples={lastAssistant?.graphTriples ?? []}
      />
    </div>
  );
}
```

- [ ] **Step 5: Write `frontend/app/page.tsx`**

```tsx
import { ChatApp } from "@/components/chat-app";

export default function Home() {
  return <ChatApp />;
}
```

- [ ] **Step 6: Update `frontend/app/layout.tsx`**

Ensure the file wraps `children` in `next-themes`'s `ThemeProvider` with `attribute="data-theme"` (so it toggles the same `[data-theme="dark"]` CSS scope the design tokens define — not the default `class` strategy), sets `defaultTheme="light"`, and keeps the `<Toaster />` mount from Task 11, and sets `html, body { height: 100% }` (already true if `app/globals.css` includes the `tokens/base.css` body reset from Task 7) plus a `<div id="app-root" className="h-screen">{children}</div>` wrapper so `ChatApp`'s `h-full`/`h-screen` flex layout has a sized ancestor.

- [ ] **Step 7: Type-check and manual verification**

```bash
cd frontend && pnpm exec tsc --noEmit
```

Expected: no errors.

Then, with the FastAPI backend + Celery worker + Redis + Qdrant + Neo4j running (see `README.md` for startup commands) and `frontend/.env.local` pointing at it:

```bash
cd frontend && pnpm dev
```

Manually verify in a browser at `http://localhost:3000`:
1. Empty state renders with the upload zone.
2. Upload a PDF → header shows "Ingesting …" → sidebar shows a `queued`/`ingesting` `DocumentChip` → toast on completion → sidebar chip flips to `ready`.
3. Ask a question → user bubble appears → spinner while sending → assistant bubble appears with a reasoning trace above it and inline source citations below it.
4. Sources panel on the right shows the same vector chunks (with scores) and any graph triples from that answer.
5. Stop the FastAPI server, ask another question → toast "Failed to connect to the backend…" and an error-styled message bubble appear.
6. Toggle the theme button → page switches to the dark token scope.

- [ ] **Step 8: Commit**

```bash
git add frontend/components/empty-state.tsx frontend/components/composer.tsx frontend/components/theme-toggle.tsx frontend/components/chat-app.tsx frontend/app/page.tsx frontend/app/layout.tsx
git commit -m "feat: compose ChatApp with sidebar, reasoning trace, sources panel, and theme toggle"
```

---

### Task 16: Remove the Streamlit UI and update docs

**Files:**
- Delete: `ui/` (entire directory)
- Delete: `test_ui_upload.py` (tests the deleted Streamlit upload helper)
- Modify: `README.md` (replace Streamlit run instructions with `frontend/` pnpm instructions)
- Modify: `.env.example` (add `FRONTEND_ORIGIN=http://localhost:3000`, matching `main.py`'s `os.getenv("FRONTEND_ORIGIN", ...)`)

- [ ] **Step 1: Confirm nothing else imports `ui/`**

```bash
grep -rn "from ui" --include="*.py" . | grep -v ".venv"
grep -rn "import ui" --include="*.py" . | grep -v ".venv"
```

Expected: no matches outside `ui/` itself and `test_ui_upload.py`.

- [ ] **Step 2: Delete the Streamlit app and its test**

```bash
git rm -r ui/ test_ui_upload.py
```

- [ ] **Step 3: Update `.env.example`**

Add after the `NEO4J_DATABASE` line:

```
# Frontend
FRONTEND_ORIGIN=http://localhost:3000
```

- [ ] **Step 4: Update `README.md`**

Replace any `streamlit run ui/app.py` instructions with:

```bash
cd frontend
pnpm install
pnpm dev
```

and note the `NEXT_PUBLIC_API_URL` env var (defaults to `http://127.0.0.1:8000`).

- [ ] **Step 5: Run the full backend test suite**

```bash
python -m pytest test_trace.py test_vector_store.py test_tools.py test_agent_query.py test_ingest_api.py test_config.py test_worker_config.py test_storage.py test_ingestion.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add -u README.md .env.example
git commit -m "chore: remove Streamlit UI in favor of the Next.js frontend"
```

---

## Self-Review Notes

- **Spec coverage:** every requirement in `docs/superpowers/specs/2026-07-03-nextjs-frontend-design.md` (Next.js 16 + TS + Tailwind v4 + shadcn/ui, direct-to-FastAPI fetch with `NEXT_PUBLIC_API_URL`, CORS middleware, chat + upload + polling parity, network/HTTP error handling, `.env.local`/`.env.example`, deleting `ui/`) is covered by Tasks 6–16. The design-fidelity requirement (sidebar doc library, reasoning trace, sources panel, citations, vector/graph brand colors, dark theme) is covered by Tasks 7, 10, 12, 13, 14, 15, backed by real data via Tasks 1–5.
- **Known scope line:** inline citation markers inside the LLM's prose answer are NOT parsed into `Citation` pills (see Global Constraints) — only the structured Sources panel and the trailing citation row under each answer use the `Citation` component. This was a deliberate simplification, not an oversight.
- **Concurrency:** Task 4's `AgentAnswer`/fresh-graph-per-call design is the key fix that makes the reasoning trace safe under FastAPI's single shared `agent` object handling concurrent requests — flagged explicitly in that task's description and tested by `test_concurrent_queries_do_not_share_trace_state`.
