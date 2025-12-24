"""
EMA Oscillation & Degeneration Test (Prompt 3).

Tests skill routing with alternating success/failure patterns
to verify EMA dampens noise rather than amplifying it.
"""

import pytest
import csv
from typing import List, Dict, Tuple


# Constants
LEARNING_RATE = 0.2
WEIGHT_MIN = 0.1
WEIGHT_MAX = 2.0


def apply_ema_update(weight: float, outcome: float) -> float:
    """Apply EMA update with clamping."""
    new_weight = LEARNING_RATE * outcome + (1 - LEARNING_RATE) * weight
    return max(WEIGHT_MIN, min(WEIGHT_MAX, new_weight))


def get_first_choice(weights: Dict[str, float]) -> str:
    """Get the skill with highest weight (alphabetical tiebreaker)."""
    return max(weights.keys(), key=lambda k: (weights[k], k))


class TestEMAOscillation:
    """Tests for EMA oscillation and degeneration behavior."""

    def test_alternating_skill_200_runs(self, tmp_path):
        """Test oscillating skill vs stable skill over 200 runs."""
        # oscillating_skill: alternates success/failure
        # stable_skill: consistent 60% success but 2x cost
        
        weights = {
            "oscillating_skill": 1.0,
            "stable_skill": 1.0
        }
        
        trace = []
        first_choices = []
        flip_flop_count = 0
        
        for run in range(200):
            # Record state
            first = get_first_choice(weights)
            first_choices.append(first)
            
            # Count flip-flops
            if run > 0 and first_choices[-1] != first_choices[-2]:
                flip_flop_count += 1
            
            # Simulate outcomes
            # Oscillating: success on even runs, failure on odd
            osc_outcome = 1.0 if run % 2 == 0 else 0.0
            
            # Stable: always 60% success
            stable_outcome = 0.6  # Expected value
            
            # Update weights based on which was selected
            if first == "oscillating_skill":
                weights["oscillating_skill"] = apply_ema_update(
                    weights["oscillating_skill"], osc_outcome
                )
            else:
                weights["stable_skill"] = apply_ema_update(
                    weights["stable_skill"], stable_outcome
                )
            
            trace.append({
                "run": run,
                "oscillating_weight": weights["oscillating_skill"],
                "stable_weight": weights["stable_skill"],
                "first_choice": first,
                "osc_outcome": osc_outcome
            })
        
        # Write trace
        with open(tmp_path / "ema_oscillation_trace.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["run", "oscillating_weight", "stable_weight", "first_choice", "osc_outcome"])
            writer.writeheader()
            writer.writerows(trace)
        
        # Verdicts
        
        # 1. Routing should not flip-flop endlessly
        # Allow some flip-flops but not constant switching
        flip_flop_rate = flip_flop_count / 199
        endless_flip_flop = flip_flop_rate > 0.5
        
        # 2. Stable skill should not be starved
        stable_selections = sum(1 for c in first_choices if c == "stable_skill")
        stable_starved = stable_selections < 20  # At least 10% selection
        
        # 3. EMA should dampen noise
        # Oscillating skill's weight should converge toward 0.5 (average of 1.0 and 0.0)
        osc_weight = weights["oscillating_skill"]
        # After many updates, should be near EMA steady state
        ema_damped = 0.3 <= osc_weight <= 0.7
        
        # Final verdict
        passed = not endless_flip_flop and not stable_starved and ema_damped
        
        with open(tmp_path / "ema_verdict.txt", "w") as f:
            f.write(f"flip_flop_rate: {flip_flop_rate:.2%}\n")
            f.write(f"stable_selections: {stable_selections}\n")
            f.write(f"final_oscillating_weight: {osc_weight:.3f}\n")
            f.write(f"endless_flip_flop: {endless_flip_flop}\n")
            f.write(f"stable_starved: {stable_starved}\n")
            f.write(f"ema_damped: {ema_damped}\n")
            f.write(f"\nVERDICT: {'PASS' if passed else 'FAIL'}\n")
        
        assert not endless_flip_flop, f"Routing flip-flopped endlessly: {flip_flop_rate:.2%}"
        assert not stable_starved, f"Stable skill was starved: {stable_selections} selections"
        assert ema_damped, f"EMA did not dampen noise: oscillating weight = {osc_weight:.3f}"

    def test_ema_convergence(self):
        """Verify EMA converges to expected value."""
        weight = 1.0
        
        # Apply 100 updates with outcome = 0.5
        for _ in range(100):
            weight = apply_ema_update(weight, 0.5)
        
        # Should converge close to 0.5
        assert abs(weight - 0.5) < 0.1, f"EMA did not converge: {weight}"

    def test_extreme_oscillation_clamped(self):
        """Extreme oscillation should be clamped."""
        weight = 1.0
        
        for i in range(1000):
            outcome = 1.0 if i % 2 == 0 else 0.0
            weight = apply_ema_update(weight, outcome)
        
        # Weight should remain within bounds
        assert WEIGHT_MIN <= weight <= WEIGHT_MAX
        
        # Should be near the average (0.5) after many oscillations
        assert 0.3 <= weight <= 0.7
