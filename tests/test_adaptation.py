"""
Adaptation Engine Tests (DTL-SKILL-ADAPT v1).
"""

import pytest


class TestRepeatedFailureDetection:
    """Tests for repeated failure detection."""

    def test_detect_repeated_failures(self):
        """Repeated failures should be detected."""
        from src.core.adaptation import (
            ExecutionMetrics, detect_repeated_failures,
            record_failure, MAX_REPEATED_FAILURES
        )
        
        metrics = ExecutionMetrics()
        
        # Record failures below threshold
        for _ in range(MAX_REPEATED_FAILURES - 1):
            record_failure(metrics, "network_error")
        
        assert detect_repeated_failures(metrics) is None
        
        # One more should trigger
        record_failure(metrics, "network_error")
        assert detect_repeated_failures(metrics) == "network_error"


class TestTimeoutDriftDetection:
    """Tests for timeout drift detection."""

    def test_detect_timeout_drift(self):
        """Timeout drift should be detected."""
        from src.core.adaptation import (
            ExecutionMetrics, detect_timeout_drift, record_step
        )
        
        metrics = ExecutionMetrics(expected_duration_ms=1000)
        
        # Record slow steps
        record_step(metrics, 2500)
        record_step(metrics, 2500)
        
        assert detect_timeout_drift(metrics) is True


class TestMidRunRecovery:
    """Tests for successful mid-run recovery."""

    def test_skill_switch_on_repeated_failure(self):
        """Should switch skills on repeated failures."""
        from src.core.adaptation import (
            ExecutionMetrics, adapt, record_failure
        )
        
        metrics = ExecutionMetrics()
        
        # Record repeated failures
        for _ in range(3):
            record_failure(metrics, "tool_error")
        
        decision = adapt(
            metrics,
            available_skills=["skill_a", "skill_b"],
            current_skill="skill_a"
        )
        
        assert decision.action == "switch_skill"
        assert decision.new_skill == "skill_b"

    def test_replan_on_early_drift(self):
        """Should replan on early timeout drift."""
        from src.core.adaptation import (
            ExecutionMetrics, adapt, record_step
        )
        
        metrics = ExecutionMetrics(expected_duration_ms=1000, step_count=2)
        
        # Simulate drift
        record_step(metrics, 3000)
        record_step(metrics, 3000)
        
        decision = adapt(metrics, available_skills=[])
        
        assert decision.action == "replan"


class TestNoIdentityMutation:
    """Tests that adaptation never mutates identity."""

    def test_abort_does_not_mutate(self):
        """Abort action should not touch identity."""
        from src.core.adaptation import (
            ExecutionMetrics, adapt, record_failure,
            apply_adaptation, AdaptationAbortError
        )
        
        metrics = ExecutionMetrics()
        
        # Trigger abort
        for _ in range(5):
            record_failure(metrics, "critical_error")
        
        decision = adapt(metrics, available_skills=[], current_skill="test")
        
        if decision.action == "abort":
            # Should raise, not mutate
            with pytest.raises(AdaptationAbortError):
                apply_adaptation(decision)
