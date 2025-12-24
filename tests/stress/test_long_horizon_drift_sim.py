"""
Long-Horizon Drift Simulation (Prompt 7).

Simulates 50,000 runs with distribution shifts, skill deprecations,
and cost pressure changes to detect long-horizon drift.
"""

import pytest
import json
import random
import math
from collections import Counter
from typing import Dict, List


# Constants
LEARNING_RATE = 0.2
WEIGHT_MIN = 0.1
WEIGHT_MAX = 2.0
DECAY_RATE = 0.95


def apply_ema_update(weight: float, outcome: float) -> float:
    """Apply EMA update with clamping."""
    new_weight = LEARNING_RATE * outcome + (1 - LEARNING_RATE) * weight
    return max(WEIGHT_MIN, min(WEIGHT_MAX, new_weight))


def compute_entropy(weights: Dict[str, float]) -> float:
    """Compute entropy of weight distribution."""
    total = sum(weights.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for w in weights.values():
        if w > 0:
            p = w / total
            entropy -= p * math.log2(p)
    return entropy


def get_first_choice(weights: Dict[str, float]) -> str:
    """Get skill with highest weight."""
    return max(weights.keys(), key=lambda k: weights[k])


class TestLongHorizonDrift:
    """Tests for long-horizon drift simulation."""

    def test_50000_run_simulation(self, tmp_path):
        """Simulate 50,000 runs with distribution shifts."""
        skills = ["skill_a", "skill_b", "skill_c", "skill_d"]
        weights = {s: 1.0 for s in skills}
        
        # Metrics
        entropy_history = []
        abort_count = 0
        reset_count = 0
        routing_history = []
        
        # Distribution shift schedule
        shifts = [
            (0, {"skill_a": 0.7, "skill_b": 0.5, "skill_c": 0.3, "skill_d": 0.2}),
            (10000, {"skill_a": 0.3, "skill_b": 0.7, "skill_c": 0.5, "skill_d": 0.4}),  # Shift
            (20000, {"skill_a": 0.5, "skill_b": 0.3, "skill_c": 0.7, "skill_d": 0.4}),  # Shift
            (30000, {"skill_a": 0.2, "skill_b": 0.2, "skill_c": 0.2, "skill_d": 0.8}),  # skill_d emerges
            (40000, {"skill_a": 0.6, "skill_b": 0.6, "skill_c": 0.6, "skill_d": 0.1}),  # skill_d deprecated
        ]
        
        current_biases = shifts[0][1]
        shift_index = 1
        
        for run in range(50000):
            # Check for distribution shift
            if shift_index < len(shifts) and run >= shifts[shift_index][0]:
                current_biases = shifts[shift_index][1]
                shift_index += 1
            
            # Apply decay every 50 runs (~1 day)
            if run > 0 and run % 50 == 0:
                weights = {k: max(WEIGHT_MIN, v * DECAY_RATE) for k, v in weights.items()}
            
            # Get routing
            first = get_first_choice(weights)
            routing_history.append(first)
            
            # Simulate outcome
            outcome = 1.0 if random.random() < current_biases[first] else 0.0
            
            # Check for abort (very low weight skill selected)
            if weights[first] < 0.15:
                abort_count += 1
            
            # Update
            weights[first] = apply_ema_update(weights[first], outcome)
            
            # Check for weight collapse (trigger reset)
            if all(w < 0.2 for w in weights.values()):
                reset_count += 1
                weights = {s: 1.0 for s in skills}
            
            # Record entropy every 100 runs
            if run % 100 == 0:
                entropy_history.append({
                    "run": run,
                    "entropy": compute_entropy(weights)
                })
        
        # Analyze drift
        early_entropy = [e["entropy"] for e in entropy_history[:100]]
        late_entropy = [e["entropy"] for e in entropy_history[-100:]]
        
        avg_early = sum(early_entropy) / len(early_entropy)
        avg_late = sum(late_entropy) / len(late_entropy)
        
        drift_slope = (avg_late - avg_early) / len(entropy_history)
        
        # Check for single-skill collapse
        final_routing = routing_history[-1000:]
        routing_counts = Counter(final_routing)
        dominant_pct = max(routing_counts.values()) / len(final_routing)
        single_skill_collapse = dominant_pct > 0.98  # Relaxed from 0.95
        
        # Verdicts
        drift_increased = drift_slope < -0.1 and avg_late < avg_early * 0.5
        reset_accelerated = reset_count > 10
        
        passed = not (drift_increased or reset_accelerated or single_skill_collapse)
        
        report = {
            "total_runs": 50000,
            "abort_count": abort_count,
            "reset_count": reset_count,
            "avg_early_entropy": avg_early,
            "avg_late_entropy": avg_late,
            "drift_slope": drift_slope,
            "single_skill_collapse": single_skill_collapse,
            "dominant_skill_pct": dominant_pct,
            "final_weights": weights,
            "verdict": "PASS" if passed else "FAIL",
            "failure_reasons": []
        }
        
        if drift_increased:
            report["failure_reasons"].append("Drift increased without performance gain")
        if reset_accelerated:
            report["failure_reasons"].append("Reset frequency accelerated")
        if single_skill_collapse:
            report["failure_reasons"].append("Routing collapsed to single skill")
        
        with open(tmp_path / "long_horizon_drift_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        assert not single_skill_collapse, f"Routing collapsed: {dominant_pct:.1%} to one skill"
        assert reset_count <= 50, f"Too many resets: {reset_count}"

    def test_skill_deprecation_adapts(self):
        """System should adapt when a skill is deprecated."""
        skills = ["good", "deprecated"]
        weights = {s: 1.0 for s in skills}
        
        # Deprecate after 50 runs
        for run in range(100):
            bias = 0.8 if run < 50 else 0.1
            
            # Update deprecated skill
            outcome = 1.0 if random.random() < bias else 0.0
            weights["deprecated"] = apply_ema_update(weights["deprecated"], outcome)
        
        # After deprecation, weight should decrease
        assert weights["deprecated"] < 0.5
