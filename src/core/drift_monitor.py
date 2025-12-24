"""
Drift Monitoring & Alerting for Strategic Autonomy.

Detects long-horizon strategic drift before it becomes failure.
Metrics are computed post-run, stored append-only, and non-invasive.
"""

import json
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


# Alert thresholds
DOMINANCE_THRESHOLD = 0.65
DOMINANCE_RUN_WINDOW = 100
RESET_THRESHOLD_PER_RUNS = 500
ENTROPY_COLLAPSE_THRESHOLD = 0.4


@dataclass
class DriftMetrics:
    """Drift metrics for a single run."""
    run_id: str
    timestamp: str
    routing_entropy: float
    skill_dominance_ratio: float
    dominant_skill: str
    reset_occurred: bool
    counterfactual_delta_avg: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DriftAlert:
    """A drift alert."""
    alert_type: str
    severity: str
    message: str
    threshold: float
    actual_value: float
    run_window: int


class DriftMonitor:
    """
    Monitors strategic drift.
    
    Alerts do NOT abort execution.
    All metrics are read-only and non-invasive.
    """
    
    def __init__(self, metrics_path: Optional[str] = None, ledger_func=None):
        """
        Initialize drift monitor.
        
        Args:
            metrics_path: Path to drift_metrics.json (append-only)
            ledger_func: Function to log events
        """
        self.metrics_path = Path(metrics_path) if metrics_path else None
        self._ledger = ledger_func or self._default_ledger
        self._metrics_history: List[DriftMetrics] = []
        self._ledger_entries = []
    
    def _default_ledger(self, event: str, payload: Dict[str, Any]):
        """Default ledger for testing."""
        self._ledger_entries.append({"event": event, "payload": payload})
    
    def compute_entropy(self, weights: Dict[str, float]) -> float:
        """Compute Shannon entropy of weight distribution."""
        if not weights:
            return 0.0
        
        total = sum(weights.values())
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for w in weights.values():
            if w > 0:
                p = w / total
                entropy -= p * math.log2(p)
        
        return entropy
    
    def compute_dominance(self, weights: Dict[str, float]) -> tuple:
        """
        Compute skill dominance ratio.
        
        Returns:
            (dominant_skill, dominance_ratio)
        """
        if not weights:
            return ("none", 0.0)
        
        total = sum(weights.values())
        if total == 0:
            return ("none", 0.0)
        
        dominant = max(weights.keys(), key=lambda k: weights[k])
        ratio = weights[dominant] / total
        
        return (dominant, ratio)
    
    def record_metrics(
        self,
        run_id: str,
        weights: Dict[str, float],
        reset_occurred: bool = False,
        counterfactual_delta: float = 0.0
    ) -> DriftMetrics:
        """
        Record metrics for a run.
        
        Metrics are deterministically ordered and snapshot-based.
        """
        entropy = self.compute_entropy(weights)
        dominant_skill, dominance = self.compute_dominance(weights)
        
        metrics = DriftMetrics(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat(),
            routing_entropy=entropy,
            skill_dominance_ratio=dominance,
            dominant_skill=dominant_skill,
            reset_occurred=reset_occurred,
            counterfactual_delta_avg=counterfactual_delta
        )
        
        self._metrics_history.append(metrics)
        
        # Append to file if configured
        if self.metrics_path:
            self._append_to_file(metrics)
        
        return metrics
    
    def _append_to_file(self, metrics: DriftMetrics):
        """Append metrics to JSON file."""
        try:
            if self.metrics_path.exists():
                with open(self.metrics_path, "r") as f:
                    data = json.load(f)
            else:
                data = {"runs": []}
            
            data["runs"].append(metrics.to_dict())
            
            with open(self.metrics_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self._ledger("DRIFT_METRICS_WRITE_ERROR", {"error": str(e)})
    
    def check_alerts(self) -> List[DriftAlert]:
        """
        Check for drift alerts based on recent history.
        
        Alerts are emitted but do NOT abort execution.
        """
        alerts = []
        
        if len(self._metrics_history) < DOMINANCE_RUN_WINDOW:
            return alerts
        
        recent = self._metrics_history[-DOMINANCE_RUN_WINDOW:]
        
        # Check single skill dominance
        dominant_counts: Dict[str, int] = {}
        for m in recent:
            if m.skill_dominance_ratio > DOMINANCE_THRESHOLD:
                dominant_counts[m.dominant_skill] = dominant_counts.get(m.dominant_skill, 0) + 1
        
        for skill, count in dominant_counts.items():
            if count >= DOMINANCE_RUN_WINDOW * 0.8:  # 80% of window
                alert = DriftAlert(
                    alert_type="SKILL_DOMINANCE",
                    severity="WARNING",
                    message=f"Skill '{skill}' dominated {count}/{DOMINANCE_RUN_WINDOW} runs",
                    threshold=DOMINANCE_THRESHOLD,
                    actual_value=count / DOMINANCE_RUN_WINDOW,
                    run_window=DOMINANCE_RUN_WINDOW
                )
                alerts.append(alert)
                self._ledger("DRIFT_ALERT", asdict(alert))
        
        # Check reset frequency
        reset_count = sum(1 for m in recent if m.reset_occurred)
        expected_resets = DOMINANCE_RUN_WINDOW / RESET_THRESHOLD_PER_RUNS
        if reset_count > expected_resets * 2:  # 2x expected
            alert = DriftAlert(
                alert_type="RESET_FREQUENCY",
                severity="WARNING",
                message=f"High reset frequency: {reset_count} in {DOMINANCE_RUN_WINDOW} runs",
                threshold=expected_resets,
                actual_value=reset_count,
                run_window=DOMINANCE_RUN_WINDOW
            )
            alerts.append(alert)
            self._ledger("DRIFT_ALERT", asdict(alert))
        
        # Check entropy collapse
        avg_entropy = sum(m.routing_entropy for m in recent) / len(recent)
        if avg_entropy < ENTROPY_COLLAPSE_THRESHOLD:
            alert = DriftAlert(
                alert_type="ENTROPY_COLLAPSE",
                severity="WARNING",
                message=f"Low routing entropy: {avg_entropy:.3f}",
                threshold=ENTROPY_COLLAPSE_THRESHOLD,
                actual_value=avg_entropy,
                run_window=DOMINANCE_RUN_WINDOW
            )
            alerts.append(alert)
            self._ledger("DRIFT_ALERT", asdict(alert))
        
        return alerts
    
    def get_metrics_history(self) -> List[DriftMetrics]:
        """Get all recorded metrics."""
        return list(self._metrics_history)
    
    def export_for_dashboard(self) -> Dict[str, Any]:
        """Export metrics for ops dashboards."""
        if not self._metrics_history:
            return {"runs": [], "summary": {}}
        
        recent = self._metrics_history[-100:] if len(self._metrics_history) > 100 else self._metrics_history
        
        return {
            "runs": [m.to_dict() for m in recent],
            "summary": {
                "total_runs": len(self._metrics_history),
                "avg_entropy": sum(m.routing_entropy for m in recent) / len(recent),
                "reset_count": sum(1 for m in recent if m.reset_occurred),
                "dominant_skills": list(set(m.dominant_skill for m in recent))
            }
        }
