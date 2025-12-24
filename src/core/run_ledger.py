"""
Deterministic Run Ledger (Prompt AH).

Append-only ledger capturing every irreversible decision.
No deletes, no edits. Ledger write occurs before side effects.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class LedgerWriteError(Exception):
    """Raised when ledger write fails."""
    pass


class LedgerTamperingError(Exception):
    """Raised when ledger tampering is detected."""
    pass


# Event types
EVENT_GROUNDHOG_REUSE = "GROUNDHOG_REUSE_DECISION"
EVENT_KILL_SWITCH = "KILL_SWITCH"
EVENT_REPORT_FINALIZED = "REPORT_FINALIZED"
EVENT_ABORT = "ABORT"
EVENT_OPERATOR_OVERRIDE = "OPERATOR_OVERRIDE"
EVENT_RED_LINE_VIOLATION = "RED_LINE_VIOLATION"
EVENT_PROACTIVE_ACTION = "PROACTIVE_ACTION"

VALID_EVENTS = {
    EVENT_GROUNDHOG_REUSE,
    EVENT_KILL_SWITCH,
    EVENT_REPORT_FINALIZED,
    EVENT_ABORT,
    EVENT_OPERATOR_OVERRIDE,
    EVENT_RED_LINE_VIOLATION,
    EVENT_PROACTIVE_ACTION,
}


class RunLedger:
    """
    Append-only run ledger for auditing.
    
    Records are immutable once written.
    """
    
    def __init__(self, storage_path: Optional[str] = None, run_id: Optional[str] = None):
        if storage_path is None:
            project_root = Path(__file__).parent.parent.parent
            storage_path = str(project_root / "data" / "run_ledger.jsonl")
        
        self.storage_path = Path(storage_path)
        self.run_id = run_id or str(uuid.uuid4())
        self._ensure_storage_exists()
        self._entry_count = self._count_entries()
    
    def _ensure_storage_exists(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.touch()
    
    def _count_entries(self) -> int:
        """Count existing ledger entries."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except FileNotFoundError:
            return 0
    
    def _compute_hash(self, payload: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of payload."""
        normalized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def append(
        self,
        event: str,
        actor: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append an immutable record to the ledger.
        
        Args:
            event: Event type (GROUNDHOG_REUSE_DECISION, KILL_SWITCH, etc.)
            actor: Who triggered the event (system, agent:<name>)
            payload: Optional payload data
            
        Returns:
            The created ledger record
            
        Raises:
            LedgerWriteError: If write fails
        """
        if event not in VALID_EVENTS:
            raise ValueError(f"Invalid event type: {event}. Valid: {VALID_EVENTS}")
        
        payload = payload or {}
        
        record = {
            "run_id": self.run_id,
            "event": event,
            "actor": actor,
            "hash": self._compute_hash(payload),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
            "sequence": self._entry_count,
        }
        
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
            self._entry_count += 1
            return record
        except Exception as e:
            raise LedgerWriteError(f"Ledger write failure: {e}")
    
    def get_entries(self, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all ledger entries, optionally filtered by run_id."""
        entries = []
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if run_id is None or entry.get("run_id") == run_id:
                            entries.append(entry)
        except FileNotFoundError:
            pass
        return entries
    
    def verify_integrity(self) -> bool:
        """
        Verify ledger integrity by checking sequence numbers.
        
        Returns:
            True if ledger is intact
            
        Raises:
            LedgerTamperingError: If tampering detected
        """
        entries = self.get_entries()
        
        # Group by run_id and verify sequences
        runs: Dict[str, List[Dict]] = {}
        for entry in entries:
            rid = entry.get("run_id", "unknown")
            if rid not in runs:
                runs[rid] = []
            runs[rid].append(entry)
        
        for rid, run_entries in runs.items():
            sorted_entries = sorted(run_entries, key=lambda x: x.get("sequence", 0))
            for i, entry in enumerate(sorted_entries):
                if entry.get("sequence") != i:
                    raise LedgerTamperingError(
                        f"Ledger tampering detected: sequence gap in run {rid}"
                    )
        
        return True


# Global ledger instance (initialized per run)
_CURRENT_LEDGER: Optional[RunLedger] = None


def get_ledger(run_id: Optional[str] = None) -> RunLedger:
    """Get or create the current run ledger."""
    global _CURRENT_LEDGER
    if _CURRENT_LEDGER is None or (run_id and _CURRENT_LEDGER.run_id != run_id):
        _CURRENT_LEDGER = RunLedger(run_id=run_id)
    return _CURRENT_LEDGER


def log_event(event: str, actor: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Log an event to the current run ledger."""
    return get_ledger().append(event, actor, payload)


def reset_ledger() -> None:
    """Reset the global ledger (for testing)."""
    global _CURRENT_LEDGER
    _CURRENT_LEDGER = None
