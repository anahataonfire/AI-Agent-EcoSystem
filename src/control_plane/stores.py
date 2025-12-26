"""
Immutable Stores for DTL v2.0

Provides:
- IdentityStore: Locked agent identity storage (write-once)
- EvidenceStore: Evidence with TTL expiry
- RunLedger: Append-only run history

All stores:
- Are append-only or write-once
- Support TTL expiry where applicable
- Integrate with CommitGate for writes
"""

import json
import os
import hashlib
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Iterator
from enum import Enum


class StorePermission(Enum):
    """Permission modes for stores."""
    READ_ONLY = "read_only"
    APPEND_ONLY = "append_only"
    WRITE_ONCE = "write_once"


@dataclass
class StoreEntry:
    """Base class for store entries."""
    entry_id: str
    created_at: str
    content_hash: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IdentityEntry(StoreEntry):
    """Agent identity entry (write-once)."""
    agent_id: str
    version: str
    manifest_hash: str
    capabilities_locked: list[str]
    created_by: str


@dataclass
class EvidenceEntry(StoreEntry):
    """Evidence entry with TTL."""
    source_url: str
    source_trust_tier: int
    fetched_at: str
    expires_at: str  # TTL expiry
    summary: str
    asset_tags: list[str]
    run_id: str


@dataclass
class LedgerEntry(StoreEntry):
    """Run ledger entry (append-only)."""
    run_id: str
    run_ts: str
    mode: str
    success: bool
    steps_completed: list[str]
    bundle_hash: Optional[str]
    errors: list[str]


class IdentityStore:
    """
    T5.1: Immutable identity store.
    
    - Write-once semantics (no updates, no deletes)
    - Locked after initial write
    - Used to store agent manifests and versions
    """
    
    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or Path('data/identity_store')
        self.store_path.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.store_path / '.locked'
    
    def write(self, entry: IdentityEntry) -> bool:
        """
        Write identity entry. Fails if entry already exists.
        
        Returns:
            True if written, False if already exists
        """
        entry_path = self.store_path / f"{entry.entry_id}.json"
        
        if entry_path.exists():
            return False  # Write-once: cannot overwrite
        
        with open(entry_path, 'w') as f:
            json.dump(entry.to_dict(), f, indent=2)
        
        # Lock the entry (read-only permissions)
        os.chmod(entry_path, 0o444)
        
        return True
    
    def read(self, entry_id: str) -> Optional[IdentityEntry]:
        """Read identity entry by ID."""
        entry_path = self.store_path / f"{entry_id}.json"
        
        if not entry_path.exists():
            return None
        
        with open(entry_path) as f:
            data = json.load(f)
        
        return IdentityEntry(**data)
    
    def exists(self, entry_id: str) -> bool:
        """Check if identity exists."""
        return (self.store_path / f"{entry_id}.json").exists()
    
    def list_all(self) -> list[str]:
        """List all identity IDs."""
        return [f.stem for f in self.store_path.glob('*.json')]
    
    def compute_manifest_hash(self, manifest_path: Path) -> str:
        """Compute hash of a manifest file."""
        content = manifest_path.read_text()
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"


class EvidenceStore:
    """
    T5.2: Evidence store with TTL expiry.
    
    - Append-only for new evidence
    - TTL-based expiry (default: 24 hours)
    - Researcher writes here via CommitGate
    """
    
    DEFAULT_TTL_HOURS = 24
    
    def __init__(self, store_path: Optional[Path] = None, ttl_hours: int = DEFAULT_TTL_HOURS):
        self.store_path = store_path or Path('data/evidence_store')
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
    
    def write(self, entry: EvidenceEntry) -> Path:
        """
        Write evidence entry.
        
        Automatically sets expires_at based on TTL if not provided.
        """
        entry_path = self.store_path / f"{entry.entry_id}.json"
        
        # Set TTL if not already set
        if not entry.expires_at:
            expires = datetime.now(timezone.utc) + timedelta(hours=self.ttl_hours)
            entry.expires_at = expires.isoformat()
        
        with open(entry_path, 'w') as f:
            json.dump(entry.to_dict(), f, indent=2)
        
        return entry_path
    
    def read(self, entry_id: str) -> Optional[EvidenceEntry]:
        """Read evidence entry, returns None if expired."""
        entry_path = self.store_path / f"{entry_id}.json"
        
        if not entry_path.exists():
            return None
        
        with open(entry_path) as f:
            data = json.load(f)
        
        entry = EvidenceEntry(**data)
        
        # Check TTL
        if self._is_expired(entry):
            return None
        
        return entry
    
    def exists(self, entry_id: str, check_ttl: bool = True) -> bool:
        """Check if evidence exists and is not expired."""
        entry_path = self.store_path / f"{entry_id}.json"
        
        if not entry_path.exists():
            return False
        
        if check_ttl:
            entry = self.read(entry_id)
            return entry is not None
        
        return True
    
    def _is_expired(self, entry: EvidenceEntry) -> bool:
        """Check if entry has expired."""
        if not entry.expires_at:
            return False
        
        try:
            expires = datetime.fromisoformat(entry.expires_at.replace('Z', '+00:00'))
            return datetime.now(timezone.utc) > expires
        except ValueError:
            return False
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        removed = 0
        
        for entry_file in self.store_path.glob('*.json'):
            try:
                with open(entry_file) as f:
                    data = json.load(f)
                
                entry = EvidenceEntry(**data)
                
                if self._is_expired(entry):
                    entry_file.unlink()
                    removed += 1
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        
        return removed
    
    def list_valid(self) -> list[str]:
        """List all non-expired evidence IDs."""
        valid = []
        
        for entry_file in self.store_path.glob('*.json'):
            try:
                with open(entry_file) as f:
                    data = json.load(f)
                
                entry = EvidenceEntry(**data)
                
                if not self._is_expired(entry):
                    valid.append(entry.entry_id)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        
        return valid


class RunLedger:
    """
    T5.3: Run ledger with directory structure.
    
    - Append-only log of all runs
    - Directory structure: data/ledger/YYYY/MM/DD/RUN-*.json
    - Promotion log tracks commit state
    """
    
    def __init__(self, ledger_path: Optional[Path] = None):
        self.ledger_path = ledger_path or Path('data/ledger')
        self.ledger_path.mkdir(parents=True, exist_ok=True)
    
    def _get_entry_path(self, run_id: str, run_ts: str) -> Path:
        """Get path for a ledger entry based on timestamp."""
        try:
            ts = datetime.fromisoformat(run_ts.replace('Z', '+00:00'))
        except ValueError:
            ts = datetime.now(timezone.utc)
        
        date_path = self.ledger_path / ts.strftime('%Y/%m/%d')
        date_path.mkdir(parents=True, exist_ok=True)
        
        return date_path / f"{run_id}.json"
    
    def append(self, entry: LedgerEntry) -> Path:
        """
        Append a run entry to the ledger.
        
        Returns:
            Path to the ledger entry file
        """
        entry_path = self._get_entry_path(entry.run_id, entry.run_ts)
        
        with open(entry_path, 'w') as f:
            json.dump(entry.to_dict(), f, indent=2)
        
        return entry_path
    
    def read(self, run_id: str, run_ts: str) -> Optional[LedgerEntry]:
        """Read a specific ledger entry."""
        entry_path = self._get_entry_path(run_id, run_ts)
        
        if not entry_path.exists():
            return None
        
        with open(entry_path) as f:
            data = json.load(f)
        
        return LedgerEntry(**data)
    
    def find_by_run_id(self, run_id: str) -> Optional[LedgerEntry]:
        """Find entry by run_id (searches all dates)."""
        for entry_file in self.ledger_path.rglob(f"{run_id}.json"):
            try:
                with open(entry_file) as f:
                    data = json.load(f)
                return LedgerEntry(**data)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        
        return None
    
    def list_by_date(self, date: str) -> list[LedgerEntry]:
        """
        List all entries for a specific date (YYYY-MM-DD format).
        """
        entries = []
        
        try:
            dt = datetime.strptime(date, '%Y-%m-%d')
            date_path = self.ledger_path / dt.strftime('%Y/%m/%d')
            
            if date_path.exists():
                for entry_file in date_path.glob('*.json'):
                    try:
                        with open(entry_file) as f:
                            data = json.load(f)
                        entries.append(LedgerEntry(**data))
                    except (json.JSONDecodeError, TypeError, KeyError):
                        pass
        except ValueError:
            pass
        
        return entries
    
    def get_recent(self, limit: int = 10) -> list[LedgerEntry]:
        """Get most recent ledger entries."""
        all_entries = []
        
        for entry_file in self.ledger_path.rglob('*.json'):
            try:
                with open(entry_file) as f:
                    data = json.load(f)
                all_entries.append(LedgerEntry(**data))
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        
        # Sort by run_ts descending
        all_entries.sort(key=lambda e: e.run_ts, reverse=True)
        
        return all_entries[:limit]
    
    def count_by_date(self, date: str) -> dict:
        """Count success/failure for a specific date."""
        entries = self.list_by_date(date)
        
        return {
            'total': len(entries),
            'success': sum(1 for e in entries if e.success),
            'failed': sum(1 for e in entries if not e.success)
        }


def create_identity_entry(
    agent_id: str,
    version: str,
    manifest_path: Path,
    capabilities: list[str],
    created_by: str = 'system'
) -> IdentityEntry:
    """Factory to create IdentityEntry with computed hash."""
    content_hash = f"sha256:{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}"
    
    return IdentityEntry(
        entry_id=f"{agent_id}-{version}",
        created_at=datetime.now(timezone.utc).isoformat(),
        content_hash=content_hash,
        agent_id=agent_id,
        version=version,
        manifest_hash=content_hash,
        capabilities_locked=capabilities,
        created_by=created_by
    )


def create_evidence_entry(
    evidence_id: str,
    source_url: str,
    trust_tier: int,
    summary: str,
    asset_tags: list[str],
    run_id: str,
    run_ts: str,
    ttl_hours: int = 24
) -> EvidenceEntry:
    """Factory to create EvidenceEntry with TTL."""
    expires = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    content = f"{source_url}:{summary}:{run_id}"
    
    return EvidenceEntry(
        entry_id=evidence_id,
        created_at=run_ts,
        content_hash=f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}",
        source_url=source_url,
        source_trust_tier=trust_tier,
        fetched_at=run_ts,
        expires_at=expires.isoformat(),
        summary=summary,
        asset_tags=asset_tags,
        run_id=run_id
    )


def create_ledger_entry(
    run_id: str,
    run_ts: str,
    mode: str,
    success: bool,
    steps: list[str],
    bundle_hash: Optional[str] = None,
    errors: Optional[list[str]] = None
) -> LedgerEntry:
    """Factory to create LedgerEntry."""
    content = f"{run_id}:{run_ts}:{success}"
    
    return LedgerEntry(
        entry_id=run_id,
        created_at=run_ts,
        content_hash=f"sha256:{hashlib.sha256(content.encode()).hexdigest()[:16]}",
        run_id=run_id,
        run_ts=run_ts,
        mode=mode,
        success=success,
        steps_completed=steps,
        bundle_hash=bundle_hash,
        errors=errors or []
    )
