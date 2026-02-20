import os
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from storage.vector_store import VectorStoreManager
from storage.graph_store import GraphStoreManager
from retrieval.tools import VectorSearchTool, GraphSearchTool

class MedicalRAGAgent:
    def __init__(self, provider: str = "gemini", model_name: str = "gemini-3.1-pro-preview"):
        # Initialize the underlying storage connections
        self.vector_manager = VectorStoreManager()
        self.graph_manager = GraphStoreManager()

        # Initialize the specific tools for the agent
        self.tools = [
            VectorSearchTool(vector_manager=self.vector_manager),
            GraphSearchTool(graph_manager=self.graph_manager)
        ]

        # Initialize the LLM "Brain"
        if provider == "anthropic":
            self.llm = ChatAnthropic(
                model=model_name, 
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                temperature=0.2 # Slight temperature for better synthesis
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

        # Build the LangGraph React Agent
        # The ReAct architecture intrinsically handles the "Tool-Based Retrieval" and 
        # "Self-Correction (Active Retrieval)" loops planned in the architecture!
        self.agent_executor = create_react_agent(
            self.llm,
            self.tools,
            prompt="""You are a highly advanced Medical ReAct Agent. 
            You have access to a massive 3000+ page medical database via two powerful tools:
            1. vector_search: Use this to track down specific paragraphs, facts, or drug dosages.
            2. graph_search: Use this if the query involves relationships (e.g., finding connections between diseases, drugs, or symptoms that might be pages apart).
            
            Always evaluate if the context you received is sufficient to answer the user's question. 
            If not, think about what you are missing and use another tool to search again before giving your final answer.
            When generating your final answer, ALWAYS site the [Doc ID | Chapter | Section] or [Citation ID] provided by the tools."""
        )

    async def aquery(self, user_question: str) -> str:
        """
        Executes the agent graph asynchronously given a user question.
        """
        print(f"\n[Agent] Receiving Query: {user_question}")
        inputs = {"messages": [HumanMessage(content=user_question)]}
        
        # Stream the agent's thought process
        final_message = ""
        async for s in self.agent_executor.astream(inputs, stream_mode="values"):
            message = s["messages"][-1]
            message.pretty_print()
            final_message = message.content

        return final_message
