"""
Reset Frequency Guard for Strategic Autonomy.

Prevents hidden instability masked by repeated resets.
Tracks resets, emits warnings, and recommends operator action.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


# Failure code for reset instability
DTL_STRAT_014 = "DTL-STRAT-014"

# Thresholds
MAX_RESETS_PER_WINDOW = 5
RESET_WINDOW_SIZE = 500


@dataclass
class ResetEvent:
    """A policy memory reset event."""
    timestamp: str
    reason: str
    weights_before: Dict[str, float]
    weights_after: Dict[str, float]


@dataclass
class ResetWarning:
    """Warning for excessive resets."""
    warning_type: str
    severity: str
    reset_count: int
    window_size: int
    threshold: int
    recommendation: str
    failure_code: str


class ResetGuard:
    """
    Guards against hidden instability from repeated resets.
    
    - No automatic reset loops
    - No reset without ledger log
    - Emits warnings for operator attention
    """
    
    def __init__(self, ledger_func=None):
        """
        Initialize reset guard.
        
        Args:
            ledger_func: Function to log events
        """
        self._ledger = ledger_func or self._default_ledger
        self._reset_history: List[ResetEvent] = []
        self._ledger_entries = []
        self._run_count = 0
    
    def _default_ledger(self, event: str, payload: Dict[str, Any]):
        """Default ledger for testing."""
        self._ledger_entries.append({"event": event, "payload": payload})
    
    def increment_run(self):
        """Increment run counter."""
        self._run_count += 1
    
    def record_reset(
        self,
        reason: str,
        weights_before: Dict[str, float],
        weights_after: Dict[str, float]
    ) -> Optional[ResetWarning]:
        """
        Record a policy memory reset.
        
        ALWAYS logs to ledger before recording.
        Returns warning if threshold exceeded.
        """
        # Log BEFORE recording
        self._ledger("POLICY_MEMORY_RESET", {
            "reason": reason,
            "weights_before": weights_before,
            "weights_after": weights_after,
            "run_count": self._run_count
        })
        
        event = ResetEvent(
            timestamp=datetime.utcnow().isoformat(),
            reason=reason,
            weights_before=weights_before,
            weights_after=weights_after
        )
        
        self._reset_history.append(event)
        
        # Check threshold
        return self._check_threshold()
    
    def _check_threshold(self) -> Optional[ResetWarning]:
        """Check if reset threshold exceeded."""
        # Count resets in window
        window_start = max(0, self._run_count - RESET_WINDOW_SIZE)
        recent_resets = len(self._reset_history)  # Simplified: all resets in this session
        
        if recent_resets > MAX_RESETS_PER_WINDOW:
            warning = ResetWarning(
                warning_type="RESET_INSTABILITY",
                severity="WARNING",
                reset_count=recent_resets,
                window_size=RESET_WINDOW_SIZE,
                threshold=MAX_RESETS_PER_WINDOW,
                recommendation="Review policy memory configuration. Consider disabling learning.",
                failure_code=DTL_STRAT_014
            )
            
            self._ledger("RESET_INSTABILITY_WARNING", asdict(warning))
            return warning
        
        return None
    
    def get_reset_stats(self) -> Dict[str, Any]:
        """
        Get reset statistics for provenance footer and compliance export.
        """
        return {
            "total_resets": len(self._reset_history),
            "run_count": self._run_count,
            "reset_rate": len(self._reset_history) / max(1, self._run_count),
            "threshold": MAX_RESETS_PER_WINDOW,
            "window_size": RESET_WINDOW_SIZE,
            "recent_reasons": [r.reason for r in self._reset_history[-5:]]
        }
    
    def generate_provenance_section(self) -> str:
        """Generate provenance footer section for reset stats."""
        stats = self.get_reset_stats()
        
        lines = [
            "### Reset Statistics",
            f"- Total Resets: {stats['total_resets']}",
            f"- Reset Rate: {stats['reset_rate']:.4f} per run",
            f"- Threshold: {stats['threshold']} per {stats['window_size']} runs",
        ]
        
        if stats['recent_reasons']:
            lines.append(f"- Recent Reasons: {', '.join(stats['recent_reasons'][:3])}")
        
        return "\n".join(lines)
    
    def export_for_compliance(self) -> Dict[str, Any]:
        """Export reset data for compliance."""
        return {
            "reset_guard": {
                "stats": self.get_reset_stats(),
                "history": [asdict(r) for r in self._reset_history[-10:]],
                "warnings_issued": sum(
                    1 for e in self._ledger_entries 
                    if e["event"] == "RESET_INSTABILITY_WARNING"
                )
            }
        }
    
    def simulate_instability(self, count: int = 10) -> List[ResetWarning]:
        """
        Simulate instability for testing.
        
        Returns list of warnings generated.
        """
        warnings = []
        
        for i in range(count):
            self._run_count += 1
            warning = self.record_reset(
                reason=f"weight_collapse_{i}",
                weights_before={"a": 0.1, "b": 0.1},
                weights_after={"a": 1.0, "b": 1.0}
            )
            if warning:
                warnings.append(warning)
        
        return warnings
