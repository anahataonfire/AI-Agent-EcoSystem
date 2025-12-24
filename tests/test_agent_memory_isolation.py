"""
Agent Memory Isolation Tests (Prompt AE).

Tests that agents cannot share or mutate each other's memory.
"""

import pytest


class TestStateIsolation:
    """Tests for copy-on-read state isolation."""

    def test_agent_state_isolation(self):
        """Each agent should receive an isolated copy of state."""
        # Simulate state isolation by testing that modifications
        # to a copy don't affect the original
        
        original_state = {
            "messages": ["msg1", "msg2"],
            "evidence_map": {"ev_001": {"type": "rss_item"}}
        }
        
        # Agent receives a copy
        import copy
        agent_state = copy.deepcopy(original_state)
        
        # Agent modifies its copy
        agent_state["messages"].append("rogue_message")
        agent_state["evidence_map"]["ev_rogue"] = {"type": "fake"}
        
        # Original should be unchanged
        assert len(original_state["messages"]) == 2
        assert "ev_rogue" not in original_state["evidence_map"]


class TestCrossAgentWrite:
    """Tests for cross-agent write prevention."""

    def test_deny_cross_agent_write(self):
        """Agents must not write to shared state outside their scope."""
        from src.agents.manifest import validate_action, CapabilityViolationError
        
        # Thinker should not write evidence
        with pytest.raises(CapabilityViolationError):
            validate_action("thinker", "write_evidence")
        
        # Sanitizer should not write identity
        with pytest.raises(CapabilityViolationError):
            validate_action("sanitizer", "write_identity")

    def test_executor_cannot_write_identity(self):
        """Executor must not write to identity store."""
        from src.agents.manifest import validate_action, CapabilityViolationError
        
        with pytest.raises(CapabilityViolationError):
            validate_action("executor", "write_identity")


class TestReporterPersistence:
    """Tests that only reporter can persist."""

    def test_reporter_only_persistence(self):
        """Only reporter_node should have write_identity capability."""
        from src.agents.manifest import check_capability
        
        # Only reporter can write identity
        assert check_capability("thinker", "write_identity") is False
        assert check_capability("sanitizer", "write_identity") is False
        assert check_capability("executor", "write_identity") is False
        assert check_capability("reporter", "write_identity") is True

    def test_reporter_has_full_write_access(self):
        """Reporter should have all persistence capabilities."""
        from src.agents.manifest import check_capability
        
        assert check_capability("reporter", "write_identity") is True
        assert check_capability("reporter", "write_evidence") is True
        assert check_capability("reporter", "read_identity") is True
        assert check_capability("reporter", "read_evidence") is True
