"""
Evidence Candidate Queue for DTL v2.0

Ephemeral buffer for evidence candidates from Researcher before Reporter processing.
This queue ensures:
1. No direct Researcher writes to EvidenceStore
2. Evidence validated before persistence
3. Queue cleared after each run (ephemeral)
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Iterator
from collections import deque
import hashlib


@dataclass
class EvidenceCandidate:
    """
    An evidence candidate from Researcher.
    
    This is NOT yet validated or persisted evidence.
    Must pass through Reporter → CommitGate before becoming real evidence.
    """
    evidence_id: str
    source_url: str
    source_trust_tier: int  # 1-4, 1=highest
    fetched_at: str
    summary: Optional[str] = None
    raw_content_hash: Optional[str] = None
    relevance_score: Optional[float] = None
    asset_tags: Optional[list[str]] = None
    
    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EvidenceCandidate':
        return cls(
            evidence_id=data['evidence_id'],
            source_url=data['source_url'],
            source_trust_tier=data['source_trust_tier'],
            fetched_at=data['fetched_at'],
            summary=data.get('summary'),
            raw_content_hash=data.get('raw_content_hash'),
            relevance_score=data.get('relevance_score'),
            asset_tags=data.get('asset_tags')
        )
    
    @staticmethod
    def generate_id() -> str:
        """Generate a unique evidence ID."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        hash_part = hashlib.sha256(ts.encode()).hexdigest()[:8].upper()
        return f"EV-{hash_part}{ts[-4:]}"


class EvidenceCandidateQueue:
    """
    Ephemeral queue for evidence candidates.
    
    Lifecycle:
    1. Researcher adds candidates via `enqueue()`
    2. Reporter pulls candidates via `dequeue()` or `peek()`
    3. Queue cleared at run end or on explicit `clear()`
    
    Thread-safety: Not thread-safe. Use in single-threaded pipeline only.
    """
    
    def __init__(self, max_size: int = 100, persist_path: Optional[str] = None):
        """
        Create queue.
        
        Args:
            max_size: Maximum candidates to hold. Oldest dropped if exceeded.
            persist_path: Optional path to persist queue state (for crash recovery).
        """
        self._queue: deque[EvidenceCandidate] = deque(maxlen=max_size)
        self._max_size = max_size
        self._persist_path = Path(persist_path) if persist_path else None
        self._total_enqueued = 0
        self._total_dequeued = 0
        
        # Load persisted state if exists
        if self._persist_path and self._persist_path.exists():
            self._load()
    
    def enqueue(self, candidate: EvidenceCandidate) -> bool:
        """
        Add a candidate to the queue.
        
        Returns True if added, False if duplicate (same evidence_id).
        """
        # Check for duplicate
        existing_ids = {c.evidence_id for c in self._queue}
        if candidate.evidence_id in existing_ids:
            return False
        
        self._queue.append(candidate)
        self._total_enqueued += 1
        
        if self._persist_path:
            self._persist()
        
        return True
    
    def dequeue(self) -> Optional[EvidenceCandidate]:
        """Remove and return the oldest candidate, or None if empty."""
        if not self._queue:
            return None
        
        candidate = self._queue.popleft()
        self._total_dequeued += 1
        
        if self._persist_path:
            self._persist()
        
        return candidate
    
    def dequeue_all(self) -> list[EvidenceCandidate]:
        """Remove and return all candidates."""
        candidates = list(self._queue)
        self._total_dequeued += len(candidates)
        self._queue.clear()
        
        if self._persist_path:
            self._persist()
        
        return candidates
    
    def peek(self) -> Optional[EvidenceCandidate]:
        """Return oldest candidate without removing, or None if empty."""
        return self._queue[0] if self._queue else None
    
    def peek_all(self) -> list[EvidenceCandidate]:
        """Return all candidates without removing."""
        return list(self._queue)
    
    def clear(self):
        """Clear all candidates from the queue."""
        self._queue.clear()
        
        if self._persist_path:
            self._persist()
    
    def __len__(self) -> int:
        return len(self._queue)
    
    def __bool__(self) -> bool:
        return len(self._queue) > 0
    
    def __iter__(self) -> Iterator[EvidenceCandidate]:
        return iter(self._queue)
    
    @property
    def stats(self) -> dict:
        """Return queue statistics."""
        return {
            "current_size": len(self._queue),
            "max_size": self._max_size,
            "total_enqueued": self._total_enqueued,
            "total_dequeued": self._total_dequeued,
            "dropped": max(0, self._total_enqueued - self._total_dequeued - len(self._queue))
        }
    
    def _persist(self):
        """Persist queue state to disk."""
        if not self._persist_path:
            return
        
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "candidates": [c.to_dict() for c in self._queue],
            "total_enqueued": self._total_enqueued,
            "total_dequeued": self._total_dequeued,
            "persisted_at": datetime.now(timezone.utc).isoformat()
        }
        with open(self._persist_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self):
        """Load queue state from disk."""
        if not self._persist_path or not self._persist_path.exists():
            return
        
        try:
            with open(self._persist_path, 'r') as f:
                data = json.load(f)
            
            for cd in data.get("candidates", []):
                self._queue.append(EvidenceCandidate.from_dict(cd))
            
            self._total_enqueued = data.get("total_enqueued", 0)
            self._total_dequeued = data.get("total_dequeued", 0)
        except (json.JSONDecodeError, KeyError):
            pass  # Start fresh on error
