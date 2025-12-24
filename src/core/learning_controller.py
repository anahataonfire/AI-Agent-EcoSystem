"""
Learning Controller for Strategic Autonomy.

Controls all learning operations with kill switch integration.
When DISABLE_LEARNING is active:
- No Policy Memory writes
- No routing weight updates
- No counterfactual learning
- No decay application
- Execution proceeds with Bounded Autonomy defaults
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json


# Failure code for learning while disabled
DTL_STRAT_013 = "DTL-STRAT-013"


@dataclass
class LearningState:
    """Immutable learning state snapshot for a run."""
    learning_enabled: bool
    snapshot_time: str
    weights: Dict[str, float] = field(default_factory=dict)
    
    @staticmethod
    def default_weights() -> Dict[str, float]:
        """Return bounded autonomy default weights."""
        return {}  # Empty = all skills get weight 1.0


class LearningController:
    """
    Controls Strategic Autonomy learning with kill switch support.
    
    Kill switch is read ONCE at run start and immutable during run.
    """
    
    def __init__(self, ledger_func=None):
        """
        Initialize controller.
        
        Args:
            ledger_func: Function to log events (event: str, payload: dict)
        """
        self._ledger = ledger_func or self._default_ledger
        self._run_state: Optional[LearningState] = None
        self._ledger_entries = []
    
    def _default_ledger(self, event: str, payload: Dict[str, Any]):
        """Default ledger implementation for testing."""
        self._ledger_entries.append({"event": event, "payload": payload})
    
    def start_run(self, current_weights: Optional[Dict[str, float]] = None) -> LearningState:
        """
        Start a new run. Reads kill switch ONCE.
        
        Returns:
            Immutable LearningState for this run
        """
        from src.core.kill_switches import DISABLE_LEARNING
        
        learning_enabled = not DISABLE_LEARNING
        
        # Log the kill switch state
        self._ledger("LEARNING_STATE_READ", {
            "learning_enabled": learning_enabled,
            "source": "kill_switch"
        })
        
        # Create immutable state
        self._run_state = LearningState(
            learning_enabled=learning_enabled,
            snapshot_time=datetime.utcnow().isoformat(),
            weights=current_weights or LearningState.default_weights()
        )
        
        return self._run_state
    
    def can_learn(self) -> bool:
        """Check if learning is allowed for this run."""
        if self._run_state is None:
            return False
        return self._run_state.learning_enabled
    
    def apply_weight_update(
        self, 
        skill: str, 
        outcome: float,
        learning_rate: float = 0.2
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply EMA weight update.
        
        Returns:
            (success, failure_code)
        """
        if not self.can_learn():
            self._ledger("LEARNING_SKIPPED_DISABLED", {
                "skill": skill,
                "outcome": outcome,
                "reason": "kill_switch",
                "failure_code": DTL_STRAT_013
            })
            return False, DTL_STRAT_013
        
        # Apply EMA update
        old_weight = self._run_state.weights.get(skill, 1.0)
        new_weight = learning_rate * outcome + (1 - learning_rate) * old_weight
        new_weight = max(0.1, min(2.0, new_weight))
        
        # Log before mutation
        self._ledger("WEIGHT_UPDATE", {
            "skill": skill,
            "old": old_weight,
            "new": new_weight,
            "outcome": outcome
        })
        
        self._run_state.weights[skill] = new_weight
        return True, None
    
    def apply_decay(self, decay_rate: float = 0.95) -> Tuple[bool, Optional[str]]:
        """
        Apply time-based decay to all weights.
        
        Returns:
            (success, failure_code)
        """
        if not self.can_learn():
            self._ledger("LEARNING_SKIPPED_DISABLED", {
                "operation": "decay",
                "reason": "kill_switch",
                "failure_code": DTL_STRAT_013
            })
            return False, DTL_STRAT_013
        
        for skill in self._run_state.weights:
            old = self._run_state.weights[skill]
            self._run_state.weights[skill] = max(0.1, old * decay_rate)
        
        self._ledger("DECAY_APPLIED", {"decay_rate": decay_rate})
        return True, None
    
    def run_counterfactual(self, ledger_entries: list) -> Tuple[bool, Optional[str]]:
        """
        Run counterfactual evaluation.
        
        Returns:
            (success, failure_code)
        """
        if not self.can_learn():
            self._ledger("LEARNING_SKIPPED_DISABLED", {
                "operation": "counterfactual",
                "reason": "kill_switch",
                "failure_code": DTL_STRAT_013
            })
            return False, DTL_STRAT_013
        
        # Counterfactual logic would go here
        self._ledger("COUNTERFACTUAL_COMPLETE", {})
        return True, None
    
    def write_policy_memory(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        Write policy memory to disk.
        
        Returns:
            (success, failure_code)
        """
        if not self.can_learn():
            self._ledger("LEARNING_SKIPPED_DISABLED", {
                "operation": "policy_memory_write",
                "reason": "kill_switch",
                "failure_code": DTL_STRAT_013
            })
            return False, DTL_STRAT_013
        
        # Would write to disk in real implementation
        self._ledger("POLICY_MEMORY_WRITTEN", {"path": path})
        return True, None
    
    def get_ledger_entries(self) -> list:
        """Get all ledger entries (for testing)."""
        return self._ledger_entries
    
    def get_weights(self) -> Dict[str, float]:
        """Get current weights snapshot."""
        if self._run_state is None:
            return {}
        return dict(self._run_state.weights)
