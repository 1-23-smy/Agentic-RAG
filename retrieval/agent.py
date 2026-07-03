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
