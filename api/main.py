"""
DTL v3.0 API - Personal Intelligence System

FastAPI backend wrapping existing research engine.
"""

import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Request, Response
import logging
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
sys.path.insert(0, PROJECT_ROOT)


# ============================================================================
# Request/Response Schemas
# ============================================================================

class InboxAddRequest(BaseModel):
    """Add item to inbox."""
    url: Optional[str] = None
    text: Optional[str] = None
    notes: Optional[str] = None


class InboxItem(BaseModel):
    """Inbox item response."""
    id: str
    type: str  # "link" | "text" | "note"
    content: str
    summary: Optional[str] = None
    categories: List[str] = []
    created_at: str


class LibraryItem(BaseModel):
    """Library content item."""
    id: str
    title: str
    summary: str
    source_url: Optional[str] = None
    categories: List[str] = []
    action_items: List[str] = []
    created_at: str
    planner_status: Optional[str] = None  # 'queued' | 'in_progress' | 'done' | null


class ResearchRequest(BaseModel):
    """Research query request."""
    query: str
    use_library: bool = True  # Cite user's own sources


class ResearchReport(BaseModel):
    """Grounded research report."""
    id: str
    query: str
    markdown: str
    grounding_score: int  # 0-100
    evidence_ids: List[str] = []
    created_at: str


class FeedbackRequest(BaseModel):
    """User feedback on content."""
    item_id: str
    feedback_type: str  # "positive" | "negative" | "save"
    context: Optional[str] = None


class PlannerTask(BaseModel):
    """Planner task."""
    id: str
    title: str
    priority: int  # 1, 2, 3
    status: str  # "todo" | "in_progress" | "done"
    category: Optional[str] = None
    source_id: Optional[str] = None
    created_at: str


# ============================================================================
# API Token Auth (Single User)
# ============================================================================

API_TOKEN = os.environ.get("DTL_API_TOKEN", "dev-token-change-me")


def verify_token(x_api_key: str = Header(None)) -> bool:
    """Simple token verification for single-user mode."""
    if x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print("DTL v3.0 API starting...")
    yield
    print("DTL v3.0 API shutting down...")


app = FastAPI(
    title="DTL v3.0 API",
    description="Personal Intelligence System - Grounded Research + Planner",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Logging & Observability
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dtl-api")

@app.middleware("http")
async def log_empty_responses(request: Request, call_next):
    """Log warning when API returns empty array (potential silent failure)."""
    from starlette.responses import Response as StarletteResponse
    
    response = await call_next(request)
    
    # Only check JSON responses
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        # Consume the body
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk
        
        body_text = body_bytes.decode()
        
        if body_text.strip() == "[]":
            logger.warning(f"Empty array response for {request.method} {request.url} - investigate potential silent failure")
        
        # Rebuild response with consumed body
        return StarletteResponse(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
            
    return response


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "3.0.0"}


@app.get("/stats")
async def get_stats(x_api_key: str = Header(None)):
    """Get dashboard stats - live counts from all stores."""
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        import sqlite3
        
        content_db = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        evidence_db = Path(PROJECT_ROOT) / "data" / "evidence_store.db"
        planner_db = Path(PROJECT_ROOT) / "data" / "planner_tasks.db"
        
        # Content count
        content_count = 0
        categories = set()
        if content_db.exists():
            with sqlite3.connect(content_db) as conn:
                content_count = conn.execute("SELECT COUNT(*) FROM content").fetchone()[0]
                rows = conn.execute("SELECT categories FROM content WHERE categories IS NOT NULL").fetchall()
                import json
                for row in rows:
                    try:
                        cats = json.loads(row[0])
                        categories.update(cats)
                    except:
                        pass
        
        # Evidence count
        evidence_count = 0
        if evidence_db.exists():
            with sqlite3.connect(evidence_db) as conn:
                try:
                    evidence_count = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
                except:
                    pass
        
        # Active tasks count
        tasks_active = 0
        if planner_db.exists():
            with sqlite3.connect(planner_db) as conn:
                try:
                    tasks_active = conn.execute("SELECT COUNT(*) FROM tasks WHERE status != 'done'").fetchone()[0]
                except:
                    pass
        
        return {
            "curated_links": content_count,
            "evidence_items": evidence_count,
            "categories": len(categories),
            "tasks_active": tasks_active,
        }
    except Exception as e:
        print(f"Stats error: {e}")
        return {"curated_links": 0, "evidence_items": 0, "categories": 0, "tasks_active": 0}


# ============================================================================
# Inbox Endpoints
# ============================================================================

@app.post("/inbox/add", response_model=InboxItem)
async def inbox_add(request: InboxAddRequest, x_api_key: str = Header(None)):
    """Add item to inbox for processing."""
    verify_token(x_api_key)
    
    # Determine type
    if request.url:
        item_type = "link"
        content = request.url
    elif request.text:
        item_type = "text"
        content = request.text
    else:
        item_type = "note"
        content = request.notes or ""
    
    # TODO: Integrate with Curator for auto-summarization
    item_id = f"inbox_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    return InboxItem(
        id=item_id,
        type=item_type,
        content=content,
        summary=None,  # Will be populated by Curator
        categories=[],
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/inbox/pending", response_model=List[InboxItem])
async def inbox_pending(x_api_key: str = Header(None)):
    """Get unprocessed inbox items."""
    verify_token(x_api_key)
    # TODO: Fetch from inbox store
    return []


# ============================================================================
# Library Endpoints
# ============================================================================

@app.get("/library/browse", response_model=List[LibraryItem])
async def library_browse(
    category: Optional[str] = None,
    limit: int = 50,
    x_api_key: str = Header(None)
):
    """Browse library content."""
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        from src.content.store import ContentStore
        
        # Use explicit absolute path to avoid CWD issues
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        store = ContentStore(db_path=db_path)
        items = store.list_entries(limit=limit)
        
        return [
            LibraryItem(
                id=item.id,
                title=item.title or "Untitled",
                summary=item.summary or "",
                source_url=item.url,
                categories=item.categories if item.categories else [],
                action_items=[ai.description for ai in (item.action_items or [])],
                created_at=item.ingested_at or "",
            )
            for item in items
        ]
    except Exception as e:
        print(f"Library browse error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Library browse error: {str(e)}")


@app.get("/library/search", response_model=List[LibraryItem])
async def library_search(q: str, x_api_key: str = Header(None)):
    """Full-text search across library."""
    verify_token(x_api_key)
    # TODO: Implement search
    return []


def _normalize_action_items(items: list) -> List[str]:
    """Convert action_items to list of strings for API response.
    
    Action items can be stored as either:
    - Strings: returned as-is
    - Dicts: converted to "[type] description" format
    """
    result = []
    for item in items:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            item_type = item.get("type", "action")
            description = item.get("description", "")
            result.append(f"[{item_type}] {description}")
    return result


@app.get("/content/browse", response_model=List[LibraryItem])
async def content_browse(
    limit: int = 50,
    planner_status: Optional[str] = None,
    x_api_key: str = Header(None)
):
    """Browse curated content store (user's saved links).
    
    Optional filter: planner_status (queued | in_progress | done)
    """
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        import sqlite3
        import json
        
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Build query with optional filter
            if planner_status:
                rows = conn.execute(
                    "SELECT * FROM content WHERE planner_status = ? ORDER BY ingested_at DESC LIMIT ?",
                    (planner_status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM content ORDER BY ingested_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            
            return [
                LibraryItem(
                    id=row["id"],
                    title=row["title"] or "Untitled",
                    summary=(row["summary"] or "")[:500],
                    source_url=row["url"],
                    categories=json.loads(row["categories"]) if row["categories"] else [],
                    action_items=_normalize_action_items(json.loads(row["action_items"]) if row["action_items"] else []),
                    created_at=row["ingested_at"] or "",
                    planner_status=dict(row).get("planner_status"),  # Handle missing column
                )
                for row in rows
            ]
    except Exception as e:
        print(f"Content browse error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Content browse error: {str(e)}")


@app.patch("/content/{content_id}/categories")
async def content_update_categories(
    content_id: str,
    categories: List[str],
    x_api_key: str = Header(None)
):
    """Update categories for a content item."""
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        import sqlite3
        import json
        
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        
        with sqlite3.connect(db_path) as conn:
            # Update categories as JSON array
            cursor = conn.execute(
                "UPDATE content SET categories = ? WHERE id = ?",
                (json.dumps(categories), content_id)
            )
            if cursor.rowcount > 0:
                return {"success": True, "content_id": content_id, "categories": categories}
            else:
                raise HTTPException(status_code=404, detail="Content not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Category update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/content/{content_id}/auto-categorize")
async def content_auto_categorize(content_id: str, x_api_key: str = Header(None)):
    """Use AI to suggest categories for a content item."""
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        import sqlite3
        import json
        import google.generativeai as genai
        
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        
        # Get content details
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, title, summary, url FROM content WHERE id = ?",
                (content_id,)
            ).fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Content not found")
            
            title = row["title"]
            summary = row["summary"]
            url = row["url"] or ""
        
        # Configure Gemini
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="No Gemini API key configured")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Available categories - more refined list
        categories = [
            "AI/ML", "Trading", "Research", "Learning", "Baking", "Fitness",
            "Productivity", "Development", "News", "Reference", "Finance",
            "Health", "Technology", "Business", "Creative", "Science"
        ]
        
        prompt = f"""Analyze this content and suggest 1-3 most relevant categories.

Title: {title}
Summary: {summary[:500] if summary else 'No summary'}
URL: {url}

Available categories: {', '.join(categories)}

Return ONLY a JSON array of category names, nothing else. Example: ["AI/ML", "Research"]
Pick categories that best match the content topic. Be specific and accurate."""

        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Parse JSON from response (handle markdown code blocks)
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        suggested = json.loads(response_text)
        
        # Validate categories
        valid_categories = [c for c in suggested if c in categories]
        if not valid_categories:
            valid_categories = ["Reference"]  # Default fallback
        
        return {
            "success": True,
            "content_id": content_id,
            "title": title,
            "suggested_categories": valid_categories
        }
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}, response: {response_text}")
        return {"success": False, "error": "Failed to parse AI response", "suggested_categories": ["Reference"]}
    except Exception as e:
        print(f"Auto-categorize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/content/bulk-auto-categorize")
async def content_bulk_auto_categorize(
    apply: bool = True,
    x_api_key: str = Header(None)
):
    """
    Auto-categorize all uncategorized content items using AI.
    
    Args:
        apply: If True, apply the suggested categories immediately. If False, just return suggestions.
    
    Returns:
        Summary of categorization results
    """
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        import sqlite3
        import json
        import google.generativeai as genai
        
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        
        # Get all uncategorized items
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT id, title, summary, url, categories 
                FROM content 
                WHERE categories IS NULL 
                   OR categories = '[]' 
                   OR categories = '["uncategorized"]'
                ORDER BY ingested_at DESC
            """).fetchall()
        
        if not rows:
            return {"success": True, "processed": 0, "message": "No uncategorized items found"}
        
        # Configure Gemini
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="No Gemini API key configured")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Available categories
        categories = [
            "AI/ML", "Trading", "Research", "Learning", "Baking", "Fitness",
            "Productivity", "Development", "News", "Reference", "Finance",
            "Health", "Technology", "Business", "Creative", "Science"
        ]
        
        results = []
        
        for row in rows:
            content_id = row["id"]
            title = row["title"] or "Untitled"
            summary = row["summary"] or ""
            url = row["url"] or ""
            
            try:
                prompt = f"""Analyze this content and suggest 1-3 most relevant categories.

Title: {title}
Summary: {summary[:500] if summary else 'No summary'}
URL: {url}

Available categories: {', '.join(categories)}

Return ONLY a JSON array of category names, nothing else. Example: ["AI/ML", "Research"]
Pick categories that best match the content topic. Be specific and accurate."""

                response = model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Parse JSON from response
                if "```" in response_text:
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                
                suggested = json.loads(response_text)
                valid_categories = [c for c in suggested if c in categories]
                if not valid_categories:
                    valid_categories = ["Reference"]
                
                # Apply immediately if requested
                if apply:
                    with sqlite3.connect(db_path) as conn:
                        conn.execute(
                            "UPDATE content SET categories = ? WHERE id = ?",
                            (json.dumps(valid_categories), content_id)
                        )
                
                results.append({
                    "id": content_id,
                    "title": title[:50],
                    "categories": valid_categories,
                    "applied": apply
                })
                
            except Exception as e:
                results.append({
                    "id": content_id,
                    "title": title[:50],
                    "error": str(e),
                    "applied": False
                })
        
        applied_count = sum(1 for r in results if r.get("applied"))
        
        return {
            "success": True,
            "processed": len(results),
            "applied": applied_count,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Bulk auto-categorize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# In-memory store for deep research jobs
_deep_research_jobs: Dict[str, dict] = {}


class DeepResearchResult(BaseModel):
    """Deep research job result."""
    research_id: str
    source_content_id: str
    source_title: str
    status: str  # "extracting" | "researching" | "synthesizing" | "completed" | "failed"
    extracted_claims: List[str] = []
    research_findings: List[dict] = []
    report_markdown: Optional[str] = None
    datamart: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


@app.post("/content/{content_id}/deep-research", response_model=DeepResearchResult)
async def content_deep_research(content_id: str, x_api_key: str = Header(None)):
    """Start deep research on an existing content item.
    
    Process:
    1. Extract key claims/topics from the content
    2. Research each claim across multiple sources
    3. Synthesize findings into an analysis report
    4. Route to appropriate datamart
    """
    verify_token(x_api_key)
    
    from threading import Thread
    
    # Get content from database
    content_db = os.path.join(PROJECT_ROOT, "data", "content", "content.db")
    if not os.path.exists(content_db):
        raise HTTPException(status_code=404, detail="Content database not found")
    
    import sqlite3
    with sqlite3.connect(content_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, title, summary, url, categories FROM content WHERE id = ?",
            (content_id,)
        ).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"Content {content_id} not found")
    
    research_id = f"DR-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.now(timezone.utc).isoformat()
    
    # Initialize job
    _deep_research_jobs[research_id] = {
        "research_id": research_id,
        "source_content_id": content_id,
        "source_title": row["title"] or "Untitled",
        "source_summary": row["summary"] or "",
        "source_url": row["url"] or "",
        "source_categories": json.loads(row["categories"]) if row["categories"] else [],
        "status": "extracting",
        "extracted_claims": [],
        "research_findings": [],
        "report_markdown": None,
        "datamart": None,
        "error": None,
        "created_at": created_at,
        "completed_at": None,
    }
    
    def run_deep_research():
        job = _deep_research_jobs[research_id]
        
        try:
            from google import genai
            from src.core.llm_config import get_llm_api_key
            
            api_key = get_llm_api_key()
            client = genai.Client(api_key=api_key)
            
            # Step 1: Extract claims/topics
            job["status"] = "extracting"
            
            extract_prompt = f"""Analyze this content and extract 3-5 key claims or topics that warrant deeper research.

TITLE: {job["source_title"]}
CONTENT: {job["source_summary"]}
URL: {job["source_url"]}

Return a JSON array of strings, each being a specific, searchable claim or topic.
Example: ["$1.5M weekly trading bot profit claims", "MEV arbitrage strategies", "browomo crypto trading history"]

Return ONLY the JSON array, no other text."""

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=extract_prompt
            )
            
            try:
                claims_text = response.text.strip()
                if claims_text.startswith("```"):
                    claims_text = claims_text.split("\n", 1)[1].rsplit("```", 1)[0]
                claims = json.loads(claims_text)
                job["extracted_claims"] = claims[:5]
            except:
                job["extracted_claims"] = [job["source_title"]]
            
            # Step 2: Research each claim
            job["status"] = "researching"
            findings = []
            
            for claim in job["extracted_claims"][:3]:  # Limit to 3 claims
                # Google News RSS
                try:
                    import requests
                    news_url = f"https://news.google.com/rss/search?q={claim.replace(' ', '+')}"
                    # Use feedparser if available, or simple fetch
                    findings.append({
                        "claim": claim,
                        "source": "google_news",
                        "query": news_url,
                        "status": "searched"
                    })
                except Exception as e:
                    findings.append({"claim": claim, "source": "google_news", "error": str(e)})
                
                # Reddit search
                try:
                    reddit_url = f"https://www.reddit.com/search.json?q={claim.replace(' ', '+')}&sort=relevance&limit=5"
                    resp = requests.get(reddit_url, headers={"User-Agent": "DTL-Research/1.0"}, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        posts = data.get("data", {}).get("children", [])[:3]
                        for post in posts:
                            findings.append({
                                "claim": claim,
                                "source": "reddit",
                                "title": post["data"].get("title", ""),
                                "url": f"https://reddit.com{post['data'].get('permalink', '')}",
                                "score": post["data"].get("score", 0)
                            })
                except Exception as e:
                    findings.append({"claim": claim, "source": "reddit", "error": str(e)})
            
            job["research_findings"] = findings
            
            # Step 3: Synthesize report
            job["status"] = "synthesizing"
            
            findings_text = "\n".join([
                f"- [{f.get('source', 'unknown')}] {f.get('title', f.get('claim', 'No title'))}"
                for f in findings if not f.get("error")
            ])
            
            synthesis_prompt = f"""You are a research analyst. Create a comprehensive analysis report for this content.

ORIGINAL CONTENT:
Title: {job["source_title"]}
Summary: {job["source_summary"]}
URL: {job["source_url"]}

EXTRACTED CLAIMS TO ANALYZE:
{json.dumps(job["extracted_claims"], indent=2)}

RESEARCH FINDINGS:
{findings_text}

Create a structured Markdown report with these sections:

# Deep Research: {job["source_title"]}

## Source Overview
Brief description of the original content and why it merits deeper analysis.

## Claim Analysis
For each extracted claim:
- **Claim**: The specific claim
- **Verification Status**: Verified / Unverified / Contradicted / Needs More Research
- **Evidence**: What was found supporting or contradicting this

## Key Findings
Bullet points of the most important discoveries from research.

## Risk Assessment
- Red flags identified
- Credibility concerns
- Missing information

## Action Items
Specific next steps based on the analysis:
- [ ] Action item 1
- [ ] Action item 2

## Sources
List of sources consulted during research."""

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=synthesis_prompt
            )
            
            job["report_markdown"] = response.text if response.text else "Report generation failed"
            
            # Step 4: Route to datamart
            try:
                registry_path = os.path.join(PROJECT_ROOT, "config", "datamart_registry.json")
                if os.path.exists(registry_path):
                    with open(registry_path) as f:
                        registry = json.load(f)
                    
                    # Find matching datamart based on categories
                    source_cats = [c.lower() for c in job["source_categories"]]
                    for topic_id, topic_config in registry.get("topics", {}).items():
                        topic_cats = [c.lower() for c in topic_config.get("categories", [])]
                        if any(c in source_cats for c in topic_cats):
                            job["datamart"] = topic_id
                            break
                    
                    if not job["datamart"]:
                        job["datamart"] = "unrouted"
            except Exception as e:
                print(f"Datamart routing error: {e}")
            
            job["status"] = "completed"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            job["status"] = "failed"
            job["error"] = str(e)
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    # Start background thread
    thread = Thread(target=run_deep_research, daemon=True)
    thread.start()
    
    return DeepResearchResult(**{k: v for k, v in _deep_research_jobs[research_id].items() 
                                  if k in DeepResearchResult.model_fields})


@app.get("/content/{content_id}/deep-research/status", response_model=DeepResearchResult)
async def content_deep_research_status(content_id: str, x_api_key: str = Header(None)):
    """Get status of deep research job for a content item."""
    verify_token(x_api_key)
    
    # Find job by source content ID
    for job in _deep_research_jobs.values():
        if job["source_content_id"] == content_id:
            return DeepResearchResult(**{k: v for k, v in job.items() 
                                          if k in DeepResearchResult.model_fields})
    
    raise HTTPException(status_code=404, detail=f"No deep research job found for content {content_id}")


@app.patch("/content/{content_id}/planner-status")
async def content_update_planner_status(
    content_id: str,
    status: Optional[str] = None,
    x_api_key: str = Header(None)
):
    """Update planner status for a content item.
    
    status: 'queued' | 'in_progress' | 'done' | null (to unqueue)
    """
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        import sqlite3
        
        # Validate status
        valid_statuses = [None, "queued", "in_progress", "done"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "UPDATE content SET planner_status = ? WHERE id = ?",
                (status, content_id)
            )
            if cursor.rowcount > 0:
                return {"success": True, "content_id": content_id, "planner_status": status}
            else:
                raise HTTPException(status_code=404, detail="Content not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Planner status update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/content/{content_id}")
async def content_delete(content_id: str, x_api_key: str = Header(None)):
    """Delete a content item from the library."""
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        from src.content.store import ContentStore
        
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        store = ContentStore(db_path=db_path)
        
        # Delete from database
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("DELETE FROM content WHERE id = ?", (content_id,))
            if cursor.rowcount > 0:
                return {"success": True, "deleted_id": content_id}
            else:
                raise HTTPException(status_code=404, detail="Content not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Content delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Planner Endpoints
# ============================================================================

@app.get("/planner/projects", response_model=List[PlannerTask])
async def planner_projects(x_api_key: str = Header(None)):
    """Get active projects/tasks."""
    verify_token(x_api_key)
    
    try:
        from src.agents.planner import PlannerStore
        store = PlannerStore()
        tasks = store.list_by_priority(limit=50)
        
        return [
            PlannerTask(
                id=t.id,
                title=t.description,  # PlannerTask uses 'description' for the task text
                priority=t.priority,
                status=t.status,
                category=t.source_id if t.source_id != "manual" else None,
                source_id=t.source_id,
                created_at=t.created_at or "",
            )
            for t in tasks
        ]
    except Exception as e:
        print(f"Error fetching tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching tasks: {str(e)}")


@app.post("/planner/task", response_model=PlannerTask)
async def planner_create_task(
    title: str,
    priority: int = 2,
    category: Optional[str] = None,
    x_api_key: str = Header(None)
):
    """Create a new task."""
    verify_token(x_api_key)
    
    from src.agents.planner import PlannerStore, PlannerTask as PlannerTaskModel, TaskStatus, TaskSource
    
    task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat()
    
    # Create the task object
    task = PlannerTaskModel(
        id=task_id,
        source_type=TaskSource.MANUAL.value,  # Use .value for SQLite
        source_id=category or "manual",
        description=title,
        priority=priority,
        status=TaskStatus.TODO.value,  # Use .value for SQLite
        created_at=now,
        updated_at=now,
    )
    
    # Persist to database
    store = PlannerStore()
    store.create(task)
    
    return PlannerTask(
        id=task_id,
        title=title,
        priority=priority,
        status="todo",
        category=category,
        created_at=now,
    )


@app.patch("/planner/task/{task_id}/status")
async def planner_update_status(
    task_id: str,
    status: str,
    x_api_key: str = Header(None)
):
    """Update a task's status (for drag-and-drop Kanban)."""
    verify_token(x_api_key)
    
    try:
        from src.agents.planner import PlannerStore
        store = PlannerStore()
        store.update(task_id, status=status)
        return {"success": True, "task_id": task_id, "status": status}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Research Endpoints
# ============================================================================

@app.post("/research/run", response_model=ResearchReport)
async def research_run(request: ResearchRequest, x_api_key: str = Header(None)):
    """Run grounded research query."""
    verify_token(x_api_key)
    
    try:
        from src.graph.workflow import run_pipeline
        
        result = run_pipeline(request.query)
        report_id = f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        return ResearchReport(
            id=report_id,
            query=request.query,
            markdown=result.get("final_report", "No report generated"),
            grounding_score=result.get("grounding_score", 0),
            evidence_ids=result.get("evidence_ids", []),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        return ResearchReport(
            id="error",
            query=request.query,
            markdown=f"Error: {str(e)}",
            grounding_score=0,
            evidence_ids=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )


@app.get("/research/{report_id}", response_model=ResearchReport)
async def research_get(report_id: str, x_api_key: str = Header(None)):
    """Get a research report by ID."""
    verify_token(x_api_key)
    # TODO: Fetch from report store
    raise HTTPException(status_code=404, detail="Report not found")


# ============================================================================
# Feedback Endpoints
# ============================================================================

@app.post("/feedback")
async def feedback_submit(request: FeedbackRequest, x_api_key: str = Header(None)):
    """Submit feedback on content."""
    verify_token(x_api_key)
    
    try:
        from src.agents.advisor import Advisor
        
        advisor = Advisor()
        # Record feedback for learning
        # TODO: Implement proper feedback recording
        
        return {"status": "recorded", "item_id": request.item_id}
    except Exception:
        return {"status": "recorded", "item_id": request.item_id}


@app.get("/learning/summary")
async def learning_summary(x_api_key: str = Header(None)):
    """Get user's learning/preference summary from advisor memory."""
    verify_token(x_api_key)
    
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path(PROJECT_ROOT) / "data" / "advisor_learning.db"
        if not db_path.exists():
            return {"feedback_count": 0, "patterns": [], "categories": {}}
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get total feedback count
        cursor.execute("SELECT COUNT(*) FROM learning_patterns")
        feedback_count = cursor.fetchone()[0]
        
        # Get recent patterns
        cursor.execute("""
            SELECT pattern_type, context, outcome, confidence, created_at 
            FROM learning_patterns 
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        patterns = [
            {
                "type": row[0],
                "context": row[1],
                "outcome": row[2],
                "confidence": row[3],
                "created_at": row[4],
            }
            for row in cursor.fetchall()
        ]
        
        # Get category counts (accepted only)
        cursor.execute("""
            SELECT context, COUNT(*) as cnt
            FROM learning_patterns 
            WHERE pattern_type = 'category' AND outcome = 'accepted'
            GROUP BY context
        """)
        
        # Parse categories from context JSON
        import json
        category_counts: Dict[str, int] = {}
        for row in cursor.fetchall():
            try:
                ctx = json.loads(row[0])
                cat = ctx.get("suggested", "Unknown")
                category_counts[cat] = category_counts.get(cat, 0) + row[1]
            except:
                pass
        
        conn.close()
        
        return {
            "feedback_count": feedback_count,
            "patterns": patterns,
            "categories": category_counts,
        }
    except Exception as e:
        print(f"Learning summary error: {e}")
        return {"feedback_count": 0, "patterns": [], "categories": {}}


# ============================================================================
# Polymarket Scanner Endpoints
# ============================================================================

class PolymarketOpportunity(BaseModel):
    """Polymarket opportunity."""
    market_id: str
    question: str
    hours_remaining: float
    yes_price: float
    no_price: float
    liquidity: float
    certainty_side: str
    certainty_pct: float
    apr_estimate: float
    event_slug: str
    market_url: str


@app.get("/polymarket/opportunities", response_model=List[PolymarketOpportunity])
async def polymarket_opportunities(
    max_hours: float = 4.0,
    min_certainty: float = 0.95,
    min_liquidity: float = 100.0,
    x_api_key: str = Header(None)
):
    """Scan Polymarket for high-certainty opportunities."""
    verify_token(x_api_key)
    
    try:
        from src.polymarket_scanner import CertaintyScanner
        
        scanner = CertaintyScanner()
        opportunities = scanner.scan(
            max_hours=max_hours,
            min_certainty=min_certainty,
            min_liquidity=min_liquidity
        )
        
        return [
            PolymarketOpportunity(
                market_id=opp.market_id,
                question=opp.question,
                hours_remaining=opp.hours_remaining,
                yes_price=opp.yes_price,
                no_price=opp.no_price,
                liquidity=opp.liquidity,
                certainty_side=opp.certainty_side,
                certainty_pct=opp.certainty_pct,
                apr_estimate=opp.apr_estimate,
                event_slug=opp.event_slug,
                market_url=opp.market_url,
            )
            for opp in opportunities
        ]
    except Exception as e:
        # Return empty list on error (frontend handles this)
        print(f"Polymarket scan error: {e}")
        raise HTTPException(status_code=500, detail=f"Polymarket scan error: {str(e)}")


# ============================================================================
# Evidence Browser Endpoints
# ============================================================================

class EvidenceItem(BaseModel):
    """Evidence store item."""
    evidence_id: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: str
    lifecycle: str


@app.get("/evidence/browse", response_model=List[EvidenceItem])
async def evidence_browse(limit: int = 50, x_api_key: str = Header(None)):
    """Browse evidence store items."""
    verify_token(x_api_key)
    
    try:
        from src.core.evidence_store import EvidenceStore
        
        store = EvidenceStore()
        ids = store.list_ids()[:limit]
        
        items = []
        for eid in ids:
            entry = store.get_with_metadata(eid)
            if entry:
                items.append(EvidenceItem(
                    evidence_id=eid,
                    payload=entry.get("payload", {}),
                    metadata=entry.get("metadata", {}),
                    created_at=entry.get("created_at", ""),
                    lifecycle=entry.get("lifecycle", "active"),
                ))
        return items
    except Exception as e:
        print(f"Evidence browse error: {e}")
        raise HTTPException(status_code=500, detail=f"Evidence browse error: {str(e)}")


@app.get("/evidence/{evidence_id}", response_model=EvidenceItem)
async def evidence_get(evidence_id: str, x_api_key: str = Header(None)):
    """Get a specific evidence item."""
    verify_token(x_api_key)
    
    try:
        from src.core.evidence_store import EvidenceStore
        
        store = EvidenceStore()
        entry = store.get_with_metadata(evidence_id)
        
        if not entry:
            raise HTTPException(status_code=404, detail="Evidence not found")
        
        return EvidenceItem(
            evidence_id=evidence_id,
            payload=entry.get("payload", {}),
            metadata=entry.get("metadata", {}),
            created_at=entry.get("created_at", ""),
            lifecycle=entry.get("lifecycle", "active"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Datamarts Endpoints
# ============================================================================

class DatamartItem(BaseModel):
    """Datamart bundle summary."""
    topic_id: str
    topic_name: str
    source_count: int
    version: int
    fingerprint: str
    status: str
    created_at: str
    updated_at: str


@app.get("/datamarts/list", response_model=List[DatamartItem])
async def datamarts_list(include_archived: bool = False, x_api_key: str = Header(None)):
    """List all datamart bundles."""
    verify_token(x_api_key)
    
    try:
        from src.content.datamart_bundler import DatamartBundler
        
        bundler = DatamartBundler()
        bundles = bundler.list_bundles(include_archived=include_archived)
        
        return [
            DatamartItem(
                topic_id=b.topic_id,
                topic_name=b.topic_name,
                source_count=b.source_count,
                version=b.version,
                fingerprint=b.fingerprint,
                status=b.status,
                created_at=b.created_at,
                updated_at=b.updated_at,
            )
            for b in bundles
        ]
    except Exception as e:
        print(f"Datamarts list error: {e}")
        raise HTTPException(status_code=500, detail=f"Datamarts list error: {str(e)}")


# ============================================================================
# Health Report Endpoints
# ============================================================================

class HealthReport(BaseModel):
    """Datamart health report."""
    topics_active: int
    topics_pending: int
    topics_archived: int
    last_sync_time: str
    last_sync_outcome: str
    top_topics: List[Dict[str, Any]]
    fingerprint_mismatches: int
    notify_count_7d: int
    planner_tasks_7d: int
    generated_at: str


@app.get("/health/datamart", response_model=HealthReport)
async def health_datamart(x_api_key: str = Header(None)):
    """Get datamart health report."""
    verify_token(x_api_key)
    
    try:
        import json
        import re
        from pathlib import Path
        from datetime import timedelta
        from src.content.datamart_bundler import DatamartBundler
        from src.content.store import ContentStore
        
        # 1. Load registry and count by status
        registry_path = Path(PROJECT_ROOT) / "config" / "datamart_registry.json"
        registry = {}
        if registry_path.exists():
            with open(registry_path) as f:
                registry = json.load(f).get("topics", {})
        
        status_counts = {"active": 0, "pending": 0, "archived": 0}
        for topic_id, meta in registry.items():
            status = meta.get("status", "unknown")
            if status in status_counts:
                status_counts[status] += 1
        
        # 2. Last Sync Time & Outcome
        log_path = Path(PROJECT_ROOT) / "logs" / "datamart_sync.log"
        last_sync_time = "Never"
        last_sync_outcome = "Unknown"
        
        if log_path.exists():
            lines = log_path.read_text().strip().split("\n")
            for line in reversed(lines):
                if "Sync Complete. Success" in line:
                    last_sync_outcome = "SUCCESS"
                    match = re.search(r"\[(.*?)\]", line)
                    if match:
                        last_sync_time = match.group(1)
                    break
                elif "Sync Failed" in line:
                    last_sync_outcome = "FAILED"
                    match = re.search(r"\[(.*?)\]", line)
                    if match:
                        last_sync_time = match.group(1)
                    break
        
        # 3. Top Topics by Source Count
        bundler = DatamartBundler()
        topic_source_counts = []
        
        datamarts_dir = bundler.base_path
        if datamarts_dir.exists():
            for topic_dir in datamarts_dir.iterdir():
                if topic_dir.is_dir():
                    manifest = bundler.read_manifest(topic_dir.name)
                    if manifest:
                        topic_source_counts.append({
                            "topic_id": topic_dir.name,
                            "source_count": len(manifest.sources)
                        })
        
        topic_source_counts.sort(key=lambda x: x["source_count"], reverse=True)
        
        # 4. Fingerprint validation (simplified - just count)
        mismatch_count = 0  # For now, assume all valid
        
        # 5. Activity counts
        store = ContentStore()
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        notify_count = 0
        planner_task_count = 0
        
        try:
            all_entries = store.list_entries(limit=1000)
            for entry in all_entries:
                try:
                    if hasattr(entry, 'ingested_at'):
                        ingested = datetime.fromisoformat(entry.ingested_at.replace("Z", "+00:00"))
                        if ingested >= seven_days_ago:
                            if hasattr(entry, 'deep_analysis') and entry.deep_analysis:
                                actions = getattr(entry.deep_analysis, 'system_actions', []) or []
                                if 'NOTIFY' in [str(a) for a in actions]:
                                    notify_count += 1
                except Exception:
                    continue
        except Exception:
            pass
        
        return HealthReport(
            topics_active=status_counts.get("active", 0),
            topics_pending=status_counts.get("pending", 0),
            topics_archived=status_counts.get("archived", 0),
            last_sync_time=last_sync_time,
            last_sync_outcome=last_sync_outcome,
            top_topics=topic_source_counts[:10],
            fingerprint_mismatches=mismatch_count,
            notify_count_7d=notify_count,
            planner_tasks_7d=planner_task_count,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        print(f"Health report error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Deep Research Endpoints
# ============================================================================

# In-memory job store (would use Redis/DB in production)
_research_jobs: Dict[str, dict] = {}


class DeepResearchRequest(BaseModel):
    """Request to start a deep research job."""
    topic: str
    keywords: List[str] = []
    target_datamart: Optional[str] = None  # Auto-detect if not specified
    sources: List[str] = ["google_news", "reddit"]
    max_items: int = 40
    sync_to_drive: bool = True


class DeepResearchStatus(BaseModel):
    """Status of a deep research job."""
    research_id: str
    status: str  # "queued" | "fetching" | "synthesizing" | "completed" | "failed"
    topic: str
    evidence_count: int = 0
    report_id: Optional[str] = None
    datamart: Optional[str] = None
    drive_synced: bool = False
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


@app.post("/research/start", response_model=DeepResearchStatus)
async def research_start(request: DeepResearchRequest, x_api_key: str = Header(None)):
    """Start a deep research job on a topic.
    
    Fetches from Google News and Reddit, synthesizes with LLM, 
    routes to datamart, and optionally syncs to Google Drive.
    """
    verify_token(x_api_key)
    
    import asyncio
    from threading import Thread
    
    research_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.now(timezone.utc).isoformat()
    
    # Initialize job
    _research_jobs[research_id] = {
        "research_id": research_id,
        "status": "queued",
        "topic": request.topic,
        "keywords": request.keywords,
        "target_datamart": request.target_datamart,
        "sources": request.sources,
        "max_items": request.max_items,
        "sync_to_drive": request.sync_to_drive,
        "evidence_count": 0,
        "report_id": None,
        "datamart": None,
        "drive_synced": False,
        "error": None,
        "created_at": created_at,
        "completed_at": None,
    }
    
    # Run research in background thread
    def run_research():
        import time
        job = _research_jobs[research_id]
        
        try:
            job["status"] = "fetching"
            
            # Fetch from sources
            evidence_items = []
            
            # Google News RSS
            if "google_news" in request.sources:
                try:
                    from src.content.fetcher import ContentFetcher
                    fetcher = ContentFetcher()
                    # Use a simple search URL
                    news_url = f"https://news.google.com/rss/search?q={request.topic.replace(' ', '+')}"
                    items = fetcher.fetch_rss(news_url, max_items=request.max_items // 2)
                    evidence_items.extend(items[:request.max_items // 2])
                except Exception as e:
                    print(f"Google News fetch error: {e}")
            
            # Reddit RSS (may fail with 403)
            if "reddit" in request.sources:
                try:
                    reddit_url = f"https://www.reddit.com/search.json?q={request.topic.replace(' ', '+')}&sort=relevance&limit=20"
                    import requests
                    resp = requests.get(reddit_url, headers={"User-Agent": "DTL-Research/1.0"}, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        for post in data.get("data", {}).get("children", [])[:request.max_items // 2]:
                            evidence_items.append({
                                "title": post["data"].get("title", ""),
                                "url": f"https://reddit.com{post['data'].get('permalink', '')}",
                                "source": "reddit",
                            })
                except Exception as e:
                    print(f"Reddit fetch error: {e}")
            
            job["evidence_count"] = len(evidence_items)
            job["status"] = "synthesizing"
            
            # LLM Synthesis
            try:
                from google import genai
                from src.core.llm_config import get_llm_api_key
                
                api_key = get_llm_api_key()
                client = genai.Client(api_key=api_key)
                
                evidence_text = "\n".join([
                    f"- [{i+1}] {item.get('title', 'No title')} ({item.get('source', 'unknown')})"
                    for i, item in enumerate(evidence_items[:30])
                ])
                
                prompt = f"""You are a research analyst. Synthesize the following evidence about "{request.topic}" into a structured report.

EVIDENCE:
{evidence_text}

Create a report with these sections:
1. Executive Summary (2-3 sentences)
2. Key Developments (5+ bullet points)
3. Analysis & Trends
4. Key Players
5. Risks & Challenges
6. Outlook & Implications

Use [EVID:N] format to cite evidence items."""

                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                
                report_text = response.text if response.text else "No report generated"
                
                # Store report as evidence
                report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
                job["report_id"] = report_id
                
            except Exception as e:
                print(f"LLM synthesis error: {e}")
                job["error"] = str(e)
                
            # Route to datamart
            try:
                from src.content.routing_policy import RoutingPolicy
                import json
                
                policy_path = os.path.join(PROJECT_ROOT, "config", "routing_policy.json")
                registry_path = os.path.join(PROJECT_ROOT, "config", "datamart_registry.json")
                
                if os.path.exists(policy_path) and os.path.exists(registry_path):
                    with open(registry_path) as f:
                        registry = json.load(f)
                    
                    # Find matching datamart
                    target = request.target_datamart
                    if not target:
                        # Auto-detect based on topic
                        for topic_id, topic_config in registry.get("topics", {}).items():
                            topic_tags = [t.lower() for t in topic_config.get("tags", [])]
                            if any(kw.lower() in request.topic.lower() for kw in topic_tags):
                                target = topic_id
                                break
                    
                    job["datamart"] = target or "unrouted"
                    
            except Exception as e:
                print(f"Routing error: {e}")
            
            # Sync to Drive
            if request.sync_to_drive and job.get("datamart"):
                try:
                    import subprocess
                    result = subprocess.run(
                        [".venv/bin/python", "-m", "src.cli", "datamart-sync"],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        timeout=60
                    )
                    job["drive_synced"] = result.returncode == 0
                except Exception as e:
                    print(f"Drive sync error: {e}")
            
            job["status"] = "completed"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            job["status"] = "failed"
            job["error"] = str(e)
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    # Start background thread
    thread = Thread(target=run_research, daemon=True)
    thread.start()
    
    return DeepResearchStatus(**_research_jobs[research_id])


@app.get("/research/{research_id}/status", response_model=DeepResearchStatus)
async def research_status(research_id: str, x_api_key: str = Header(None)):
    """Get status of a research job."""
    verify_token(x_api_key)
    
    if research_id not in _research_jobs:
        raise HTTPException(status_code=404, detail=f"Research job {research_id} not found")
    
    return DeepResearchStatus(**_research_jobs[research_id])


@app.get("/research/jobs", response_model=List[DeepResearchStatus])
async def research_list_jobs(x_api_key: str = Header(None)):
    """List all research jobs."""
    verify_token(x_api_key)
    
    return [DeepResearchStatus(**job) for job in _research_jobs.values()]


@app.get("/datamarts/topics")
async def datamarts_list_topics(x_api_key: str = Header(None)):
    """List available datamart topics for research routing."""
    verify_token(x_api_key)
    
    registry_path = os.path.join(PROJECT_ROOT, "config", "datamart_registry.json")
    if not os.path.exists(registry_path):
        return []
    
    with open(registry_path) as f:
        registry = json.load(f)
    
    return [
        {"id": topic_id, "name": config.get("name", topic_id), "status": config.get("status", "unknown")}
        for topic_id, config in registry.get("topics", {}).items()
    ]


# ============================================================================
# Run with: uvicorn api.main:app --reload
# ============================================================================

