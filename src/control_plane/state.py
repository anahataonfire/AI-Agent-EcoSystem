"""
System State Management for DTL v2.0

Manages the runtime state (NORMAL, DEGRADED, HALTED) with persistence
and transition rules.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import json
from pathlib import Path


class SystemState(Enum):
    """Runtime system states."""
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: SystemState
    to_state: SystemState
    reason: str
    timestamp: str
    operator_ack_required: bool


class StateManager:
    """
    Manages system state transitions and persistence.
    """
    
    def __init__(self, state_file: Optional[str] = None):
        self.state_file = Path(state_file) if state_file else Path("data/system_state.json")
        self._current_state = SystemState.NORMAL
        self._consecutive_failures = 0
        self._transitions: list[StateTransition] = []
        self._load_state()
    
    def _load_state(self):
        """Load persisted state if exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self._current_state = SystemState(data.get("state", "NORMAL"))
                    self._consecutive_failures = data.get("consecutive_failures", 0)
            except (json.JSONDecodeError, KeyError):
                self._current_state = SystemState.NORMAL
    
    def _save_state(self):
        """Persist current state."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump({
                "state": self._current_state.value,
                "consecutive_failures": self._consecutive_failures,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)
    
    @property
    def current_state(self) -> SystemState:
        return self._current_state
    
    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures
    
    def record_success(self):
        """Record a successful run, resetting failure count."""
        self._consecutive_failures = 0
        if self._current_state == SystemState.DEGRADED:
            self._transition_to(SystemState.NORMAL, "Success after degraded mode")
        self._save_state()
    
    def record_failure(self, reason: str) -> SystemState:
        """
        Record a failure and potentially transition to DEGRADED.
        Returns the new state.
        """
        self._consecutive_failures += 1
        
        if self._consecutive_failures >= 3 and self._current_state == SystemState.NORMAL:
            self._transition_to(SystemState.DEGRADED, f"3 consecutive failures: {reason}")
        
        self._save_state()
        return self._current_state
    
    def force_halt(self, reason: str):
        """Operator-initiated halt."""
        self._transition_to(SystemState.HALTED, f"Operator halt: {reason}")
        self._save_state()
    
    def resume_normal(self, operator_ack: str):
        """Resume normal operation after operator acknowledgment."""
        if self._current_state in (SystemState.DEGRADED, SystemState.HALTED):
            self._consecutive_failures = 0
            self._transition_to(SystemState.NORMAL, f"Operator resume: {operator_ack}")
            self._save_state()
    
    def _transition_to(self, new_state: SystemState, reason: str):
        """Record a state transition."""
        transition = StateTransition(
            from_state=self._current_state,
            to_state=new_state,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
            operator_ack_required=(new_state == SystemState.DEGRADED)
        )
        self._transitions.append(transition)
        self._current_state = new_state
        
        # Log the transition
        print(f"[STATE] {transition.from_state.value} -> {transition.to_state.value}: {reason}")
    
    def can_proceed(self) -> bool:
        """Check if the system can proceed with normal operations."""
        return self._current_state != SystemState.HALTED
    
    def is_degraded(self) -> bool:
        """Check if system is in degraded mode."""
        return self._current_state == SystemState.DEGRADED
