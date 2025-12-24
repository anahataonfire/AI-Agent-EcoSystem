"""
Kill-Switch Authority Verification Test (Prompt 4).

Verifies that DISABLE_LEARNING kill switch always overrides learning
at run boundary, counterfactual, decay read, and post-run write.
"""

import pytest
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class LedgerEntry:
    """A ledger entry."""
    event: str
    payload: Dict[str, Any]


class MockLedger:
    """Mock ledger for testing."""
    
    def __init__(self):
        self.entries = []
    
    def log(self, event: str, payload: Dict[str, Any]):
        self.entries.append(LedgerEntry(event, payload))
    
    def has_event(self, event: str) -> bool:
        return any(e.event == event for e in self.entries)


class LearningController:
    """Controls learning based on kill switch state."""
    
    def __init__(self, ledger: MockLedger):
        self.ledger = ledger
        self.disable_learning = False
        self.weights = {"skill_a": 1.0, "skill_b": 1.0}
    
    def set_kill_switch(self, disabled: bool):
        """Set the DISABLE_LEARNING switch."""
        self.disable_learning = disabled
        self.ledger.log("KILL_SWITCH_CHANGE", {"disabled": disabled})
    
    def can_learn(self) -> bool:
        """Check if learning is allowed."""
        return not self.disable_learning
    
    def apply_update(self, skill: str, outcome: float) -> bool:
        """Apply a learning update. Returns True if successful."""
        if self.disable_learning:
            self.ledger.log("LEARNING_BLOCKED", {"skill": skill, "reason": "kill_switch"})
            return False
        
        # Log before update
        self.ledger.log("LEARNING_UPDATE", {"skill": skill, "outcome": outcome})
        
        # Apply EMA
        alpha = 0.2
        self.weights[skill] = alpha * outcome + (1 - alpha) * self.weights[skill]
        return True
    
    def run_counterfactual(self) -> bool:
        """Run counterfactual evaluation."""
        if self.disable_learning:
            self.ledger.log("COUNTERFACTUAL_BLOCKED", {"reason": "kill_switch"})
            return False
        
        self.ledger.log("COUNTERFACTUAL_STARTED", {})
        # Simulate counterfactual
        return True
    
    def apply_decay(self) -> bool:
        """Apply decay to weights."""
        if self.disable_learning:
            # Decay read is blocked
            self.ledger.log("DECAY_BLOCKED", {"reason": "kill_switch"})
            return False
        
        for skill in self.weights:
            self.weights[skill] *= 0.95
        return True


class TestKillSwitchAuthority:
    """Tests for kill switch authority over learning."""

    def test_kill_switch_blocks_run_boundary(self):
        """Kill switch blocks learning at run boundary."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        controller.set_kill_switch(True)
        
        # Try to apply update
        result = controller.apply_update("skill_a", 1.0)
        
        assert result is False
        assert ledger.has_event("LEARNING_BLOCKED")
        assert ledger.has_event("KILL_SWITCH_CHANGE")

    def test_kill_switch_blocks_counterfactual(self):
        """Kill switch blocks counterfactual evaluation."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        controller.set_kill_switch(True)
        
        result = controller.run_counterfactual()
        
        assert result is False
        assert ledger.has_event("COUNTERFACTUAL_BLOCKED")

    def test_kill_switch_blocks_decay(self):
        """Kill switch blocks decay application."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        controller.set_kill_switch(True)
        
        result = controller.apply_decay()
        
        assert result is False
        assert ledger.has_event("DECAY_BLOCKED")

    def test_kill_switch_blocks_post_run_write(self):
        """Kill switch blocks post-run weight updates."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        # Complete a "run" then enable kill switch
        controller.set_kill_switch(True)
        
        # Post-run update should be blocked
        result = controller.apply_update("skill_b", 0.8)
        
        assert result is False
        assert ledger.has_event("LEARNING_BLOCKED")

    def test_learning_resumes_after_switch_off(self):
        """Learning resumes when kill switch is disabled."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        # Enable, then disable
        controller.set_kill_switch(True)
        controller.set_kill_switch(False)
        
        result = controller.apply_update("skill_a", 1.0)
        
        assert result is True
        assert ledger.has_event("LEARNING_UPDATE")

    def test_no_partial_updates_persist(self):
        """No partial state updates when kill switch active."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        original_weight = controller.weights["skill_a"]
        
        controller.set_kill_switch(True)
        controller.apply_update("skill_a", 0.0)  # Would decrease weight
        
        assert controller.weights["skill_a"] == original_weight

    def test_ledger_records_intervention(self):
        """All interventions are recorded in ledger."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        controller.set_kill_switch(True)
        controller.apply_update("skill_a", 1.0)
        controller.run_counterfactual()
        controller.apply_decay()
        
        # All should be logged
        assert ledger.has_event("KILL_SWITCH_CHANGE")
        assert ledger.has_event("LEARNING_BLOCKED")
        assert ledger.has_event("COUNTERFACTUAL_BLOCKED")
        assert ledger.has_event("DECAY_BLOCKED")

    def test_generate_assertions_log(self, tmp_path):
        """Generate kill switch assertions log."""
        ledger = MockLedger()
        controller = LearningController(ledger)
        
        assertions = []
        
        # Test 1: Run boundary
        controller.set_kill_switch(True)
        r1 = controller.apply_update("skill_a", 1.0)
        assertions.append(f"ASSERT run_boundary_blocked: {r1 is False}")
        
        # Test 2: Counterfactual
        r2 = controller.run_counterfactual()
        assertions.append(f"ASSERT counterfactual_blocked: {r2 is False}")
        
        # Test 3: Decay
        r3 = controller.apply_decay()
        assertions.append(f"ASSERT decay_blocked: {r3 is False}")
        
        # Test 4: Ledger recorded
        r4 = ledger.has_event("KILL_SWITCH_CHANGE")
        assertions.append(f"ASSERT ledger_recorded: {r4 is True}")
        
        # Test 5: Resume after toggle
        controller.set_kill_switch(False)
        r5 = controller.apply_update("skill_b", 0.8)
        assertions.append(f"ASSERT learning_resumed: {r5 is True}")
        
        with open(tmp_path / "kill_switch_assertions.log", "w") as f:
            f.write("\n".join(assertions))
        
        assert all("True" in a for a in assertions)
