"""
Autonomy Degradation Tests (Prompt 5).

Proves autonomy fails loudly, not gracefully.
"""

import pytest


class TestRetryDisabled:
    """Tests for system behavior when retry is disabled."""

    def test_no_retry_explicit_failure(self):
        """With retry disabled, failures should propagate immediately."""
        from src.core.retry_strategy import (
            decide_retry, RetryState, RetryConfig, FailureClass
        )
        
        # Zero retries allowed
        config = RetryConfig(max_total_retries=0)
        
        decision = decide_retry(
            FailureClass.TRANSIENT,
            RetryState(),
            config
        )
        
        assert decision.should_retry is False
        assert "cap" in decision.reason.lower()

    def test_degradation_signal_clear(self):
        """Degradation signal should be unambiguous."""
        from src.core.retry_strategy import decide_retry, RetryState, RetryConfig, FailureClass
        
        config = RetryConfig(max_total_retries=0)
        decision = decide_retry(FailureClass.TRANSIENT, RetryState(), config)
        
        # Signal should clearly indicate why
        assert decision.reason is not None
        assert len(decision.reason) > 10


class TestAttributionDisabled:
    """Tests for system behavior when attribution confidence is low."""

    def test_low_attribution_signals_clearly(self):
        """Low attribution should produce clear failure signal."""
        from src.core.failure_attribution import attribute_failure
        
        # Unknown error type
        attr = attribute_failure("Some completely unknown xyzzy error")
        
        # Should still produce attribution (not abort)
        assert attr.root_cause in ["tool", "data", "prompt", "policy", "unknown"]
        # Unknown errors get lower confidence but still work
        assert attr.confidence > 0


class TestContextBudgetMinimum:
    """Tests for system behavior at minimum context budget."""

    def test_minimum_budget_selects_nothing(self):
        """Minimum budget should select highest priority only."""
        from src.core.context_budget import ContextSlice, select_context_slices
        
        slices = [
            ContextSlice("critical", priority=10, token_estimate=50, content="Critical"),
            ContextSlice("normal", priority=5, token_estimate=50, content="Normal"),
        ]
        
        # Very small budget
        selected = select_context_slices(slices, max_tokens=60)
        
        assert len(selected) == 1
        assert selected[0].source == "critical"

    def test_no_hallucinated_recovery(self):
        """System should not hallucinate content to fill budget."""
        from src.core.context_budget import ContextSlice, select_context_slices, get_total_tokens
        
        slices = [
            ContextSlice("only", priority=10, token_estimate=100, content="x" * 400),
        ]
        
        selected = select_context_slices(slices, max_tokens=50)
        
        # Cannot fit - should return empty, not truncated
        assert len(selected) == 0
        # No phantom content
        assert get_total_tokens(selected) == 0


class TestProactiveDisabled:
    """Tests for system behavior when proactive engine is disabled."""

    def test_low_confidence_blocks_proactive(self):
        """Low confidence should block proactive actions."""
        from src.core.proactive import evaluate_proactive_action
        
        decision = evaluate_proactive_action(
            action_type="auto_action",
            confidence=0.5,  # Below 0.85
            reason="Test"
        )
        
        assert decision.blocked is True
        assert "confidence" in decision.block_reason.lower()

    def test_kill_switch_blocks_proactive(self):
        """Kill switches should block proactive actions."""
        from src.core.proactive import evaluate_proactive_action, check_proactive_allowed
        import src.core.kill_switches as ks
        
        # Save original
        original = ks.DISABLE_TRUE_REUSE
        
        try:
            # Enable kill switch
            ks.DISABLE_TRUE_REUSE = True
            
            # Check proactive allowed should return False
            allowed, reason = check_proactive_allowed()
            assert allowed is False
            assert "kill switch" in reason.lower()
            
            # Evaluate should block
            decision = evaluate_proactive_action(
                action_type="auto_action",
                confidence=0.9,
                reason="Test"
            )
            
            assert decision.blocked is True
            assert "kill switch" in decision.block_reason.lower()
        finally:
            # Restore original
            ks.DISABLE_TRUE_REUSE = original


class TestFailureAttributionCorrectness:
    """Tests for correct failure attribution under degradation."""

    def test_attribution_matches_actual_cause(self):
        """Attribution should match the actual failure cause."""
        from src.core.failure_attribution import attribute_failure
        
        # Tool error
        attr = attribute_failure("Connection timeout occurred")
        assert attr.root_cause == "tool"
        
        # Data error
        attr = attribute_failure("Validation failed: missing required field")
        assert attr.root_cause == "data"
        
        # Policy error
        attr = attribute_failure("Access denied", error_code="DTL-SEC-001")
        assert attr.root_cause == "policy"

    def test_no_misattribution_under_pressure(self):
        """Attribution should remain accurate under multiple failures."""
        from src.core.failure_attribution import attribute_failure
        
        # Same error multiple times should get same attribution
        for _ in range(5):
            attr = attribute_failure("Rate limit exceeded")
            assert attr.root_cause == "tool"
            assert attr.retryable is True
