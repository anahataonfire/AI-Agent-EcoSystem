"""
Query Cache for Groundhog Day deduplication.

Provides fast SQLite-based caching of query results to speed up
duplicate detection and reduce redundant work.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any


DB_PATH = Path("data/query_cache.db")


def _get_connection() -> sqlite3.Connection:
    """Get database connection, creating schema if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # Create schema
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_cache (
            query_hash TEXT PRIMARY KEY,
            report_id TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            evidence_count INTEGER DEFAULT 0,
            sources_json TEXT DEFAULT '[]'
        )
    """)
    
    # Create index for timestamp-based queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_completed_at 
        ON query_cache(completed_at)
    """)
    
    conn.commit()
    return conn


def cache_query(
    query_hash: str, 
    report_id: str, 
    evidence_count: int = 0,
    sources: list = None
):
    """
    Cache a completed query result.
    
    Args:
        query_hash: SHA256 hash of the query (first 16 chars)
        report_id: Evidence store ID for the report
        evidence_count: Number of evidence items collected
        sources: List of source names used
    """
    import json
    
    conn = _get_connection()
    sources_json = json.dumps(sources or [])
    
    conn.execute("""
        INSERT OR REPLACE INTO query_cache 
        (query_hash, report_id, completed_at, evidence_count, sources_json)
        VALUES (?, ?, ?, ?, ?)
    """, (
        query_hash, 
        report_id, 
        datetime.utcnow().isoformat() + "Z",
        evidence_count,
        sources_json
    ))
    
    conn.commit()
    conn.close()


def get_cached_report(
    query_hash: str, 
    max_age_minutes: int = 15
) -> Optional[str]:
    """
    Get cached report ID if fresh enough.
    
    Args:
        query_hash: SHA256 hash of the query
        max_age_minutes: Maximum age for cache hit
        
    Returns:
        Report ID if found and fresh, None otherwise
    """
    conn = _get_connection()
    cursor = conn.execute(
        "SELECT report_id, completed_at FROM query_cache WHERE query_hash = ?",
        (query_hash,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    report_id, completed_at_str = row
    
    # Parse timestamp and check freshness
    try:
        # Handle both 'Z' suffix and '+00:00' format
        if completed_at_str.endswith("Z"):
            completed_at_str = completed_at_str[:-1] + "+00:00"
        completed_at = datetime.fromisoformat(completed_at_str.replace("+00:00", ""))
        age = datetime.utcnow() - completed_at
        
        if age > timedelta(minutes=max_age_minutes):
            return None  # Cache expired
            
    except (ValueError, TypeError):
        return None  # Invalid timestamp
    
    return report_id


def get_cache_metadata(query_hash: str) -> Optional[Dict[str, Any]]:
    """
    Get full cache entry metadata.
    
    Args:
        query_hash: SHA256 hash of the query
        
    Returns:
        Dict with report_id, completed_at, evidence_count, sources
    """
    import json
    
    conn = _get_connection()
    cursor = conn.execute(
        """SELECT report_id, completed_at, evidence_count, sources_json 
           FROM query_cache WHERE query_hash = ?""",
        (query_hash,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    report_id, completed_at, evidence_count, sources_json = row
    
    return {
        "report_id": report_id,
        "completed_at": completed_at,
        "evidence_count": evidence_count,
        "sources": json.loads(sources_json) if sources_json else [],
    }


def invalidate_cache(query_hash: str):
    """
    Remove a cache entry.
    
    Args:
        query_hash: Hash of the query to invalidate
    """
    conn = _get_connection()
    conn.execute("DELETE FROM query_cache WHERE query_hash = ?", (query_hash,))
    conn.commit()
    conn.close()


def cleanup_stale_cache(max_age_hours: int = 24):
    """
    Remove cache entries older than specified age.
    
    Args:
        max_age_hours: Maximum age in hours (default 24)
    """
    conn = _get_connection()
    cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat() + "Z"
    
    cursor = conn.execute(
        "DELETE FROM query_cache WHERE completed_at < ?",
        (cutoff,)
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    
    return deleted


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Returns:
        Dict with entry_count, oldest_entry, newest_entry
    """
    conn = _get_connection()
    
    cursor = conn.execute("SELECT COUNT(*) FROM query_cache")
    count = cursor.fetchone()[0]
    
    cursor = conn.execute(
        "SELECT MIN(completed_at), MAX(completed_at) FROM query_cache"
    )
    row = cursor.fetchone()
    oldest, newest = row if row else (None, None)
    
    conn.close()
    
    return {
        "entry_count": count,
        "oldest_entry": oldest,
        "newest_entry": newest,
    }
