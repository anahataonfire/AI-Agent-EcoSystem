"""
Evidence Store - SQLite Backend (P0 Migration)

This module provides a reliable, production-ready evidence store using SQLite:
- Atomic writes with transactions
- Hash-based deduplication with payload_hash
- Indexed queries on evidence_id, query_hash, lifecycle
- Race condition prevention via SQLite locking
- Backward compatible API with JSON version

Migrated from JSON to address corruption and concurrency risks.
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# MALICIOUS PAYLOAD SANITIZATION (Prompt X) - Preserved from original
# ============================================================================

class MaliciousPayloadError(Exception):
    """Raised when a payload contains malicious content that cannot be sanitized."""
    pass


# Patterns for instruction smuggling detection
INSTRUCTION_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"^System:", re.MULTILINE),
    re.compile(r"^Assistant:", re.MULTILINE),
    re.compile(r"You are ChatGPT", re.IGNORECASE),
    re.compile(r"^Human:", re.MULTILINE),
    re.compile(r"```[^`]*\b(do|execute|run|perform|ignore|override)\b[^`]*```", re.IGNORECASE | re.DOTALL),
]

# Patterns that must trigger outright rejection
FOOTER_SPOOF_PATTERN = re.compile(r"###\s*Execution\s+Provenance", re.IGNORECASE)
IDENTITY_INJECTION_PATTERN = re.compile(r"\[\[IDENTITY_FACTS_READ_ONLY\]\]")

# Pattern for citation token scrubbing
CITATION_TOKEN_PATTERN = re.compile(r"\[EVID:[a-zA-Z0-9:_-]+\]")


def sanitize_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Sanitize a payload by removing malicious content.
    
    Args:
        payload: The payload dict to sanitize
        
    Returns:
        Tuple of (sanitized_payload, was_sanitized)
        
    Raises:
        MaliciousPayloadError: If payload contains footer spoof or identity injection
    """
    if not payload:
        return payload, False
    
    was_sanitized = False
    sanitized = {}
    
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized_value, field_sanitized = _sanitize_string(value)
            sanitized[key] = sanitized_value
            if field_sanitized:
                was_sanitized = True
        elif isinstance(value, dict):
            nested, nested_sanitized = sanitize_payload(value)
            sanitized[key] = nested
            if nested_sanitized:
                was_sanitized = True
        else:
            sanitized[key] = value
    
    return sanitized, was_sanitized


def _sanitize_string(text: str) -> Tuple[str, bool]:
    """
    Sanitize a single string value.
    
    Returns:
        Tuple of (sanitized_text, was_sanitized)
        
    Raises:
        MaliciousPayloadError: If text contains footer spoof or identity injection
    """
    # Check for footer spoofing - reject outright
    if FOOTER_SPOOF_PATTERN.search(text):
        raise MaliciousPayloadError("Footer spoofing detected: Execution Provenance in payload")
    
    # Check for identity injection - reject outright
    if IDENTITY_INJECTION_PATTERN.search(text):
        raise MaliciousPayloadError("Malicious identity injection attempt detected")
    
    was_sanitized = False
    result = text
    
    # Strip instruction patterns
    for pattern in INSTRUCTION_PATTERNS:
        if pattern.search(result):
            result = pattern.sub("[REDACTED]", result)
            was_sanitized = True
    
    # Scrub citation tokens
    if CITATION_TOKEN_PATTERN.search(result):
        result = CITATION_TOKEN_PATTERN.sub("[CITATION_REMOVED]", result)
        was_sanitized = True
    
    return result, was_sanitized


# ============================================================================
# SQLITE EVIDENCE STORE
# ============================================================================

DB_PATH = Path(__file__).parent.parent.parent / "data" / "evidence_store.db"


def _get_connection() -> sqlite3.Connection:
    """Get database connection with schema initialization."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Create schema
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            metadata_json TEXT DEFAULT '{}',
            query_hash TEXT,
            source_url TEXT,
            source_trust_tier INTEGER DEFAULT 3,
            lifecycle TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            sanitized INTEGER DEFAULT 0
        );
        
        CREATE INDEX IF NOT EXISTS idx_evidence_query_hash 
        ON evidence(query_hash);
        
        CREATE INDEX IF NOT EXISTS idx_evidence_lifecycle 
        ON evidence(lifecycle);
        
        CREATE INDEX IF NOT EXISTS idx_evidence_payload_hash 
        ON evidence(payload_hash);
        
        CREATE INDEX IF NOT EXISTS idx_evidence_created_at 
        ON evidence(created_at);
    """)
    conn.commit()
    return conn


def _compute_payload_hash(payload: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of normalized payload for deduplication."""
    normalized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


class EvidenceStore:
    """
    Production-grade evidence store backed by SQLite.
    
    Features:
    - Atomic writes with transactions
    - Hash-based deduplication (payload_hash)
    - Indexed queries (evidence_id, query_hash, lifecycle, created_at)
    - WAL mode for concurrent access
    - Backward compatible API
    
    Evidence lifecycle states:
    - active: Available for citation
    - expired: Old, should not be cited
    - revoked: Explicitly invalidated
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the evidence store.
        
        Args:
            storage_path: Optional custom path to SQLite database.
                         Defaults to 'data/evidence_store.db'
        """
        if storage_path:
            self.db_path = Path(storage_path)
        else:
            self.db_path = DB_PATH
        
        # Ensure DB is initialized
        self._get_conn()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Create schema if needed
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evidence (
                evidence_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}',
                query_hash TEXT,
                source_url TEXT,
                source_trust_tier INTEGER DEFAULT 3,
                lifecycle TEXT DEFAULT 'active',
                created_at TEXT NOT NULL,
                sanitized INTEGER DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_evidence_query_hash 
            ON evidence(query_hash);
            
            CREATE INDEX IF NOT EXISTS idx_evidence_lifecycle 
            ON evidence(lifecycle);
            
            CREATE INDEX IF NOT EXISTS idx_evidence_payload_hash 
            ON evidence(payload_hash);
            
            CREATE INDEX IF NOT EXISTS idx_evidence_created_at 
            ON evidence(created_at);
        """)
        conn.commit()
        return conn
    
    def _generate_id(self, payload: Dict[str, Any]) -> str:
        """Generate a hash-based ID for a payload."""
        hash_digest = _compute_payload_hash(payload)[:12]
        return f"ev_{hash_digest}"
    
    def save(
        self, 
        payload: Dict[str, Any], 
        metadata: Optional[Dict[str, Any]] = None, 
        custom_id: Optional[str] = None
    ) -> str:
        """
        Save a payload to the evidence store.
        
        Args:
            payload: The data to store (must be JSON-serializable)
            metadata: Optional metadata (source_url, query_hash, lifecycle, etc.)
            custom_id: Optional manual ID (e.g. for deterministic final reports)
        
        Returns:
            The evidence_id of the stored evidence
            
        Raises:
            MaliciousPayloadError: If payload contains forbidden content
        """
        # Sanitize payload before storage
        sanitized_payload, was_sanitized = sanitize_payload(payload)
        
        # Compute hashes
        payload_hash = _compute_payload_hash(sanitized_payload)
        evidence_id = custom_id if custom_id else self._generate_id(sanitized_payload)
        
        # Prepare metadata
        meta = metadata.copy() if metadata else {}
        if was_sanitized:
            meta["sanitized"] = True
        
        # Extract indexed fields from metadata
        query_hash = meta.pop("query_hash", None)
        source_url = meta.pop("source_url", None)
        source_trust_tier = meta.pop("source_trust_tier", 3)
        lifecycle = meta.pop("lifecycle", "active")
        
        now = datetime.now(timezone.utc).isoformat()
        
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO evidence 
                (evidence_id, payload_json, payload_hash, metadata_json, 
                 query_hash, source_url, source_trust_tier, lifecycle, 
                 created_at, sanitized)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence_id,
                json.dumps(sanitized_payload, default=str),
                payload_hash,
                json.dumps(meta, default=str),
                query_hash,
                source_url,
                source_trust_tier,
                lifecycle,
                now,
                1 if was_sanitized else 0
            ))
            conn.commit()
        finally:
            conn.close()
        
        return evidence_id
    
    def get(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve evidence payload by ID.
        
        Args:
            evidence_id: The ID returned from save()
        
        Returns:
            The stored payload, or None if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT payload_json FROM evidence WHERE evidence_id = ?",
                (evidence_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["payload_json"])
            return None
        finally:
            conn.close()
    
    def get_with_metadata(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full evidence entry including metadata.
        
        Args:
            evidence_id: The ID returned from save()
        
        Returns:
            Dict with payload, metadata, created_at, etc. or None
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM evidence WHERE evidence_id = ?",
                (evidence_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "evidence_id": row["evidence_id"],
                    "payload": json.loads(row["payload_json"]),
                    "payload_hash": row["payload_hash"],
                    "metadata": json.loads(row["metadata_json"]),
                    "query_hash": row["query_hash"],
                    "source_url": row["source_url"],
                    "source_trust_tier": row["source_trust_tier"],
                    "lifecycle": row["lifecycle"],
                    "created_at": row["created_at"],
                    "sanitized": bool(row["sanitized"]),
                }
            return None
        finally:
            conn.close()
    
    def exists(self, evidence_id: str) -> bool:
        """Check if evidence exists by ID."""
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT 1 FROM evidence WHERE evidence_id = ?",
                (evidence_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    def list_ids(self) -> List[str]:
        """List all evidence IDs in the store."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT evidence_id FROM evidence")
            return [row["evidence_id"] for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def find_by_query_hash(self, query_hash: str, lifecycle: str = "active") -> List[str]:
        """
        Find all evidence IDs for a given query hash.
        
        Args:
            query_hash: The query hash to search for
            lifecycle: Filter by lifecycle state (default: active)
        
        Returns:
            List of evidence IDs
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT evidence_id FROM evidence WHERE query_hash = ? AND lifecycle = ?",
                (query_hash, lifecycle)
            )
            return [row["evidence_id"] for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def find_by_payload_hash(self, payload_hash: str) -> Optional[str]:
        """
        Find evidence by payload hash (deduplication check).
        
        Args:
            payload_hash: SHA-256 hash of the payload
        
        Returns:
            evidence_id if duplicate exists, None otherwise
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "SELECT evidence_id FROM evidence WHERE payload_hash = ? LIMIT 1",
                (payload_hash,)
            )
            row = cursor.fetchone()
            return row["evidence_id"] if row else None
        finally:
            conn.close()
    
    def update_lifecycle(self, evidence_id: str, lifecycle: str) -> bool:
        """
        Update the lifecycle state of evidence.
        
        Args:
            evidence_id: The evidence to update
            lifecycle: New state: 'active', 'expired', or 'revoked'
        
        Returns:
            True if updated, False if not found
        """
        if lifecycle not in ("active", "expired", "revoked"):
            raise ValueError(f"Invalid lifecycle: {lifecycle}")
        
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "UPDATE evidence SET lifecycle = ? WHERE evidence_id = ?",
                (lifecycle, evidence_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def delete(self, evidence_id: str) -> bool:
        """
        Delete evidence by ID.
        
        Returns:
            True if deleted, False if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM evidence WHERE evidence_id = ?",
                (evidence_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def clear(self) -> int:
        """
        Clear all evidence from the store.
        
        Returns:
            Number of entries cleared
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM evidence")
            count = cursor.fetchone()["cnt"]
            conn.execute("DELETE FROM evidence")
            conn.commit()
            return count
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dict with counts and breakdown by lifecycle
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("SELECT COUNT(*) as total FROM evidence")
            total = cursor.fetchone()["total"]
            
            cursor = conn.execute("""
                SELECT lifecycle, COUNT(*) as count 
                FROM evidence 
                GROUP BY lifecycle
            """)
            by_lifecycle = {row["lifecycle"]: row["count"] for row in cursor.fetchall()}
            
            cursor = conn.execute("SELECT COUNT(*) as sanitized FROM evidence WHERE sanitized = 1")
            sanitized = cursor.fetchone()["sanitized"]
            
            return {
                "total": total,
                "by_lifecycle": by_lifecycle,
                "sanitized_count": sanitized,
            }
        finally:
            conn.close()
