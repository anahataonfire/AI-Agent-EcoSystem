
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from src.agents.curator import CuratorAgent
from src.content.schemas import RouteDestination, SystemAction

# 20 Real Links
URLS = [
    # Papers (Likely Deep Analysis / Datamart)
    "https://arxiv.org/abs/2310.08560", # MemGPT
    "https://arxiv.org/abs/2401.10020", # Self-Discover
    "https://lilianweng.github.io/posts/2023-06-23-agent/", # Lilian Weng Agents
    "https://arxiv.org/abs/2303.11366", # Reflexion
    "https://arxiv.org/abs/2305.10601", # Tree of Thoughts

    # Frameworks (Likely Planner or Library)
    "https://github.com/langchain-ai/langchain",
    "https://github.com/microsoft/autogen",
    "https://github.com/Significant-Gravitas/AutoGPT",
    "https://e2b.dev/blog/ai-agents-in-production",
    
    # News/Models (Likely Monitoring or Knowledge Update)
    "https://openai.com/index/gpt-4o",
    "https://blog.google/technology/ai/gemini-pro/",
    "https://anthropic.com/news/claude-3-5-sonnet",
    "https://huggingface.co/blog/llama3",
    "https://simonwillison.net/2024/Apr/19/llama-3/",
    "https://techcrunch.com/2024/05/13/openai-launches-gpt-4o/",
    "https://www.theverge.com/2024/5/14/24156683/google-io-2024-news-announcements",
    "https://deepmind.google/technologies/gemini/flash/",
    
    # Random / Other
    "https://www.sequoiacap.com/article/generative-ai-act-two/",
    "https://www.ycombinator.com/library/1k-llm-agents",
    "https://docs.python.org/3/library/ast.html", # Generic doc, likely Library Only
]

def mock_analyze(content_entry, manual_tags=None):
    """Mock analysis for offline testing of happy path."""
    # Simulate high-confidence analysis
    return {
        "summary": "This is a mock summary of the content.",
        "categories": ["agents", "architecture"],
        "relevance_score": 0.95,
        "action_items": [],
        "confidence_score": 0.95,
        "novelty_score": 5,
        "grounded_claims": [
            {"text": "Agentic systems require routing.", "evidence_id": "ev_001"},
            {"text": "Datamarts provide focused context.", "evidence_id": "ev_002"}
        ],
        "evidence_refs": ["ev_001", "ev_002"]
    }

def mock_fetch(self, url):
    """Mock content fetching."""
    from src.content.fetcher import FetchResult
    return FetchResult(
        content="# Mock Content\n\nAgentic systems are the future.",
        title="Mock Title",
        content_hash="mock-hash",
        success=True,
        url=url
    )

def run_verification(mock_mode=False):
    print(f"Running Validation on {len(URLS)} links... (Mock Mode: {mock_mode})")
    
    # In mock mode, patch CuratorAgent._analyze_content AND ContentFetcher.fetch
    if mock_mode:
        from src.content.fetcher import ContentFetcher
        ContentFetcher.fetch = mock_fetch
        CuratorAgent._analyze_content = lambda self, entry, tags: mock_analyze(entry, tags)
        
    agent = CuratorAgent(dry_run=False) # Write to store/bundles
    
    results = {
        "LIBRARY_ONLY": 0,
        "PLANNER_TASK": 0,
        "MONITORING": 0,
        "KNOWLEDGE_UPDATE": 0,
        "NOTEBOOKLM_DATAMART": 0,
        "errors": 0
    }
    
    bundles_created = set()
    
    for i, url in enumerate(URLS):
        print(f"[{i+1}/{len(URLS)}] Processing: {url}")
        try:
            # Ensure relevance score is high enough for deep analysis in mock mode
            # We can't easily inject relevance score into existing process flow without mocking _fetch_content too
            # essentially. 
            # Actually, CuratorAgent.process calls fetching then analysis. 
            # If we want to force NOTEBOOKLM_DATAMART, we need relevance >= 0.85 and categories in allowlist.
            # We must update the content entry AFTER fetch but BEFORE routing? 
            # Or just rely on the fact that some real URLs might hit.
            # But the user wants a deterministic SUCCESS path offline.
            # So we should mock fetcher too or rely on mocked _analyze to return high scores?
            # _analyze returns extraction. _fetch returns relevance.
            
            # Let's subclass or patch process for full control if mock_mode
            envelope = agent.process({"url": url})
            
            # If mock mode, we might need to manually override the randomly generated relevance score 
            # if fetcher isn't hitting. But fetcher hits real URLs.
            # If we are offline, fetcher fails. User said "offline".
            # So we typically need to mock fetcher too.
            
            data = envelope.payload

            
            if "content_entry" in data:
                entry = data["content_entry"]
                routing = data.get("routing", {})
                dest = routing.get("destination", "UNKNOWN")
                actions = routing.get("actions", [])
                
                print(f"  -> Destination: {dest}")
                print(f"  -> Actions: {actions}")
                print(f"  -> Confidence: {entry.get('deep_analysis', {}).get('confidence_score', 'N/A')}")
                
                if dest in results:
                    results[dest] += 1
                else:
                    results["errors"] += 1 # Unknown dest ??
                    
                if "NOTEBOOKLM_DATAMART" in dest:
                    topic = routing.get("bundle_topic")
                    if topic:
                        bundles_created.add(topic)
                        print(f"  -> BUNDLE: {topic}")
            elif data.get("status") == "duplicate":
                print(f"  -> DUPLICATE: {data.get('existing_id')}")
                results["errors"] += 1
            else:
                print(f"  -> ERROR: {data}")
                results["errors"] += 1
                
        except Exception as e:
            print(f"  -> EXCEPTION: {e}")
            results["errors"] += 1
            
    print("\n--- SUMMARY ---")
    for k, v in results.items():
        print(f"{k}: {v}")
    
    print(f"\nBundles touched/created: {bundles_created}")

def clean_db():
    db_path = PROJECT_ROOT / "data" / "content" / "content.db"
    if db_path.exists():
        print(f"Cleaning DB at {db_path}...")
        db_path.unlink()
    # also try old paths just in case
    db_path2 = PROJECT_ROOT / "data" / "content_store.db" 
    if db_path2.exists():
        print(f"Cleaning DB at {db_path2}...")
        db_path2.unlink()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (offline success path)")
    parser.add_argument("--clean", action="store_true", help="WARNING: Delete database before running (DESTRUCTIVE)")
    args = parser.parse_args()
    
    # NEVER auto-clean - require explicit flag AND confirmation
    if args.clean:
        confirm = input("WARNING: This will DELETE your content database. Type 'DELETE' to confirm: ")
        if confirm == "DELETE":
            clean_db()
        else:
            print("Clean cancelled.")
            sys.exit(1)
    
    run_verification(mock_mode=args.mock)
