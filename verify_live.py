
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

# Ensure API key is set
from dotenv import load_dotenv
load_dotenv(override=True) # Load from .env file

if not os.environ.get("GOOGLE_API_KEY"):
    print("ERROR: GOOGLE_API_KEY not found in environment.")
    sys.exit(1)

from src.agents.curator import CuratorAgent

# 5 High Signal Links
URLS = [
    "https://arxiv.org/abs/2310.08560", # MemGPT (or similar high signal paper)
    "https://blog.google/technology/ai/gemini-pro/", # Google Blog
    "https://python.langchain.com/docs/get_started/introduction", # Framework docs
    "https://docs.polymarket.com/", # Polymarket docs
    "https://blog.langchain.dev/langgraph-multi-agent-workflows/", # LangGraph
]

def clean_db():
    db_path = PROJECT_ROOT / "data" / "content" / "content.db"
    if db_path.exists():
        print(f"Cleaning DB at {db_path}...")
        db_path.unlink()

def main():
    print(f"Running LIVE Verification on {len(URLS)} links...")
    agent = CuratorAgent(dry_run=False)
    
    results = {
        "NOTEBOOKLM_DATAMART": 0,
        "LIBRARY_ONLY": 0,
        "PLANNER_TASK": 0,
        "MONITORING": 0,
        "KNOWLEDGE_UPDATE": 0,
        "errors": 0
    }
    
    new_topics = 0
    pending_topics = 0
    
    for i, url in enumerate(URLS):
        print(f"[{i+1}/{len(URLS)}] Processing: {url}")
        try:
            envelope = agent.process({"url": url})
            data = envelope.payload
            
            if "content_entry" in data:
                entry = data["content_entry"]
                routing = data.get("routing", {})
                dest = routing.get("destination", "UNKNOWN")
                actions = routing.get("actions", [])
                
                print(f"  -> Destination: {dest}")
                print(f"  -> Actions: {actions}")
                print(f"  -> Confidence: {entry.get('deep_analysis', {}).get('confidence_score', 'N/A')}")
                print(f"  -> Summary: {entry.get('summary', 'N/A')}")
                
                if dest in results:
                    results[dest] += 1
                
                if "NOTEBOOKLM_DATAMART" in dest:
                    topic = routing.get("bundle_topic")
                    auto = routing.get("auto_created_topic", False)
                    print(f"  -> BUNDLE: {topic} (Auto: {auto})")
                    
                    if auto:
                        new_topics += 1
                        
            elif data.get("status") == "duplicate":
                 print(f"  -> DUPLICATE: {data.get('existing_id')}")
            else:
                 print(f"  -> ERROR: {data}")
                 results["errors"] += 1
                 
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")
            results["errors"] += 1
            
    print("\n--- LIVE SUMMARY ---")
    for k, v in results.items():
        print(f"{k}: {v}")
    print(f"New Topics: {new_topics}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="WARNING: Delete database (DESTRUCTIVE)")
    args = parser.parse_args()
    
    # NEVER auto-clean - require explicit flag AND confirmation
    if args.clean:
        confirm = input("WARNING: This will DELETE your content database. Type 'DELETE' to confirm: ")
        if confirm == "DELETE":
            clean_db()
        else:
            print("Clean cancelled.")
            import sys
            sys.exit(1)
    
    main()
