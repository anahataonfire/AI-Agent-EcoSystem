"""
Planner Agent

Organizes action items from content and system tasks into prioritized tasks.
"""

import json
import sqlite3
import uuid
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

from .base import BaseAgent, ProposalEnvelope


# Database path
PLANNER_DB_PATH = Path(__file__).parent.parent.parent / "data" / "planner_tasks.db"
BACKLOG_PATH = Path(__file__).parent.parent.parent / "AI_Improvement_Backlog.md"


class TaskStatus(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ARCHIVED = "archived"


class TaskSource(Enum):
    CONTENT = "content"
    SYSTEM = "system"
    MANUAL = "manual"


@dataclass
class PlannerTask:
    """A prioritized task."""
    id: str
    source_type: str
    source_id: str
    description: str
    priority: int  # 1-5 (1 = highest)
    status: str
    due_date: Optional[str] = None
    created_at: str = None
    updated_at: str = None
    notes: str = ""
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at


class PlannerStore:
    """SQLite storage for planner tasks."""
    
    def __init__(self, db_path: Path = PLANNER_DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT,
                    description TEXT NOT NULL,
                    priority INTEGER DEFAULT 3,
                    status TEXT DEFAULT 'todo',
                    due_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)")
    
    def create(self, task: PlannerTask) -> bool:
        """Create a new task."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO tasks (id, source_type, source_id, description, priority, 
                                      status, due_date, created_at, updated_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task.id, task.source_type, task.source_id, task.description,
                    task.priority, task.status, task.due_date,
                    task.created_at, task.updated_at, task.notes
                ))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def read(self, task_id: str) -> Optional[PlannerTask]:
        """Read a task by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return PlannerTask(**dict(row))
            return None
    
    def update(self, task_id: str, **updates) -> bool:
        """Update task fields."""
        updates["updated_at"] = datetime.now().isoformat()
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [task_id]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?", values
            )
            return cursor.rowcount > 0
    
    def list_by_priority(self, status: Optional[str] = None, limit: int = 50) -> List[PlannerTask]:
        """List tasks ordered by priority."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY priority, created_at LIMIT ?",
                    (status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status != 'archived' ORDER BY priority, created_at LIMIT ?",
                    (limit,)
                ).fetchall()
            
            return [PlannerTask(**dict(row)) for row in rows]
    
    def list_by_source(self, source_type: str, limit: int = 50) -> List[PlannerTask]:
        """List tasks by source type."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tasks WHERE source_type = ? ORDER BY priority LIMIT ?",
                (source_type, limit)
            ).fetchall()
            return [PlannerTask(**dict(row)) for row in rows]
    
    def count_by_status(self) -> dict:
        """Count tasks by status."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM tasks GROUP BY status"
            ).fetchall()
            return {row[0]: row[1] for row in rows}


class PlannerAgent(BaseAgent):
    """
    Planner agent for managing prioritized tasks.
    
    Aggregates action items from content and system backlog into
    a unified priority list.
    """
    
    SKILL_FILE = "planner.skill.md"
    
    def __init__(self, run_id: str = "planner-run", run_ts: str = None,
                 content_store=None):
        """
        Initialize planner.
        
        Args:
            run_id: Unique run identifier
            run_ts: Timestamp for run
            content_store: ContentStore instance for reading action items
        """
        if run_ts is None:
            run_ts = datetime.now().isoformat()
        
        super().__init__(run_id=run_id, run_ts=run_ts)
        
        self.content_store = content_store
        self.store = PlannerStore()
    
    def process(self, input_data: dict) -> ProposalEnvelope:
        """
        Main processing - route to appropriate method.
        
        input_data should contain:
            - action: "create" | "update" | "list" | "import_content" | "import_system"
            - task: (for create/update) task data
            - filters: (for list) filter criteria
        """
        action = input_data.get("action", "list")
        
        if action == "create":
            result = self._create_task(input_data.get("task", {}))
            claims = ["create_task"]
        elif action == "update":
            result = self._update_task(
                input_data.get("task_id"),
                input_data.get("updates", {})
            )
            claims = ["update_task_status", "prioritize_tasks"]
        elif action == "list":
            result = self._list_tasks(input_data.get("filters", {}))
            claims = []
        elif action == "import_content":
            result = self._import_content_actions(input_data.get("content_id"))
            claims = ["create_task", "read_action_items"]
        elif action == "import_system":
            result = self._import_system_backlog()
            claims = ["create_task", "read_system_tasks"]
        else:
            result = {"error": f"Unknown action: {action}"}
            claims = []
        
        return self.wrap_output(result, claims)
    
    def _create_task(self, task_data: dict) -> dict:
        """Create a new task."""
        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
        
        task = PlannerTask(
            id=task_id,
            source_type=task_data.get("source_type", "manual"),
            source_id=task_data.get("source_id", ""),
            description=task_data.get("description", ""),
            priority=task_data.get("priority", 3),
            status="todo",
            due_date=task_data.get("due_date"),
            notes=task_data.get("notes", ""),
        )
        
        if self.store.create(task):
            return {"status": "created", "task": asdict(task)}
        else:
            return {"error": "Failed to create task"}
    
    def _update_task(self, task_id: str, updates: dict) -> dict:
        """Update an existing task."""
        if not task_id:
            return {"error": "task_id required"}
        
        # Filter to allowed updates
        allowed = {"priority", "status", "due_date", "notes", "description"}
        filtered = {k: v for k, v in updates.items() if k in allowed}
        
        if not filtered:
            return {"error": "No valid updates provided"}
        
        if self.store.update(task_id, **filtered):
            task = self.store.read(task_id)
            return {"status": "updated", "task": asdict(task) if task else None}
        else:
            return {"error": f"Task not found: {task_id}"}
    
    def _list_tasks(self, filters: dict) -> dict:
        """List tasks with optional filters."""
        status = filters.get("status")
        source_type = filters.get("source_type")
        limit = filters.get("limit", 50)
        
        if source_type:
            tasks = self.store.list_by_source(source_type, limit)
        else:
            tasks = self.store.list_by_priority(status, limit)
        
        counts = self.store.count_by_status()
        
        return {
            "tasks": [asdict(t) for t in tasks],
            "counts": counts,
            "total": len(tasks),
        }
    
    def _import_content_actions(self, content_id: str) -> dict:
        """Import action items from a content entry as tasks."""
        if not self.content_store:
            return {"error": "No content store configured"}
        
        entry = self.content_store.read(content_id)
        if not entry:
            return {"error": f"Content not found: {content_id}"}
        
        imported = []
        for action in entry.action_items:
            task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
            task = PlannerTask(
                id=task_id,
                source_type="content",
                source_id=content_id,
                description=action.description,
                priority=action.priority,
                status="todo",
                notes=f"From: {entry.title}",
            )
            if self.store.create(task):
                imported.append(task_id)
        
        return {
            "status": "imported",
            "content_id": content_id,
            "tasks_created": len(imported),
            "task_ids": imported,
        }
    
    def _import_system_backlog(self) -> dict:
        """Import tasks from AI_Improvement_Backlog.md."""
        if not BACKLOG_PATH.exists():
            return {"error": f"Backlog not found: {BACKLOG_PATH}"}
        
        with open(BACKLOG_PATH) as f:
            content = f.read()
        
        # Parse markdown for tasks
        # Look for patterns like: - [ ] Task description
        # or: - **P1**: Task description
        task_pattern = re.compile(r'- \[[ x]\] (.+?)(?:\n|$)', re.MULTILINE)
        priority_pattern = re.compile(r'\*\*P(\d)\*\*:?\s*(.+)')
        
        imported = []
        for match in task_pattern.finditer(content):
            description = match.group(1).strip()
            
            # Check for priority marker
            priority = 3
            prio_match = priority_pattern.match(description)
            if prio_match:
                priority = int(prio_match.group(1))
                description = prio_match.group(2).strip()
            
            # Skip if already imported (check by description)
            existing = [t for t in self.store.list_by_source("system", 100) 
                       if t.description == description]
            if existing:
                continue
            
            task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
            task = PlannerTask(
                id=task_id,
                source_type="system",
                source_id="AI_Improvement_Backlog.md",
                description=description,
                priority=priority,
                status="todo",
            )
            if self.store.create(task):
                imported.append(task_id)
        
        return {
            "status": "imported",
            "source": "AI_Improvement_Backlog.md",
            "tasks_created": len(imported),
            "task_ids": imported,
        }
    
    def get_stats(self) -> dict:
        """Get planner statistics."""
        counts = self.store.count_by_status()
        return {
            "total_tasks": sum(counts.values()),
            "by_status": counts,
        }
