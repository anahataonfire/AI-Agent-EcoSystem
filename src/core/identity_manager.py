"""
Authoritative Identity Store

This is the ONLY source of truth for agent identity facts.
Vector DBs, chat summaries, and LLM outputs are NOT authoritative.
All reads/writes must go through this module.

Key Invariants:
1. Write barrier: Only explicit_user, snapshot, admin sources allowed
2. Snapshot-first: Snapshot → Hash → Fact (never orphaned facts)
3. Bounded context: Max 500 chars when serialized for prompt
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Authoritative Identity Store location
DB_PATH = Path(__file__).parent.parent.parent / "data" / "authoritative_identity_store.db"

# Allowed source types for write barrier
ALLOWED_SOURCE_TYPES = frozenset({"explicit_user", "snapshot", "admin"})

# Max serialized size for identity context
MAX_CONTEXT_CHARS = 500

# Max number of identity facts (prevents creep)
MAX_FACT_COUNT = 10

# Max snapshot data size (bytes)
MAX_SNAPSHOT_SIZE = 10000


class IdentityManager:
    """
    Manages the Deterministic Identity Layer (DTL).
    
    Provides:
    - load_identity(): Load facts at run start
    - update_identity(): Persist facts with write barrier
    - create_snapshot(): Capture ground truth to Evidence Store
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    fact_key TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    snapshot_hash TEXT,
                    effective_from TEXT NOT NULL,
                    effective_to TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (fact_key, effective_from)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_hash TEXT PRIMARY KEY,
                    snapshot_data TEXT NOT NULL,
                    evidence_id TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
    
    def load_identity(self) -> Dict[str, Any]:
        """
        Load current identity facts.
        
        Returns:
            Dict of fact_key -> fact_value for all active (non-expired) facts
        """
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT fact_key, fact_value 
                FROM facts 
                WHERE effective_from <= ?
                  AND (effective_to IS NULL OR effective_to > ?)
            """, (now, now))
            
            facts = {}
            for row in cursor:
                try:
                    facts[row[0]] = json.loads(row[1])
                except json.JSONDecodeError:
                    facts[row[0]] = row[1]
            
            return facts
    
    def update_identity(
        self,
        fact_key: str,
        fact_value: Any,
        source_type: str,
        snapshot_hash: Optional[str] = None
    ) -> None:
        """
        Persist a fact with write barrier enforcement.
        
        Args:
            fact_key: Unique identifier for the fact
            fact_value: The fact data (must be JSON-serializable)
            source_type: One of {explicit_user, snapshot, admin}
            snapshot_hash: Required for snapshot-type facts
            
        Raises:
            ValueError: If source_type is not allowed or snapshot_hash missing
        """
        # WRITE BARRIER - Hard enforcement
        if source_type not in ALLOWED_SOURCE_TYPES:
            raise ValueError(
                f"Illegal source_type: '{source_type}'. "
                f"Allowed: {ALLOWED_SOURCE_TYPES}"
            )
        
        # Snapshot-first invariant
        if source_type == "snapshot" and not snapshot_hash:
            raise ValueError(
                "Snapshot facts require snapshot_hash. "
                "Create snapshot first, then reference its hash."
            )
        
        # Verify snapshot exists if referenced
        if snapshot_hash:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM snapshots WHERE snapshot_hash = ?",
                    (snapshot_hash,)
                )
                if not cursor.fetchone():
                    raise ValueError(
                        f"Snapshot hash '{snapshot_hash}' not found. "
                        "Snapshot must be created before fact can reference it."
                    )
        
        now = datetime.now(timezone.utc).isoformat()
        value_json = json.dumps(fact_value, default=str)
        
        # Enforce max fact count (admin exempt)
        if source_type != "admin":
            current_facts = self.load_identity()
            if fact_key not in current_facts and len(current_facts) >= MAX_FACT_COUNT:
                raise ValueError(
                    f"Identity fact limit exceeded (max {MAX_FACT_COUNT}). "
                    "Delete old facts or use admin source_type."
                )
        
        with sqlite3.connect(self.db_path) as conn:
            # Expire old version if exists
            conn.execute("""
                UPDATE facts SET effective_to = ?
                WHERE fact_key = ? AND effective_to IS NULL
            """, (now, fact_key))
            
            # Insert new version
            conn.execute("""
                INSERT INTO facts (
                    fact_key, fact_value, source_type, snapshot_hash,
                    effective_from, effective_to, created_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?)
            """, (fact_key, value_json, source_type, snapshot_hash, now, now))
            
            conn.commit()
    
    def create_snapshot(
        self,
        snapshot_data: Dict[str, Any],
        evidence_id: Optional[str] = None
    ) -> str:
        """
        Create a ground truth snapshot.
        
        Args:
            snapshot_data: The data to snapshot
            evidence_id: Optional reference to Evidence Store
            
        Returns:
            The SHA-256 hash of the snapshot (for referencing in facts)
        """
        data_json = json.dumps(snapshot_data, sort_keys=True, default=str)
        
        # Guard: prevent giant snapshots
        if len(data_json) > MAX_SNAPSHOT_SIZE:
            raise ValueError(
                f"Snapshot too large ({len(data_json)} bytes). "
                f"Max allowed: {MAX_SNAPSHOT_SIZE} bytes."
            )
        
        snapshot_hash = hashlib.sha256(data_json.encode()).hexdigest()[:32]  # 128 bits
        
        now = datetime.now(timezone.utc).isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Check if snapshot already exists (idempotent)
            cursor = conn.execute(
                "SELECT 1 FROM snapshots WHERE snapshot_hash = ?",
                (snapshot_hash,)
            )
            if not cursor.fetchone():
                conn.execute("""
                    INSERT INTO snapshots (
                        snapshot_hash, snapshot_data, evidence_id, created_at
                    ) VALUES (?, ?, ?, ?)
                """, (snapshot_hash, data_json, evidence_id, now))
                conn.commit()
        
        return snapshot_hash
    
    def serialize_for_prompt(self, facts: Dict[str, Any]) -> str:
        """
        Serialize identity context for prompt injection.
        
        Enforces MAX_CONTEXT_CHARS limit.
        
        Args:
            facts: Dict of facts to serialize
            
        Returns:
            Compact JSON string, truncated if necessary
        """
        if not facts:
            return ""
        
        serialized = json.dumps(facts, separators=(',', ':'), default=str)
        
        if len(serialized) > MAX_CONTEXT_CHARS:
            # Truncate with indicator
            serialized = serialized[:MAX_CONTEXT_CHARS - 15] + '..."truncated"}'
        
        return serialized
    
    def clear_all(self) -> int:
        """
        Clear all facts and snapshots. USE WITH CAUTION.
        
        Returns:
            Number of facts deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM facts")
            count = cursor.fetchone()[0]
            
            conn.execute("DELETE FROM facts")
            conn.execute("DELETE FROM snapshots")
            conn.commit()
            
        return count


# Module-level convenience functions
_default_manager: Optional[IdentityManager] = None


def get_manager() -> IdentityManager:
    """Get or create the default identity manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = IdentityManager()
    return _default_manager


def load_identity() -> Dict[str, Any]:
    """Load current identity facts."""
    return get_manager().load_identity()


def update_identity(
    fact_key: str,
    fact_value: Any,
    source_type: str,
    snapshot_hash: Optional[str] = None
) -> None:
    """Persist a fact with write barrier enforcement."""
    get_manager().update_identity(fact_key, fact_value, source_type, snapshot_hash)


def create_snapshot(
    snapshot_data: Dict[str, Any],
    evidence_id: Optional[str] = None
) -> str:
    """Create a ground truth snapshot."""
    return get_manager().create_snapshot(snapshot_data, evidence_id)


def serialize_for_prompt(facts: Dict[str, Any]) -> str:
    """Serialize identity context for prompt injection."""
    return get_manager().serialize_for_prompt(facts)
