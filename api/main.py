"""
DTL v3.0 API - Personal Intelligence System

FastAPI backend wrapping existing research engine.
"""

import os
import sys
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


# ============================================================================
# Planner Endpoints
# ============================================================================

@app.get("/planner/projects", response_model=List[PlannerTask])
async def planner_projects(x_api_key: str = Header(None)):
    """Get active projects/tasks."""
    verify_token(x_api_key)
    
    try:
        from src.agents.planner import Planner
        planner = Planner()
        tasks = planner.list_tasks(status="all")
        
        return [
            PlannerTask(
                id=t.get("id", ""),
                title=t.get("title", ""),
                priority=t.get("priority", 3),
                status=t.get("status", "todo"),
                category=t.get("category"),
                source_id=t.get("source_id"),
                created_at=t.get("created_at", ""),
            )
            for t in tasks
        ]
    except Exception:
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
    
    task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    return PlannerTask(
        id=task_id,
        title=title,
        priority=priority,
        status="todo",
        category=category,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


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
    """Get user's learning/preference summary."""
    verify_token(x_api_key)
    
    try:
        from src.agents.advisor import Advisor
        
        advisor = Advisor()
        memory = advisor.memory
        
        return {
            "feedback_count": len(memory.feedback_history),
            "top_categories": list(memory.category_preferences.keys())[:5],
            "action_patterns": memory.action_patterns,
        }
    except Exception:
        return {
            "feedback_count": 0,
            "top_categories": [],
            "action_patterns": {},
        }


# ============================================================================
# Run with: uvicorn api.main:app --reload
# ============================================================================
