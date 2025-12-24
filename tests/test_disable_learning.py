"""
Tests for DISABLE_LEARNING kill switch.

Verifies:
- Learning fully disabled when switch active
- Determinism preserved
- No partial state mutation
- Proper ledger logging
"""

import pytest
import src.core.kill_switches as ks
from src.core.learning_controller import LearningController, DTL_STRAT_013


class TestDisableLearningKillSwitch:
    """Tests for DISABLE_LEARNING kill switch."""

    def test_learning_disabled_when_switch_active(self):
        """All learning operations blocked when switch active."""
        original = ks.DISABLE_LEARNING
        try:
            ks.DISABLE_LEARNING = True
            
            controller = LearningController()
            controller.start_run({"skill_a": 1.0})
            
            # Weight update blocked
            success, code = controller.apply_weight_update("skill_a", 1.0)
            assert success is False
            assert code == DTL_STRAT_013
            
            # Decay blocked
            success, code = controller.apply_decay()
            assert success is False
            assert code == DTL_STRAT_013
            
            # Counterfactual blocked
            success, code = controller.run_counterfactual([])
            assert success is False
            assert code == DTL_STRAT_013
            
            # Policy memory write blocked
            success, code = controller.write_policy_memory("/tmp/test")
            assert success is False
            assert code == DTL_STRAT_013
        finally:
            ks.DISABLE_LEARNING = original

    def test_learning_enabled_when_switch_inactive(self):
        """Learning operations proceed when switch inactive."""
        original = ks.DISABLE_LEARNING
        try:
            ks.DISABLE_LEARNING = False
            
            controller = LearningController()
            controller.start_run({"skill_a": 1.0})
            
            success, code = controller.apply_weight_update("skill_a", 0.5)
            assert success is True
            assert code is None
        finally:
            ks.DISABLE_LEARNING = original

    def test_no_partial_state_mutation(self):
        """Weights unchanged when learning disabled."""
        original = ks.DISABLE_LEARNING
        try:
            ks.DISABLE_LEARNING = True
            
            initial_weights = {"skill_a": 1.5, "skill_b": 0.8}
            controller = LearningController()
            controller.start_run(initial_weights.copy())
            
            # Attempt updates
            controller.apply_weight_update("skill_a", 0.0)
            controller.apply_weight_update("skill_b", 1.0)
            controller.apply_decay()
            
            # Weights unchanged
            assert controller.get_weights() == initial_weights
        finally:
            ks.DISABLE_LEARNING = original

    def test_determinism_preserved(self):
        """Same inputs produce same outputs regardless of disabled learning."""
        original = ks.DISABLE_LEARNING
        try:
            ks.DISABLE_LEARNING = True
            
            weights = {"a": 1.0, "b": 0.9}
            
            c1 = LearningController()
            c1.start_run(weights.copy())
            
            c2 = LearningController()
            c2.start_run(weights.copy())
            
            # Same operations
            c1.apply_weight_update("a", 0.5)
            c2.apply_weight_update("a", 0.5)
            
            # Same state
            assert c1.get_weights() == c2.get_weights()
        finally:
            ks.DISABLE_LEARNING = original

    def test_ledger_events_logged(self):
        """Proper ledger events emitted when disabled."""
        original = ks.DISABLE_LEARNING
        try:
            ks.DISABLE_LEARNING = True
            
            controller = LearningController()
            controller.start_run({})
            controller.apply_weight_update("skill_a", 1.0)
            
            entries = controller.get_ledger_entries()
            events = [e["event"] for e in entries]
            
            assert "LEARNING_STATE_READ" in events
            assert "LEARNING_SKIPPED_DISABLED" in events
        finally:
            ks.DISABLE_LEARNING = original

    def test_kill_switch_read_once(self):
        """Kill switch state is immutable during run."""
        original = ks.DISABLE_LEARNING
        try:
            ks.DISABLE_LEARNING = False
            
            controller = LearningController()
            state = controller.start_run({"skill_a": 1.0})
            
            # Change kill switch mid-run
            ks.DISABLE_LEARNING = True
            
            # Should still use original state (enabled)
            assert controller.can_learn() is True
            
            success, _ = controller.apply_weight_update("skill_a", 0.5)
            assert success is True
        finally:
            ks.DISABLE_LEARNING = original

    def test_bounded_defaults_used_when_disabled(self):
        """Bounded autonomy defaults used when learning disabled."""
        original = ks.DISABLE_LEARNING
        try:
            ks.DISABLE_LEARNING = True
            
            controller = LearningController()
            state = controller.start_run()  # No weights provided
            
            assert state.weights == {}  # Empty = defaults
        finally:
            ks.DISABLE_LEARNING = original
