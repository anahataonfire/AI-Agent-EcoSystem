"""
Long-Horizon Drift Harness (Prompt 6).

Detects slow autonomy decay across runs.
"""

import pytest
import tempfile
import os
import json
from typing import Dict, List


class DriftMetrics:
    """Metrics tracked across runs."""
    
    def __init__(self):
        self.skill_selections: List[str] = []
        self.abort_count: int = 0
        self.success_count: int = 0
        self.cost_usage: List[int] = []
        self.decision_log: List[Dict] = []
    
    def record_run(self, skill: str, aborted: bool, cost: int, decisions: List[str]):
        self.skill_selections.append(skill)
        if aborted:
            self.abort_count += 1
        else:
            self.success_count += 1
        self.cost_usage.append(cost)
        self.decision_log.append({
            "skill": skill,
            "aborted": aborted,
            "cost": cost,
            "decisions": decisions
        })
    
    def get_selection_stability(self) -> float:
        """How often the same skill is selected."""
        if len(self.skill_selections) < 2:
            return 1.0
        same_count = sum(
            1 for i in range(1, len(self.skill_selections))
            if self.skill_selections[i] == self.skill_selections[i-1]
        )
        return same_count / (len(self.skill_selections) - 1)
    
    def get_abort_frequency(self) -> float:
        total = self.abort_count + self.success_count
        if total == 0:
            return 0.0
        return self.abort_count / total
    
    def get_decision_entropy(self) -> float:
        """Measure decision variety (higher = more varied)."""
        from collections import Counter
        all_decisions = []
        for entry in self.decision_log:
            all_decisions.extend(entry.get("decisions", []))
        if not all_decisions:
            return 0.0
        counts = Counter(all_decisions)
        total = len(all_decisions)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * (p ** 0.5)  # Simplified entropy
        return abs(entropy)
    
    def to_dict(self) -> Dict:
        return {
            "total_runs": self.abort_count + self.success_count,
            "abort_count": self.abort_count,
            "success_count": self.success_count,
            "selection_stability": self.get_selection_stability(),
            "abort_frequency": self.get_abort_frequency(),
            "avg_cost": sum(self.cost_usage) / len(self.cost_usage) if self.cost_usage else 0,
            "decision_entropy": self.get_decision_entropy(),
        }


class TestLongHorizonDrift:
    """Tests for detecting autonomy decay over time."""

    def test_skill_selection_stability(self):
        """Skill selection should remain stable across runs."""
        from src.core.state_memory import StateMemory
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "memory.json")
            memory = StateMemory(storage_path=path, decay_runs=3)
            
            metrics = DriftMetrics()
            available_skills = ["skill_a", "skill_b", "skill_c"]
            query_hash = "test_query"
            
            # Run 10 times
            for i in range(10):
                # Get preferred skills
                preferred = memory.get_preferred_skills(query_hash, available_skills)
                selected = preferred[0] if preferred else available_skills[0]
                
                # Simulate run (success most of the time)
                aborted = (i % 5 == 4)  # Fail every 5th run
                cost = 10 + (i % 3)
                
                if not aborted:
                    memory.remember(query_hash, selected, "success")
                else:
                    memory.remember(query_hash, selected, "failure")
                
                metrics.record_run(selected, aborted, cost, [f"decision_{i}"])
                
                # Apply decay periodically
                if i % 3 == 0:
                    memory.apply_decay()
            
            # Stability should be reasonable (> 0.5)
            assert metrics.get_selection_stability() >= 0.5
            # Abort frequency should be low (< 0.3)
            assert metrics.get_abort_frequency() <= 0.3

    def test_no_non_deterministic_learning(self):
        """System should remain deterministic across runs."""
        from src.core.retry_strategy import (
            decide_retry, RetryState, RetryConfig, FailureClass
        )
        
        config = RetryConfig()
        
        decisions_run1 = []
        decisions_run2 = []
        
        # Run 1
        for failure_class in [FailureClass.TRANSIENT, FailureClass.RATE_LIMIT]:
            state = RetryState()
            d = decide_retry(failure_class, state, config)
            decisions_run1.append(d.should_retry)
        
        # Run 2 (identical inputs)
        for failure_class in [FailureClass.TRANSIENT, FailureClass.RATE_LIMIT]:
            state = RetryState()
            d = decide_retry(failure_class, state, config)
            decisions_run2.append(d.should_retry)
        
        # Should be identical
        assert decisions_run1 == decisions_run2


class TestDriftMetricsExport:
    """Tests for exporting drift metrics."""

    def test_metrics_are_machine_readable(self):
        """Drift metrics should export as valid JSON."""
        metrics = DriftMetrics()
        
        for i in range(5):
            metrics.record_run(
                skill=f"skill_{i % 2}",
                aborted=(i % 3 == 0),
                cost=10 + i,
                decisions=["decide_a", "decide_b"]
            )
        
        output = metrics.to_dict()
        
        # Should be JSON serializable
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        
        assert "total_runs" in parsed
        assert "abort_frequency" in parsed
        assert "selection_stability" in parsed
        assert parsed["total_runs"] == 5
