import asyncio
from dotenv import load_dotenv

load_dotenv()

from retrieval.agent import UniversalRAGAgent

async def test_agent_gemini():
    print("--- Testing Agentic Retrieval Component (GEMINI) ---")
    
    try:
        # Initialize Agent with Gemini
        agent = UniversalRAGAgent()
        print(f"\nUniversalRAGAgent successfully initialized with {agent.llm.__class__.__name__}")
        print(f"Loaded Tools: {[t.name for t in agent.tools]}")
        
    except Exception as e:
        print(f"\nAgent initialization failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_agent_gemini())
