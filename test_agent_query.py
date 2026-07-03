import asyncio
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, ANY

MISSING = object()

# Modules stubbed in install_stubs()
STUBBED_MODULES = [
    "langchain_core.tools",
    "pydantic",
    "langchain_core.messages",
    "langgraph.prebuilt",
    "langchain_anthropic",
    "langchain_openai",
    "langchain_google_genai",
    "storage.vector_store",
    "storage.graph_store",
    "config",
    "retrieval.agent",
    "retrieval.tools",
    "retrieval.trace",
]

# Pre-install stubs before any imports that might use them
def install_stubs():
    # Create mock objects
    mock_base_tool = type('BaseTool', (), {})
    mock_pydantic_base_model = type('BaseModel', (), {})

    # Stub out langchain_core.tools.BaseTool before tools.py imports it
    core_tools = types.ModuleType("langchain_core.tools")
    core_tools.BaseTool = mock_base_tool
    sys.modules["langchain_core.tools"] = core_tools

    # Stub pydantic
    pydantic_mod = types.ModuleType("pydantic")
    pydantic_mod.BaseModel = mock_pydantic_base_model
    pydantic_mod.Field = MagicMock()
    sys.modules["pydantic"] = pydantic_mod

    # Stub langchain_core.messages
    core_messages = types.ModuleType("langchain_core.messages")
    core_messages.HumanMessage = lambda content: types.SimpleNamespace(content=content)
    sys.modules["langchain_core.messages"] = core_messages

    # Stub langgraph.prebuilt
    langgraph_prebuilt = types.ModuleType("langgraph.prebuilt")
    langgraph_prebuilt.create_react_agent = MagicMock()
    sys.modules["langgraph.prebuilt"] = langgraph_prebuilt

    # Stub LLM providers
    for mod_name, attr in [
        ("langchain_anthropic", "ChatAnthropic"),
        ("langchain_openai", "ChatOpenAI"),
        ("langchain_google_genai", "ChatGoogleGenerativeAI"),
    ]:
        mod = types.ModuleType(mod_name)
        setattr(mod, attr, MagicMock())
        sys.modules[mod_name] = mod

    # Stub storage modules
    storage_vs = types.ModuleType("storage.vector_store")
    storage_vs.VectorStoreManager = MagicMock()
    sys.modules["storage.vector_store"] = storage_vs

    storage_gs = types.ModuleType("storage.graph_store")
    storage_gs.GraphStoreManager = MagicMock()
    sys.modules["storage.graph_store"] = storage_gs

    # Stub config
    config_mod = types.ModuleType("config")
    config_mod.get_retrieval_agent_config = MagicMock(
        return_value=types.SimpleNamespace(provider="gemini", model_id="gemini-2.5-flash")
    )
    sys.modules["config"] = config_mod


class AgentQueryTest(unittest.TestCase):
    def setUp(self):
        # Snapshot the current state of all modules we're about to stub
        self.original_modules = {
            name: sys.modules.get(name, MISSING)
            for name in STUBBED_MODULES
        }

        # Install stubs before importing retrieval.agent
        install_stubs()

        # Clean up any previously imported modules
        sys.modules.pop("retrieval.agent", None)
        sys.modules.pop("retrieval.tools", None)
        sys.modules.pop("retrieval.trace", None)

        # Now import the module with stubs in place
        import retrieval.agent as agent_module
        self.agent_module = agent_module

    def tearDown(self):
        # Clean up the imported module
        sys.modules.pop("retrieval.agent", None)
        sys.modules.pop("retrieval.tools", None)
        sys.modules.pop("retrieval.trace", None)

        # Restore all stubbed modules to their original state
        for name, module in self.original_modules.items():
            if module is MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

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

        async def run_concurrent():
            return await asyncio.gather(agent.aquery("q1"), agent.aquery("q2"))

        with patch.object(self.agent_module, "create_react_agent", side_effect=fake_create_react_agent):
            r1, r2 = asyncio.run(run_concurrent())

        self.assertEqual({r1.answer, r2.answer}, {"answer-1", "answer-2"})
        self.assertEqual(len(r1.reasoning_steps), 1)
        self.assertEqual(len(r2.reasoning_steps), 1)


if __name__ == "__main__":
    unittest.main()
