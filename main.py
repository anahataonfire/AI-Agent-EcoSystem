import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.graph.workflow import run_pipeline

def main():
    print("Welcome to the AI Agent Ecosystem 2.0")
    print("-------------------------------------")
    
    # Check for API keys
    has_key = (
        os.environ.get("OPENAI_API_KEY") or 
        os.environ.get("ANTHROPIC_API_KEY") or 
        os.environ.get("GOOGLE_API_KEY")
    )
    
    if not has_key:
        print("⚠️  No API key found in environment variables.")
        print("Please set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY.")
        # For now, we'll try to run anyway - maybe there's a default or mock setup? 
        # But based on thinker.py code, it raises RuntimeError.
        # Let's verify if the user has a .env file locally that we should load?
        # Typically good practice to try loading .env if python-dotenv is available, 
        # but I'll stick to standard env vars to avoid extra deps if not requested.

    default_query = "Summarize the latest headlines from BBC News"
    query = default_query
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    
    print(f"Running pipeline with query: '{query}'")
    print("Thinking...")
    
    try:
        final_state = run_pipeline(query)
        
        print("\n=== FINAL REPORT ===\n")
        print(final_state.get("final_report", "No report generated."))
        
        # Print run stats
        if "circuit_breaker" in final_state:
            cb = final_state["circuit_breaker"]
            print(f"\nStats: {cb.step_count} steps executed")
            
        print("\n====================\n")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
