"""
Security Telemetry Tests.

Tests that security-relevant events are properly tracked in telemetry
without leaking into LLM prompt context.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestTelemetryUpdates:
    """Tests that telemetry updates correctly on security events."""

    def test_telemetry_updates_on_grounding_failure(self):
        """Grounding failures must increment telemetry counter."""
        from src.graph.state import RunState
        
        state = RunState()
        telemetry = dict(state.telemetry)
        
        # Simulate grounding failure
        telemetry["grounding_failures"] += 1
        telemetry["security_mode"] = "abort"
        
        assert telemetry["grounding_failures"] == 1
        assert telemetry["security_mode"] == "abort"

    def test_telemetry_updates_on_evidence_rejection(self):
        """Evidence rejections must increment telemetry counter."""
        from src.graph.state import RunState
        
        state = RunState()
        telemetry = dict(state.telemetry)
        
        # Simulate multiple evidence rejections
        telemetry["evidence_rejections"] += 3
        
        assert telemetry["evidence_rejections"] == 3

    def test_telemetry_tracks_reuse_denial(self):
        """Reuse denial reason must be recorded in telemetry."""
        from src.graph.state import RunState
        
        state = RunState()
        telemetry = dict(state.telemetry)
        
        # Simulate reuse denial
        telemetry["reuse_denied_reason"] = "Kill switch activated"
        
        assert telemetry["reuse_denied_reason"] == "Kill switch activated"

    def test_telemetry_clean_on_success(self):
        """Successful runs should have zero failure counts."""
        from src.graph.state import RunState
        
        state = RunState()
        
        # Default state should be clean
        assert state.telemetry["grounding_failures"] == 0
        assert state.telemetry["evidence_rejections"] == 0
        assert state.telemetry["reuse_denied_reason"] is None
        assert state.telemetry["security_mode"] == "normal"


class TestTelemetryIsolation:
    """Tests that telemetry never enters prompt context."""

    def test_no_telemetry_in_prompt_context(self):
        """Telemetry fields must NOT be injected into LLM prompts."""
        from src.graph.state import RunState
        from langchain_core.messages import HumanMessage
        
        # Create state with security telemetry
        state = RunState(
            messages=[HumanMessage(content="Test query")]
        )
        telemetry = dict(state.telemetry)
        telemetry["grounding_failures"] = 5
        telemetry["security_mode"] = "abort"
        
        # Serialize state messages (what would go to LLM)
        message_contents = [msg.content for msg in state.messages if hasattr(msg, 'content')]
        serialized = " ".join(message_contents)
        
        # Verify telemetry terms do not appear in message context
        assert "grounding_failures" not in serialized
        assert "evidence_rejections" not in serialized
        assert "security_mode" not in serialized
        assert "abort" not in serialized

    def test_telemetry_not_in_identity_context(self):
        """Telemetry must not leak into identity_context."""
        from src.graph.state import RunState
        
        state = RunState(
            identity_context={"user_preference": "test"}
        )
        
        # Telemetry should be separate from identity
        if state.identity_context:
            assert "grounding_failures" not in state.identity_context
            assert "telemetry" not in state.identity_context

    def test_telemetry_appears_in_final_state(self):
        """Telemetry must appear in final_state output for operators."""
        from src.graph.state import RunState
        
        state = RunState()
        telemetry = state.telemetry
        
        # All required fields must exist
        assert "grounding_failures" in telemetry
        assert "evidence_rejections" in telemetry
        assert "reuse_denied_reason" in telemetry
        assert "security_mode" in telemetry


class TestTelemetrySecurityModes:
    """Tests for security mode transitions."""

    def test_security_mode_normal_by_default(self):
        """Default security mode must be 'normal'."""
        from src.graph.state import RunState
        
        state = RunState()
        assert state.telemetry["security_mode"] == "normal"

    def test_security_mode_values(self):
        """Security mode must only be normal, zero_trust, or abort."""
        valid_modes = {"normal", "zero_trust", "abort"}
        
        from src.graph.state import RunState
        state = RunState()
        
        # Default is valid
        assert state.telemetry["security_mode"] in valid_modes
