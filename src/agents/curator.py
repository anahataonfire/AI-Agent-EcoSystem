"""
Curator Agent for content ingestion and analysis.

Implements the Smart Curator system:
- Fetches and parses URL content
- Generates summaries via LLM
- Auto-categorizes using taxonomy
- Scores relevance to codebase
- Suggests action items for improvements
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from .base import BaseAgent, ProposalEnvelope
from src.content.fetcher import ContentFetcher, FetchResult
from src.content.store import ContentStore
from src.content.schemas import (
    ContentEntry,
    ContentStatus,
    ActionItem,
    ActionType,
    generate_content_id,
)


# Load taxonomy at module level
TAXONOMY_PATH = Path(__file__).parent.parent.parent / "config" / "content_taxonomy.json"


def load_taxonomy() -> dict:
    """Load content taxonomy from config."""
    if TAXONOMY_PATH.exists():
        with open(TAXONOMY_PATH) as f:
            return json.load(f)
    return {"categories": []}


class CuratorAgent(BaseAgent):
    """
    Curator agent for content ingestion and analysis.
    
    Capabilities (from curator.skill.md):
    - fetch_url
    - extract_summary
    - auto_categorize
    - score_relevance
    - suggest_actions
    - write_content_store
    """
    
    SKILL_FILE = "curator.skill.md"
    
    def __init__(
        self, 
        run_id: str = None, 
        run_ts: str = None, 
        content_store: Optional[ContentStore] = None,
        firewall=None,
        runner_capabilities=None,
        dry_run: bool = False,
    ):
        # Allow running without full DTL context for CLI usage
        run_id = run_id or f"INGEST-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        run_ts = run_ts or datetime.now(timezone.utc).isoformat()
        
        super().__init__(run_id, run_ts, firewall=firewall, runner_capabilities=runner_capabilities)
        
        self.fetcher = ContentFetcher()
        self.store = content_store or ContentStore()
        self.taxonomy = load_taxonomy()
        self.dry_run = dry_run
    
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Process a URL for ingestion.
        
        Args:
            input_data: {
                'url': str,
                'manual_tags': list[str] (optional)
            }
        
        Returns:
            ProposalEnvelope with content entry data
        """
        url = input_data.get("url", "")
        manual_tags = input_data.get("manual_tags", [])
        
        capability_claims = []
        
        # Fetch content
        capability_claims.append("fetch_url")
        fetch_result = self.fetcher.fetch(url)
        
        if not fetch_result.success:
            return self.wrap_output(
                {"error": fetch_result.error, "url": url},
                capability_claims=capability_claims,
            )
        
        # Analyze with LLM
        capability_claims.extend([
            "extract_summary",
            "auto_categorize", 
            "score_relevance",
            "suggest_actions",
        ])
        
        analysis = self._analyze_content(fetch_result, manual_tags)
        
        # Create content entry
        entry = ContentEntry(
            id=generate_content_id(),
            url=url,
            title=fetch_result.title,
            summary=analysis["summary"],
            categories=analysis["categories"],
            relevance_score=analysis["relevance_score"],
            action_items=analysis["action_items"],
            status=ContentStatus.UNREAD,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            source_hash=fetch_result.content_hash,
            raw_content=fetch_result.content[:10000] if fetch_result.content else None,
        )
        
        # Store unless dry run
        if not self.dry_run:
            capability_claims.append("write_content_store")
            success = self.store.write(entry)
            if not success:
                # URL already exists
                existing = self.store.read_by_url(url)
                return self.wrap_output(
                    {
                        "status": "duplicate",
                        "existing_id": existing.id if existing else None,
                        "url": url,
                    },
                    capability_claims=capability_claims,
                )
        
        return self.wrap_output(
            {
                "status": "ingested",
                "content_entry": entry.to_dict(),
            },
            capability_claims=capability_claims,
        )
    
    def _analyze_content(self, fetch_result: FetchResult, manual_tags: list[str]) -> dict:
        """
        Analyze content using LLM.
        
        Returns dict with summary, categories, relevance_score, action_items.
        """
        try:
            return self._llm_analyze(fetch_result, manual_tags)
        except Exception as e:
            # Fallback to keyword-based analysis
            return self._fallback_analyze(fetch_result, manual_tags, str(e))
    
    def _llm_analyze(self, fetch_result: FetchResult, manual_tags: list[str]) -> dict:
        """Use Gemini to analyze content."""
        from google import genai
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        
        client = genai.Client(api_key=api_key)
        model_id = "gemini-2.0-flash"
        
        # Build category list for prompt
        category_ids = [c["id"] for c in self.taxonomy.get("categories", [])]
        
        prompt = f"""Analyze this content for an AI agent development codebase.

TITLE: {fetch_result.title}

CONTENT (truncated):
{fetch_result.content[:8000]}

---

Respond with ONLY valid JSON (no markdown), in this exact format:
{{
  "summary": "1-3 sentence summary of the key points",
  "categories": ["cat1", "cat2"],
  "relevance_score": 0.75,
  "action_items": [
    {{
      "type": "enhancement|correction|research|documentation|idea",
      "description": "What we could do based on this content",
      "related_files": ["src/agents/base.py"],
      "priority": 3
    }}
  ]
}}

RULES:
- Categories MUST be from: {json.dumps(category_ids)}
- Pick 1-3 most relevant categories
- relevance_score: 0.0-1.0 (how applicable to an AI agent codebase)
- action_items: 0-3 items, only if genuinely applicable
- related_files: use real file paths if you can infer them, otherwise omit
- priority: 1=high, 5=low
"""
        
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
        )
        text = response.text.strip()
        
        # Clean up response (remove markdown code blocks if present)
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        
        result = json.loads(text)
        
        # Merge manual tags
        categories = list(set(result.get("categories", []) + manual_tags))[:5]
        
        # Parse action items
        action_items = []
        for item in result.get("action_items", []):
            try:
                action_items.append(ActionItem(
                    action_type=ActionType(item["type"]),
                    description=item["description"],
                    related_files=item.get("related_files", []),
                    priority=item.get("priority", 3),
                ))
            except (KeyError, ValueError):
                continue
        
        return {
            "summary": result.get("summary", "No summary available"),
            "categories": categories,
            "relevance_score": min(1.0, max(0.0, result.get("relevance_score", 0.5))),
            "action_items": action_items,
        }
    
    def _fallback_analyze(
        self, 
        fetch_result: FetchResult, 
        manual_tags: list[str],
        error: str,
    ) -> dict:
        """Keyword-based fallback when LLM is unavailable."""
        content_lower = (fetch_result.content + fetch_result.title).lower()
        
        # Match categories by keywords
        categories = []
        for cat in self.taxonomy.get("categories", []):
            for keyword in cat.get("keywords", []):
                if keyword.lower() in content_lower:
                    if cat["id"] not in categories:
                        categories.append(cat["id"])
                    break
        
        # Add manual tags
        categories = list(set(categories + manual_tags))[:5]
        
        # Simple summary (first sentence or truncated title)
        summary = fetch_result.title
        if len(fetch_result.content) > 100:
            first_para = fetch_result.content.split("\n\n")[0]
            if len(first_para) < 300:
                summary = first_para
        
        return {
            "summary": f"{summary} [Fallback analysis: {error}]",
            "categories": categories or ["uncategorized"],
            "relevance_score": 0.5,
            "action_items": [],
        }
    
    def process_queue(self, queue_path: Path) -> list[dict]:
        """
        Process all URLs from a queue file.
        
        Args:
            queue_path: Path to queue file (one URL per line)
        
        Returns:
            List of processing results
        """
        from src.content.schemas import QueueRecord
        
        if not queue_path.exists():
            return []
        
        results = []
        processed_lines = []
        
        with open(queue_path, "r") as f:
            lines = f.readlines()
        
        for line in lines:
            record = QueueRecord.parse_line(line)
            if record is None:
                processed_lines.append(line)  # Keep comments/blanks
                continue
            
            # Process this URL
            result = self.process({
                "url": record.url,
                "manual_tags": record.tags,
            })
            
            results.append({
                "url": record.url,
                "result": result.payload,
            })
            
            # Mark as processed by commenting out
            processed_lines.append(f"# PROCESSED: {line.strip()}\n")
        
        # Rewrite queue file with processed items marked
        if not self.dry_run:
            with open(queue_path, "w") as f:
                f.writelines(processed_lines)
        
        return results
