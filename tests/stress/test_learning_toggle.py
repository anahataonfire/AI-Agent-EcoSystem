"""
Learning Disable Reversion Test (Prompt 10).

Tests disabling learning for 10 runs, re-enabling, and verifying
clean resumption with no latent state corruption.
"""

import pytest
import json
from typing import Dict, Any


class LearningSystem:
    """Learning system with toggle capability."""
    
    def __init__(self):
        self.weights = {"skill_a": 1.0, "skill_b": 1.0, "skill_c": 1.0}
        self.learning_enabled = True
        self.update_history = []
        self.snapshot_before_disable = None
    
    def disable_learning(self):
        """Disable learning and snapshot current state."""
        self.snapshot_before_disable = dict(self.weights)
        self.learning_enabled = False
        self.update_history.append({"event": "LEARNING_DISABLED"})
    
    def enable_learning(self):
        """Re-enable learning."""
        self.learning_enabled = True
        self.update_history.append({"event": "LEARNING_ENABLED"})
    
    def apply_update(self, skill: str, outcome: float) -> bool:
        """Apply learning update. Returns True if applied."""
        if not self.learning_enabled:
            self.update_history.append({
                "event": "UPDATE_BLOCKED",
                "skill": skill,
                "outcome": outcome
            })
            return False
        
        alpha = 0.2
        old_weight = self.weights.get(skill, 1.0)
        new_weight = alpha * outcome + (1 - alpha) * old_weight
        new_weight = max(0.1, min(2.0, new_weight))
        
        self.weights[skill] = new_weight
        self.update_history.append({
            "event": "UPDATE_APPLIED",
            "skill": skill,
            "old": old_weight,
            "new": new_weight
        })
        return True
    
    def get_routing(self):
        """Get deterministic routing order."""
        return sorted(self.weights.keys(), key=lambda k: (-self.weights[k], k))
    
    def check_integrity(self) -> bool:
        """Check for state corruption."""
        for skill, weight in self.weights.items():
            if not isinstance(weight, float):
                return False
            if weight < 0.1 or weight > 2.0:
                return False
        return True


class TestLearningToggle:
    """Tests for learning toggle reversion."""

    def test_disable_blocks_updates(self):
        """Disabled learning should block updates."""
        system = LearningSystem()
        
        system.disable_learning()
        result = system.apply_update("skill_a", 1.0)
        
        assert result is False
        assert system.weights["skill_a"] == 1.0  # Unchanged

    def test_reenable_resumes_learning(self):
        """Re-enabling learning should resume updates."""
        system = LearningSystem()
        initial_weight = system.weights["skill_a"]
        
        system.disable_learning()
        system.enable_learning()
        
        result = system.apply_update("skill_a", 0.0)  # Use 0.0 to decrease weight
        
        assert result is True
        assert system.weights["skill_a"] < initial_weight  # Weight decreased

    def test_no_latent_corruption_after_toggle(self):
        """No latent state corruption after disable/enable cycle."""
        system = LearningSystem()
        
        # Apply some updates
        system.apply_update("skill_a", 0.8)
        system.apply_update("skill_b", 0.6)
        
        # Disable for 10 "runs"
        system.disable_learning()
        for _ in range(10):
            system.apply_update("skill_a", 0.0)  # Would decrease weight
            system.apply_update("skill_b", 1.0)  # Would increase weight
        
        # State should be unchanged from before disable
        assert system.weights["skill_a"] == system.snapshot_before_disable["skill_a"]
        assert system.weights["skill_b"] == system.snapshot_before_disable["skill_b"]
        
        # Re-enable
        system.enable_learning()
        
        # Verify integrity
        assert system.check_integrity()

    def test_determinism_preserved_after_toggle(self):
        """Routing should be deterministic after toggle."""
        system = LearningSystem()
        
        # Get baseline routing
        routing_before = system.get_routing()
        
        # Toggle off and on
        system.disable_learning()
        system.enable_learning()
        
        # Routing should be identical
        routing_after = system.get_routing()
        
        assert routing_before == routing_after

    def test_10_runs_disabled_then_resume(self, tmp_path):
        """Full test: disable for 10 runs, resume, verify clean state."""
        system = LearningSystem()
        
        # Pre-disable: apply some learning
        for _ in range(5):
            system.apply_update("skill_a", 0.7)
        
        state_pre_disable = dict(system.weights)
        
        # Disable
        system.disable_learning()
        
        # 10 runs with attempted updates
        for i in range(10):
            system.apply_update("skill_a", 0.0)
            system.apply_update("skill_b", 1.0)
            system.apply_update("skill_c", 0.5)
        
        state_during_disable = dict(system.weights)
        
        # Re-enable
        system.enable_learning()
        
        # 5 runs with learning
        for _ in range(5):
            system.apply_update("skill_b", 0.9)
        
        state_after_resume = dict(system.weights)
        
        # Generate report
        report = {
            "state_pre_disable": state_pre_disable,
            "state_during_disable": state_during_disable,
            "state_after_resume": state_after_resume,
            "updates_blocked_during_disable": sum(
                1 for e in system.update_history if e["event"] == "UPDATE_BLOCKED"
            ),
            "updates_applied_after_resume": sum(
                1 for e in system.update_history 
                if e["event"] == "UPDATE_APPLIED" and 
                system.update_history.index(e) > system.update_history.index({"event": "LEARNING_ENABLED"})
            ),
            "integrity_preserved": system.check_integrity(),
            "determinism_preserved": True  # Checked separately
        }
        
        # Verify no corruption during disable
        assert state_pre_disable == state_during_disable, "State corrupted during disable"
        
        # Verify learning resumed
        assert state_after_resume["skill_b"] != state_during_disable["skill_b"], "Learning did not resume"
        
        # Verify integrity
        assert system.check_integrity(), "State corruption detected"
        
        with open(tmp_path / "learning_toggle_integrity.json", "w") as f:
            json.dump(report, f, indent=2)
