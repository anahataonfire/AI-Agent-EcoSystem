"""
Evidence Store for persisting and retrieving execution artifacts.

This module provides a simple but reliable way to store evidence from tool
executions. Evidence is stored as JSON with hash-based IDs for deduplication.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class EvidenceStore:
    """
    Persistent store for execution evidence and artifacts.
    
    Evidence is stored in a JSON file with hash-based IDs. This enables:
    - Deduplication of identical payloads
    - Fast retrieval by ID
    - Human-readable storage for debugging
    
    For production, consider migrating to SQLite or a proper database.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the evidence store.
        
        Args:
            storage_path: Path to the JSON storage file. 
                         Defaults to 'data/evidence_store.json' in project root.
        """
        if storage_path is None:
            # Default to project's data directory
            project_root = Path(__file__).parent.parent.parent
            storage_path = str(project_root / "data" / "evidence_store.json")
        
        self.storage_path = Path(storage_path)
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self) -> None:
        """Create storage file and parent directories if they don't exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._write_store({})
    
    def _read_store(self) -> Dict[str, Any]:
        """Read the entire store from disk."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _write_store(self, data: Dict[str, Any]) -> None:
        """Write the entire store to disk."""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    
    def _generate_id(self, payload: Dict[str, Any]) -> str:
        """
        Generate a hash-based ID for a payload.
        
        Uses SHA-256 truncated to 12 chars with 'ev_' prefix for readability.
        """
        # Sort keys for consistent hashing
        normalized = json.dumps(payload, sort_keys=True, default=str)
        hash_digest = hashlib.sha256(normalized.encode()).hexdigest()[:12]
        return f"ev_{hash_digest}"
    
    def save(self, payload: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Save a payload to the evidence store.
        
        Args:
            payload: The data to store (must be JSON-serializable)
            metadata: Optional metadata to attach (source, type, etc.)
        
        Returns:
            The hash-based ID of the stored evidence
        """
        evidence_id = self._generate_id(payload)
        
        store = self._read_store()
        store[evidence_id] = {
            "payload": payload,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write_store(store)
        
        return evidence_id
    
    def get(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve evidence by ID.
        
        Args:
            evidence_id: The ID returned from save()
        
        Returns:
            The stored payload, or None if not found
        """
        store = self._read_store()
        entry = store.get(evidence_id)
        
        if entry is None:
            return None
        
        return entry.get("payload")
    
    def get_with_metadata(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full evidence entry including metadata.
        
        Args:
            evidence_id: The ID returned from save()
        
        Returns:
            The full entry (payload, metadata, created_at), or None if not found
        """
        store = self._read_store()
        return store.get(evidence_id)
    
    def exists(self, evidence_id: str) -> bool:
        """Check if evidence exists by ID."""
        store = self._read_store()
        return evidence_id in store
    
    def list_ids(self) -> list:
        """List all evidence IDs in the store."""
        store = self._read_store()
        return list(store.keys())
    
    def delete(self, evidence_id: str) -> bool:
        """
        Delete evidence by ID.
        
        Returns:
            True if deleted, False if not found
        """
        store = self._read_store()
        if evidence_id in store:
            del store[evidence_id]
            self._write_store(store)
            return True
        return False
    
    def clear(self) -> int:
        """
        Clear all evidence from the store.
        
        Returns:
            Number of entries cleared
        """
        store = self._read_store()
        count = len(store)
        self._write_store({})
        return count
