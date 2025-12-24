"""
Proactive Decision Tests (DTL-SKILL-PROACTIVE v1).
"""

import pytest


class TestConfidenceThreshold:
    """Tests for confidence threshold enforcement."""

    def test_low_confidence_blocked(self):
        """Low confidence should block action."""
        from src.core.proactive import evaluate_proactive_action, MIN_PROACTIVE_CONFIDENCE
        
        decision = evaluate_proactive_action(
            action_type="auto_fetch",
            confidence=0.5,  # Below 0.85
            reason="Data might be stale"
        )
        
        assert decision.blocked is True
        assert "confidence" in decision.block_reason.lower()

    def test_high_confidence_allowed(self):
        """High confidence should allow action."""
        from src.core.proactive import evaluate_proactive_action
        from src.core.run_ledger import reset_ledger
        
        reset_ledger()
        
        decision = evaluate_proactive_action(
            action_type="auto_fetch",
            confidence=0.9,
            reason="Data is definitely stale"
        )
        
        assert decision.blocked is False


class TestFalsePositiveSuppression:
    """Tests for false positive suppression."""

    def test_recently_executed_suppressed(self):
        """Recently executed actions should be suppressed."""
        from src.core.proactive import suppress_false_positive
        
        context = {"recently_executed": True}
        
        should_suppress = suppress_false_positive("auto_fetch", context)
        assert should_suppress is True

    def test_high_uncertainty_suppressed(self):
        """High uncertainty should suppress action."""
        from src.core.proactive import suppress_false_positive
        
        context = {"context_uncertainty": 0.5}
        
        should_suppress = suppress_false_positive("auto_fetch", context)
        assert should_suppress is True

    def test_normal_context_not_suppressed(self):
        """Normal context should not suppress."""
        from src.core.proactive import suppress_false_positive
        
        context = {"recently_executed": False, "context_uncertainty": 0.1}
        
        should_suppress = suppress_false_positive("auto_fetch", context)
        assert should_suppress is False


class TestLedgerLogging:
    """Tests for ledger logging before action."""

    def test_action_logged_to_ledger(self):
        """Proactive actions should be logged to ledger."""
        from src.core.proactive import (
            evaluate_proactive_action, execute_proactive_action,
            EVENT_PROACTIVE_ACTION
        )
        from src.core.run_ledger import get_ledger, reset_ledger
        
        reset_ledger()
        
        decision = evaluate_proactive_action(
            action_type="auto_cleanup",
            confidence=0.9,
            reason="Stale data detected"
        )
        
        execute_proactive_action(decision, actor="system")
        
        ledger = get_ledger()
        entries = ledger.get_entries(ledger.run_id)
        
        proactive_entries = [e for e in entries if e["event"] == EVENT_PROACTIVE_ACTION]
        assert len(proactive_entries) >= 1
