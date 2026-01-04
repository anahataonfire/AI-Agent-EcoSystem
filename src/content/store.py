"""
SQLite-backed content store for the Smart Curator system.

Provides CRUD operations for content entries with full-text search support.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Iterator
from datetime import datetime, timezone

from .schemas import (
    ContentEntry,
    ContentStatus,
    ActionItem,
    generate_content_id,
)


class ContentStore:
    """SQLite-backed store for content entries."""
    
    DEFAULT_PATH = Path("data/content/content.db")
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or self.DEFAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS content (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    categories TEXT NOT NULL,  -- JSON array
                    relevance_score REAL NOT NULL,
                    action_items TEXT NOT NULL,  -- JSON array
                    status TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    raw_content TEXT
                )
            """)
            
            # Create indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON content(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ingested ON content(ingested_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relevance ON content(relevance_score)")
            
            # FTS5 for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                    id,
                    title,
                    summary,
                    categories,
                    content='content',
                    content_rowid='rowid'
                )
            """)
            
            # Triggers to keep FTS in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS content_ai AFTER INSERT ON content BEGIN
                    INSERT INTO content_fts(id, title, summary, categories)
                    VALUES (new.id, new.title, new.summary, new.categories);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS content_ad AFTER DELETE ON content BEGIN
                    INSERT INTO content_fts(content_fts, id, title, summary, categories)
                    VALUES ('delete', old.id, old.title, old.summary, old.categories);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS content_au AFTER UPDATE ON content BEGIN
                    INSERT INTO content_fts(content_fts, id, title, summary, categories)
                    VALUES ('delete', old.id, old.title, old.summary, old.categories);
                    INSERT INTO content_fts(id, title, summary, categories)
                    VALUES (new.id, new.title, new.summary, new.categories);
                END
            """)
            
            conn.commit()
    
    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        return sqlite3.connect(self.db_path)
    
    def write(self, entry: ContentEntry) -> bool:
        """
        Write a content entry to the store.
        
        Returns:
            True if written, False if URL already exists
        """
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO content 
                    (id, url, title, summary, categories, relevance_score, 
                     action_items, status, ingested_at, source_hash, raw_content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.id,
                        entry.url,
                        entry.title,
                        entry.summary,
                        json.dumps(entry.categories),
                        entry.relevance_score,
                        json.dumps([a.to_dict() for a in entry.action_items]),
                        entry.status.value,
                        entry.ingested_at,
                        entry.source_hash,
                        entry.raw_content,
                    )
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # URL already exists
                return False
    
    def read(self, entry_id: str) -> Optional[ContentEntry]:
        """Read a content entry by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM content WHERE id = ?", (entry_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return self._row_to_entry(row)
    
    def read_by_url(self, url: str) -> Optional[ContentEntry]:
        """Read a content entry by URL."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM content WHERE url = ?", (url,)
            ).fetchone()
            
            if not row:
                return None
            
            return self._row_to_entry(row)
    
    def update_status(self, entry_id: str, status: ContentStatus) -> bool:
        """Update the status of a content entry."""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE content SET status = ? WHERE id = ?",
                (status.value, entry_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def list_entries(self, limit: int = 50) -> list[ContentEntry]:
        """List most recent content entries."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM content ORDER BY ingested_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            
            return [self._row_to_entry(row) for row in rows]
    
    def list_by_status(self, status: ContentStatus, limit: int = 50) -> list[ContentEntry]:
        """List content entries by status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM content WHERE status = ? ORDER BY ingested_at DESC LIMIT ?",
                (status.value, limit)
            ).fetchall()
            
            return [self._row_to_entry(row) for row in rows]
    
    def list_by_category(self, category: str, limit: int = 50) -> list[ContentEntry]:
        """List content entries containing a category."""
        with self._connect() as conn:
            # Use JSON contains check
            rows = conn.execute(
                """SELECT * FROM content 
                   WHERE categories LIKE ? 
                   ORDER BY ingested_at DESC LIMIT ?""",
                (f'%"{category}"%', limit)
            ).fetchall()
            
            return [self._row_to_entry(row) for row in rows]
    
    def search(self, query: str, limit: int = 20) -> list[ContentEntry]:
        """Full-text search across title, summary, and categories."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.* FROM content c
                JOIN content_fts fts ON c.id = fts.id
                WHERE content_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit)
            ).fetchall()
            
            return [self._row_to_entry(row) for row in rows]
    
    def get_action_items(
        self, 
        action_type: Optional[str] = None, 
        limit: int = 20
    ) -> list[tuple[ContentEntry, ActionItem]]:
        """Get action items across all content entries."""
        results = []
        
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM content 
                   WHERE status != 'archived' 
                   ORDER BY relevance_score DESC"""
            ).fetchall()
            
            for row in rows:
                entry = self._row_to_entry(row)
                for action in entry.action_items:
                    if action_type is None or action.action_type.value == action_type:
                        results.append((entry, action))
                        if len(results) >= limit:
                            return results
        
        return results
    
    def count_by_status(self) -> dict[str, int]:
        """Get count of entries by status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) FROM content GROUP BY status"
            ).fetchall()
            
            return {row[0]: row[1] for row in rows}
    
    def _row_to_entry(self, row: tuple) -> ContentEntry:
        """Convert a database row to ContentEntry."""
        return ContentEntry(
            id=row[0],
            url=row[1],
            title=row[2],
            summary=row[3],
            categories=json.loads(row[4]),
            relevance_score=row[5],
            action_items=[ActionItem.from_dict(a) for a in json.loads(row[6])],
            status=ContentStatus(row[7]),
            ingested_at=row[8],
            source_hash=row[9],
            raw_content=row[10],
        )
