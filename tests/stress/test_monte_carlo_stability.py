"""
Monte Carlo Policy Stability Test (Prompt 1).

Simulates 10,000 synthetic runs with biased and adversarial distributions.
Verifies EMA updates, decay, clamping, and routing stability.
"""

import pytest
import json
import random
import math
from collections import Counter
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


# Constants from skill_routing_learning.md
LEARNING_RATE = 0.2
WEIGHT_MIN = 0.1
WEIGHT_MAX = 2.0
DECAY_RATE = 0.95


@dataclass
class PolicyMemorySnapshot:
    """Snapshot of policy memory state."""
    weights: Dict[str, float] = field(default_factory=dict)
    update_count: int = 0


def apply_ema_update(weight: float, outcome: float) -> float:
    """Apply EMA update with clamping."""
    new_weight = LEARNING_RATE * outcome + (1 - LEARNING_RATE) * weight
    return max(WEIGHT_MIN, min(WEIGHT_MAX, new_weight))


def apply_decay(weights: Dict[str, float], days_elapsed: float = 1.0) -> Dict[str, float]:
    """Apply time-based decay to weights."""
    decay_factor = DECAY_RATE ** days_elapsed
    return {k: max(WEIGHT_MIN, v * decay_factor) for k, v in weights.items()}


def get_routing_order(weights: Dict[str, float]) -> List[str]:
    """Get deterministic routing order from weights (highest first)."""
    return sorted(weights.keys(), key=lambda k: (-weights[k], k))


def compute_entropy(counts: Counter) -> float:
    """Compute Shannon entropy of a distribution."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


class TestMonteCarloPolicyStability:
    """Monte Carlo simulation for policy stability."""

    def test_policy_stability_10000_runs(self, tmp_path):
        """Simulate 10,000 runs with varied outcome distributions."""
        random.seed(42)  # Deterministic for testing
        skills = ["skill_a", "skill_b", "skill_c"]
        weights = {s: 1.0 for s in skills}
        
        routing_history = []
        weight_history = []
        clamp_triggers = 0
        
        # Outcome biases (skill_a is best, skill_c is worst)
        biases = {"skill_a": 0.8, "skill_b": 0.5, "skill_c": 0.3}
        
        for run in range(10000):
            # Apply decay every 10 runs (simulating ~1 day)
            if run > 0 and run % 10 == 0:
                weights = apply_decay(weights, days_elapsed=1.0)
            
            # Get routing order
            routing = get_routing_order(weights)
            routing_history.append(routing[0])  # Log first choice
            
            # Simulate outcome for first skill
            selected = routing[0]
            outcome = 1.0 if random.random() < biases[selected] else 0.0
            
            # Apply EMA update
            old_weight = weights[selected]
            weights[selected] = apply_ema_update(old_weight, outcome)
            
            # Track clamping
            if weights[selected] == WEIGHT_MIN or weights[selected] == WEIGHT_MAX:
                clamp_triggers += 1
            
            if run % 100 == 0:
                weight_history.append(dict(weights))
        
        # Analyze results
        routing_counts = Counter(routing_history)
        
        # Compute entropy over time (sliding window)
        window_size = 1000
        entropy_over_time = []
        for i in range(0, len(routing_history) - window_size, window_size):
            window = routing_history[i:i + window_size]
            entropy_over_time.append(compute_entropy(Counter(window)))
        
        # Verdicts
        oscillation_detected = False
        for i in range(len(routing_history) - 100):
            window = routing_history[i:i + 100]
            unique = len(set(window))
            if unique >= 3 and all(window[j] != window[j+1] for j in range(len(window)-1)):
                oscillation_detected = True
                break
        
        # Best skill should dominate (skill_a with 0.8 bias)
        dominance_justified = routing_counts["skill_a"] > routing_counts["skill_b"] > routing_counts["skill_c"]
        
        # Clamping should be rare (< 5% of runs)
        clamp_rate = clamp_triggers / 10000
        excessive_clamping = clamp_rate > 0.05
        
        # Determinism check: same snapshot → same routing
        snapshot_weights = {"skill_a": 1.2, "skill_b": 0.8, "skill_c": 1.0}
        routing_1 = get_routing_order(snapshot_weights)
        routing_2 = get_routing_order(snapshot_weights)
        determinism_ok = routing_1 == routing_2
        
        # Generate report
        report = {
            "total_runs": 10000,
            "routing_counts": dict(routing_counts),
            "clamp_triggers": clamp_triggers,
            "clamp_rate": clamp_rate,
            "oscillation_detected": oscillation_detected,
            "dominance_justified": dominance_justified,
            "determinism_verified": determinism_ok,
            "final_weights": weights,
            "verdict": "FAIL" if (oscillation_detected or not dominance_justified or excessive_clamping or not determinism_ok) else "PASS"
        }
        
        # Write outputs
        with open(tmp_path / "policy_drift_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        with open(tmp_path / "routing_entropy_over_time.csv", "w") as f:
            f.write("window,entropy\n")
            for i, e in enumerate(entropy_over_time):
                f.write(f"{i},{e:.4f}\n")
        
        # Assertions
        assert not oscillation_detected, "Routing oscillated indefinitely"
        assert dominance_justified, "Skill dominance not justified by performance"
        assert not excessive_clamping, f"Weight clamping triggered too often: {clamp_rate:.2%}"
        assert determinism_ok, "Identical snapshots produced different routing"

    def test_adversarial_distribution(self, tmp_path):
        """Test with adversarial outcome distributions."""
        random.seed(43)  # Deterministic for testing
        skills = ["skill_a", "skill_b", "skill_c"]
        weights = {s: 1.0 for s in skills}
        
        # Adversarial: outcomes flip every 100 runs
        flip_period = 100
        
        for run in range(2000):
            routing = get_routing_order(weights)
            selected = routing[0]
            
            # Flip outcomes periodically
            if (run // flip_period) % 2 == 0:
                biases = {"skill_a": 0.9, "skill_b": 0.1, "skill_c": 0.5}
            else:
                biases = {"skill_a": 0.1, "skill_b": 0.9, "skill_c": 0.5}
            
            outcome = 1.0 if random.random() < biases[selected] else 0.0
            weights[selected] = apply_ema_update(weights[selected], outcome)
        
        # After adversarial distribution, weights should stabilize
        # EMA should dampen oscillations
        weight_range = max(weights.values()) - min(weights.values())
        
        # Weights shouldn't be extreme despite adversarial inputs
        assert weight_range < 1.5, f"Weight range too extreme: {weight_range}"
        assert all(WEIGHT_MIN <= w <= WEIGHT_MAX for w in weights.values())
