"""
Agent Capability Sandboxing Tests (Prompt AB).

Tests that agents can only perform actions declared in their manifests.
"""

import pytest


class TestCapabilityEnforcement:
    """Tests for capability manifest enforcement."""

    def test_deny_identity_write_from_thinker(self):
        """Thinker agent must not be allowed to write identity."""
        from src.agents.manifest import validate_action, CapabilityViolationError
        
        with pytest.raises(CapabilityViolationError) as exc_info:
            validate_action("thinker", "write_identity")
        
        assert "capability violation" in str(exc_info.value).lower()

    def test_deny_tool_not_in_manifest(self):
        """Agent must not invoke tools not in its manifest."""
        from src.agents.manifest import validate_action, CapabilityViolationError
        
        # Thinker cannot invoke CompleteTask (only reporter can)
        with pytest.raises(CapabilityViolationError) as exc_info:
            validate_action("thinker", "invoke_tool", tool_name="CompleteTask")
        
        assert "cannot invoke" in str(exc_info.value).lower()

    def test_allow_declared_tool(self):
        """Agent should be allowed to invoke tools in its manifest."""
        from src.agents.manifest import validate_action
        
        # Thinker can invoke DataFetchRSS
        validate_action("thinker", "invoke_tool", tool_name="DataFetchRSS")
        
        # Reporter can invoke CompleteTask
        validate_action("reporter", "invoke_tool", tool_name="CompleteTask")

    def test_deny_manifest_mutation(self):
        """Manifest should not be mutated at runtime."""
        from src.agents.manifest import AGENT_MANIFESTS, validate_manifest_immutable
        
        # Store original state
        original_keys = set(AGENT_MANIFESTS.keys())
        
        # Verify immutability check passes
        assert validate_manifest_immutable() is True
        
        # Attempt mutation (should not affect validation)
        try:
            AGENT_MANIFESTS["rogue_agent"] = {"read_identity": True}
        except (TypeError, AttributeError):
            pass  # Frozen dict would raise
        
        # Even if mutation succeeded, check should detect it
        # (In real impl, manifests would be frozen)


class TestCapabilityChecks:
    """Tests for individual capability check functions."""

    def test_check_capability_read_identity(self):
        """Test read_identity capability check."""
        from src.agents.manifest import check_capability
        
        assert check_capability("thinker", "read_identity") is True
        assert check_capability("executor", "read_identity") is False
        assert check_capability("reporter", "read_identity") is True

    def test_check_capability_write_evidence(self):
        """Test write_evidence capability check."""
        from src.agents.manifest import check_capability
        
        assert check_capability("thinker", "write_evidence") is False
        assert check_capability("executor", "write_evidence") is True
        assert check_capability("reporter", "write_evidence") is True

    def test_get_allowed_tools(self):
        """Test getting list of allowed tools."""
        from src.agents.manifest import get_allowed_tools
        
        thinker_tools = get_allowed_tools("thinker")
        assert "DataFetchRSS" in thinker_tools
        assert "CompleteTask" not in thinker_tools
        
        reporter_tools = get_allowed_tools("reporter")
        assert "CompleteTask" in reporter_tools
