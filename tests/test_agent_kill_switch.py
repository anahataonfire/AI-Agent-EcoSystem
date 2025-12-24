"""
Agent Compromise Kill-Switch Tests (Prompt AF).

Tests for agent-level quarantine on security violations.
"""

import pytest


class TestAgentQuarantine:
    """Tests for agent quarantine functionality."""

    def test_quarantine_on_violation(self):
        """Agent should be quarantined after a violation."""
        from src.core.kill_switches import (
            trigger_agent_compromised,
            is_agent_quarantined,
            check_agent_allowed,
            reset_quarantine
        )
        
        reset_quarantine()
        
        # Agent not quarantined initially
        assert is_agent_quarantined("thinker") is False
        allowed, _ = check_agent_allowed("thinker")
        assert allowed is True
        
        # Trigger quarantine
        trigger_agent_compromised("thinker", "grounding_failure")
        
        # Agent should now be quarantined
        assert is_agent_quarantined("thinker") is True
        allowed, reason = check_agent_allowed("thinker")
        assert allowed is False
        assert "quarantined" in reason.lower()
        
        reset_quarantine()


class TestNoPartialExecution:
    """Tests that quarantine prevents any further execution."""

    def test_no_partial_execution(self):
        """Quarantined agent should not execute any further."""
        from src.core.kill_switches import (
            trigger_agent_compromised,
            check_agent_allowed,
            reset_quarantine
        )
        
        reset_quarantine()
        
        # Quarantine the agent
        trigger_agent_compromised("executor", "instruction_injection")
        
        # Multiple checks should all fail
        for _ in range(3):
            allowed, _ = check_agent_allowed("executor")
            assert allowed is False
        
        reset_quarantine()


class TestQuarantineTelemetry:
    """Tests that quarantine is recorded for telemetry."""

    def test_telemetry_records_agent(self):
        """Quarantine reason should be recorded for telemetry."""
        from src.core.kill_switches import (
            trigger_agent_compromised,
            get_quarantine_reason,
            get_all_quarantined_agents,
            reset_quarantine
        )
        
        reset_quarantine()
        
        trigger_agent_compromised("sanitizer", "capability_violation")
        
        # Reason should be recorded
        reason = get_quarantine_reason("sanitizer")
        assert reason == "capability_violation"
        
        # Should appear in all quarantined agents
        all_quarantined = get_all_quarantined_agents()
        assert "sanitizer" in all_quarantined
        assert all_quarantined["sanitizer"] == "capability_violation"
        
        reset_quarantine()

    def test_quarantine_message_format(self):
        """Quarantine message should follow expected format."""
        from src.core.kill_switches import build_quarantine_message
        
        message = build_quarantine_message("thinker", "grounding_failure")
        
        assert "Execution Aborted" in message
        assert "thinker" in message
        assert "compromised" in message.lower()
        assert "grounding_failure" in message
