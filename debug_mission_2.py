
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.graph.workflow import create_workflow, RunState
from langchain_core.messages import HumanMessage

load_dotenv()

def debug_pipeline(query: str):
    app = create_workflow().compile()
    initial_state = RunState(messages=[HumanMessage(content=query)])
    
    print(f"DEBUG: Running query: {query}")
    
    for event in app.stream(initial_state, {"recursion_limit": 15}): # Lower limit for debug
        for node_name, state_update in event.items():
            print(f"\n--- Node: {node_name} ---")
            if "current_plan" in state_update:
                print(f"Plan: {state_update['current_plan']}")
            if "messages" in state_update:
                last_msg = state_update["messages"][-1]
                content_preview = last_msg.content[:200] if hasattr(last_msg, 'content') else str(last_msg)[:200]
                print(f"Message ({type(last_msg).__name__}): {content_preview}...")

if __name__ == "__main__":
    query = "Find recent news about Apple using Google News."
    debug_pipeline(query)
