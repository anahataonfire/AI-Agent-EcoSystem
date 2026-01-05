"""
DTL v3.0 API - Personal Intelligence System

FastAPI backend wrapping existing research engine.
"""

import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "3.0.0"}


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
    
    # TODO: Integrate with Content Store
    try:
        from src.content.store import ContentStore
        store = ContentStore()
        items = store.list_recent(limit=limit)
        
        return [
            LibraryItem(
                id=item.get("id", ""),
                title=item.get("title", "Untitled"),
                summary=item.get("summary", ""),
                source_url=item.get("url"),
                categories=item.get("categories", []),
                action_items=item.get("action_items", []),
                created_at=item.get("created_at", ""),
            )
            for item in items
        ]
    except Exception:
        return []


@app.get("/library/search", response_model=List[LibraryItem])
async def library_search(q: str, x_api_key: str = Header(None)):
    """Full-text search across library."""
    verify_token(x_api_key)
    # TODO: Implement search
    return []


@app.get("/content/browse", response_model=List[LibraryItem])
async def content_browse(limit: int = 50, x_api_key: str = Header(None)):
    """Browse curated content store (user's saved links)."""
    verify_token(x_api_key)
    
    try:
        from pathlib import Path
        from src.content.store import ContentStore
        
        # Use absolute path to ensure we find the right database
        db_path = Path(PROJECT_ROOT) / "data" / "content" / "content.db"
        store = ContentStore(db_path=db_path)
        entries = store.list_entries(limit=limit)
        
        return [
            LibraryItem(
                id=entry.id,
                title=entry.title or "Untitled",
                summary=entry.summary[:500] if entry.summary else "",
                source_url=entry.url,
                categories=entry.categories if isinstance(entry.categories, list) else [],
                action_items=[a.action for a in entry.action_items] if entry.action_items else [],
                created_at=entry.ingested_at or "",
            )
            for entry in entries
        ]
    except Exception as e:
        print(f"Content browse error: {e}")
        import traceback
        traceback.print_exc()
        return []


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
        return []


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
        return []


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
        return []


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
# Run with: uvicorn api.main:app --reload
# ============================================================================

