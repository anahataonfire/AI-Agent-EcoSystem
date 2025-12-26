"""
Routing Statistics for DTL v2.0

Numeric-only statistics for strategy routing.
IMPORTANT: Contains NO text, beliefs, or causal claims (DISABLE_LEARNING compliant).

Fields are strictly numeric:
- Counters (invocation_count)
- Timestamps (last_invoked_at)
- EMA weights (outcome_ema_weight) - frozen when DISABLE_LEARNING active
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import jsonschema


@dataclass
class RoutingStatEntry:
    """
    A single entry of routing statistics.
    
    All fields are NUMERIC ONLY (or timestamps).
    No text, beliefs, or causal claims allowed.
    """
    strategy_id: str
    invocation_count: int = 0
    last_invoked_at: Optional[str] = None
    outcome_ema_weight: float = 0.5  # Exponential moving average weight
    avg_latency_ms: int = 0
    success_rate_30d: float = 0.0
    last_updated_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = asdict(self)
        # Only include non-None values
        return {k: v for k, v in result.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RoutingStatEntry':
        return cls(
            strategy_id=data['strategy_id'],
            invocation_count=data.get('invocation_count', 0),
            last_invoked_at=data.get('last_invoked_at'),
            outcome_ema_weight=data.get('outcome_ema_weight', 0.5),
            avg_latency_ms=data.get('avg_latency_ms', 0),
            success_rate_30d=data.get('success_rate_30d', 0.0),
            last_updated_at=data.get('last_updated_at')
        )


class RoutingStatisticsStore:
    """
    Store for routing statistics with schema validation.
    
    DISABLE_LEARNING enforcement:
    - When active, all write operations are blocked
    - Reads are always allowed
    - EMA weights are frozen (not updated)
    """
    
    def __init__(
        self, 
        store_path: Optional[str] = None,
        schema_path: Optional[str] = None
    ):
        self._store_path = Path(store_path) if store_path else Path("data/routing_statistics.json")
        self._schema_path = Path(schema_path) if schema_path else Path("config/schemas/routing_statistics.json")
        self._entries: dict[str, RoutingStatEntry] = {}
        self._schema: Optional[dict] = None
        self._learning_disabled = False
        
        self._load_schema()
        self._load_entries()
    
    def _load_schema(self):
        """Load JSON Schema for validation."""
        if self._schema_path.exists():
            with open(self._schema_path, 'r') as f:
                self._schema = json.load(f)
    
    def _load_entries(self):
        """Load entries from disk."""
        if self._store_path.exists():
            try:
                with open(self._store_path, 'r') as f:
                    data = json.load(f)
                
                for entry_data in data.get("entries", []):
                    entry = RoutingStatEntry.from_dict(entry_data)
                    self._entries[entry.strategy_id] = entry
            except (json.JSONDecodeError, KeyError):
                pass  # Start fresh on error
    
    def _save_entries(self):
        """Save entries to disk."""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "2.0.0",
            "entries": [e.to_dict() for e in self._entries.values()],
            "last_updated_at": datetime.now(timezone.utc).isoformat()
        }
        with open(self._store_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def set_learning_disabled(self, disabled: bool):
        """Set DISABLE_LEARNING state."""
        self._learning_disabled = disabled
    
    def get(self, strategy_id: str) -> Optional[RoutingStatEntry]:
        """Get statistics for a strategy. Always allowed."""
        return self._entries.get(strategy_id)
    
    def get_all(self) -> list[RoutingStatEntry]:
        """Get all entries. Always allowed."""
        return list(self._entries.values())
    
    def record_invocation(
        self, 
        strategy_id: str,
        latency_ms: int,
        success: bool
    ) -> tuple[bool, Optional[str]]:
        """
        Record a strategy invocation.
        
        Returns (success, error_message).
        Blocked if DISABLE_LEARNING is active.
        """
        if self._learning_disabled:
            return False, "DISABLE_LEARNING active - writes blocked"
        
        now = datetime.now(timezone.utc).isoformat()
        
        if strategy_id not in self._entries:
            self._entries[strategy_id] = RoutingStatEntry(
                strategy_id=strategy_id,
                last_invoked_at=now,
                last_updated_at=now
            )
        
        entry = self._entries[strategy_id]
        
        # Update counters
        entry.invocation_count += 1
        entry.last_invoked_at = now
        entry.last_updated_at = now
        
        # Update EMA latency
        alpha = 0.1  # Smoothing factor
        entry.avg_latency_ms = int(
            alpha * latency_ms + (1 - alpha) * entry.avg_latency_ms
        )
        
        # Update success rate (simple 30-day approximation)
        # In production, this would use sliding window
        if success:
            entry.success_rate_30d = min(1.0, entry.success_rate_30d + 0.01)
        else:
            entry.success_rate_30d = max(0.0, entry.success_rate_30d - 0.02)
        
        # Validate before saving
        valid, error = self._validate_entry(entry)
        if not valid:
            return False, error
        
        self._save_entries()
        return True, None
    
    def update_ema_weight(
        self, 
        strategy_id: str, 
        new_weight: float
    ) -> tuple[bool, Optional[str]]:
        """
        Update EMA weight for a strategy.
        
        Blocked if DISABLE_LEARNING is active.
        """
        if self._learning_disabled:
            return False, "DISABLE_LEARNING active - EMA weights frozen"
        
        if strategy_id not in self._entries:
            return False, f"Strategy not found: {strategy_id}"
        
        if not 0.0 <= new_weight <= 1.0:
            return False, f"Weight must be 0-1, got {new_weight}"
        
        entry = self._entries[strategy_id]
        entry.outcome_ema_weight = new_weight
        entry.last_updated_at = datetime.now(timezone.utc).isoformat()
        
        self._save_entries()
        return True, None
    
    def _validate_entry(self, entry: RoutingStatEntry) -> tuple[bool, Optional[str]]:
        """Validate entry against schema."""
        if not self._schema:
            return True, None
        
        try:
            jsonschema.validate(entry.to_dict(), self._schema)
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e.message)
    
    def delete(self, strategy_id: str) -> bool:
        """Delete entry. Blocked if DISABLE_LEARNING active."""
        if self._learning_disabled:
            return False
        
        if strategy_id in self._entries:
            del self._entries[strategy_id]
            self._save_entries()
            return True
        return False
