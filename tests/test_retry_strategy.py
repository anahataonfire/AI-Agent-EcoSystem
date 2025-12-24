"""
Retry Strategy Tests (DTL-SKILL-RETRY v1).
"""

import pytest


class TestRetryBounds:
    """Tests for retry attempt bounds."""

    def test_max_retries_enforced(self):
        """Total retry attempts must not exceed cap."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry, apply_retry_decision
        )
        
        config = RetryConfig(max_total_retries=3)
        state = RetryState()
        
        # Simulate 3 retries
        for i in range(3):
            decision = decide_retry(FailureClass.TRANSIENT, state, config)
            assert decision.should_retry is True
            state = apply_retry_decision(decision, state, FailureClass.TRANSIENT)
        
        # 4th should be denied
        decision = decide_retry(FailureClass.TRANSIENT, state, config)
        assert decision.should_retry is False
        assert "cap" in decision.reason.lower()

    def test_class_specific_limits(self):
        """Each failure class has its own limit."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry, apply_retry_decision, MAX_RETRIES_BY_CLASS
        )
        
        config = RetryConfig(max_total_retries=10)
        state = RetryState()
        
        # Rate limit should have 2 retries max
        max_rate_limit = MAX_RETRIES_BY_CLASS[FailureClass.RATE_LIMIT]
        
        for i in range(max_rate_limit):
            decision = decide_retry(FailureClass.RATE_LIMIT, state, config)
            assert decision.should_retry is True
            state = apply_retry_decision(decision, state, FailureClass.RATE_LIMIT)
        
        # Next should be denied
        decision = decide_retry(FailureClass.RATE_LIMIT, state, config)
        assert decision.should_retry is False


class TestCostCaps:
    """Tests for retry cost enforcement."""

    def test_cost_cap_enforced(self):
        """Total cost must not exceed cap."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry, apply_retry_decision
        )
        
        config = RetryConfig(max_cost_units=30, max_total_retries=10)
        state = RetryState()
        
        retries = 0
        while True:
            decision = decide_retry(FailureClass.TRANSIENT, state, config)
            if not decision.should_retry:
                break
            state = apply_retry_decision(decision, state, FailureClass.TRANSIENT)
            retries += 1
            if retries > 10:  # Safety
                break
        
        assert state.total_cost <= config.max_cost_units


class TestFailureClassification:
    """Tests for failure classification."""

    def test_transient_classification(self):
        """Transient errors should be classified correctly."""
        from src.core.retry_strategy import classify_failure, FailureClass
        
        assert classify_failure("Connection timeout") == FailureClass.TRANSIENT
        assert classify_failure("Network error occurred") == FailureClass.TRANSIENT

    def test_rate_limit_classification(self):
        """Rate limits should be classified correctly."""
        from src.core.retry_strategy import classify_failure, FailureClass
        
        assert classify_failure("Rate limit exceeded") == FailureClass.RATE_LIMIT
        assert classify_failure("Error 429: Too many requests") == FailureClass.RATE_LIMIT

    def test_policy_classification(self):
        """Policy errors should not be retryable."""
        from src.core.retry_strategy import classify_failure, FailureClass
        
        result = classify_failure("Kill switch active", error_code="DTL-SEC-005")
        assert result == FailureClass.POLICY


class TestToolSwitching:
    """Tests for tool fallback chains."""

    def test_tool_fallback(self):
        """Tool failures should suggest alternates."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry
        )
        
        config = RetryConfig()
        state = RetryState(tools_tried=["DataFetchRSS"])
        
        decision = decide_retry(
            FailureClass.TOOL_ERROR,
            state,
            config,
            current_tool="DataFetchRSS"
        )
        
        assert decision.should_retry is True
        assert decision.alternate_tool == "DataFetchAPI"

    def test_no_fallback_when_exhausted(self):
        """No alternate when all tools tried."""
        from src.core.retry_strategy import get_alternate_tool
        
        tools_tried = ["DataFetchRSS", "DataFetchAPI", "BrowserSearch"]
        alternate = get_alternate_tool("DataFetchRSS", tools_tried)
        
        assert alternate is None


class TestNonRetryable:
    """Tests for non-retryable failures."""

    def test_data_invalid_not_retryable(self):
        """Invalid data should not be retried."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry
        )
        
        config = RetryConfig()
        state = RetryState()
        
        decision = decide_retry(FailureClass.DATA_INVALID, state, config)
        assert decision.should_retry is False

    def test_policy_not_retryable(self):
        """Policy failures should not be retried."""
        from src.core.retry_strategy import (
            RetryState, RetryConfig, FailureClass,
            decide_retry
        )
        
        config = RetryConfig()
        state = RetryState()
        
        decision = decide_retry(FailureClass.POLICY, state, config)
        assert decision.should_retry is False
