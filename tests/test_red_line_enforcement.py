"""
Red-Line Enforcement Tests (Prompt AM).

Tests for absolute prohibition enforcement.
"""

import pytest


class TestIdentityMutationRedLine:
    """Tests for identity mutation red-line."""

    def test_identity_mutation_outside_reporter(self):
        """Identity mutation outside reporter must trigger red-line."""
        from src.core.red_lines import (
            validate_no_red_line_violation,
            RedLineViolationError,
            RED_LINE_IDENTITY_MUTATION
        )
        from src.core.run_ledger import reset_ledger
        
        reset_ledger()
        
        with pytest.raises(RedLineViolationError) as exc_info:
            validate_no_red_line_violation("write_identity", "thinker")
        
        assert "SECURITY BREACH" in str(exc_info.value)

    def test_reporter_identity_allowed(self):
        """Reporter should be allowed to write identity."""
        from src.core.red_lines import check_identity_mutation_allowed
        
        allowed, _ = check_identity_mutation_allowed("reporter")
        assert allowed is True
        
        allowed, _ = check_identity_mutation_allowed("executor")
        assert allowed is False


class TestUnvalidatedReuseRedLine:
    """Tests for unvalidated reuse red-line."""

    def test_reuse_without_validation(self):
        """Reuse without validation must trigger red-line."""
        from src.core.red_lines import (
            validate_no_red_line_violation,
            RedLineViolationError
        )
        from src.core.run_ledger import reset_ledger
        
        reset_ledger()
        
        with pytest.raises(RedLineViolationError):
            validate_no_red_line_violation(
                "reuse_evidence",
                "executor",
                context={"validated": False}
            )

    def test_validated_reuse_allowed(self):
        """Validated reuse should not trigger red-line."""
        from src.core.red_lines import validate_no_red_line_violation
        from src.core.run_ledger import reset_ledger
        
        reset_ledger()
        
        # Should not raise
        validate_no_red_line_violation(
            "reuse_evidence",
            "executor",
            context={"validated": True}
        )


class TestRedLineLogging:
    """Tests that red-lines are logged."""

    def test_red_line_logged_to_ledger(self):
        """Red-line violations must be logged to ledger."""
        from src.core.red_lines import trigger_red_line, RedLineViolationError, RED_LINE_LEDGER_TAMPERING
        from src.core.run_ledger import get_ledger, reset_ledger, EVENT_RED_LINE_VIOLATION
        
        reset_ledger()
        
        try:
            trigger_red_line(RED_LINE_LEDGER_TAMPERING, "unknown", "Test tampering")
        except RedLineViolationError:
            pass
        
        ledger = get_ledger()
        entries = ledger.get_entries(ledger.run_id)
        
        red_line_entries = [e for e in entries if e["event"] == EVENT_RED_LINE_VIOLATION]
        assert len(red_line_entries) >= 1


class TestAllRedLinesListed:
    """Tests that all red-lines are defined."""

    def test_all_red_lines_defined(self):
        """All required red-lines must be defined."""
        from src.core.red_lines import ALL_RED_LINES
        
        required = {
            "identity_mutation_outside_reporter",
            "ungrounded_factual_output",
            "cross_agent_instruction_execution",
            "evidence_reuse_without_validation",
            "ledger_tampering_attempt",
        }
        
        assert required == ALL_RED_LINES


class TestSecurityBreachMessage:
    """Tests for security breach message format."""

    def test_security_breach_format(self):
        """Red-line should produce SECURITY BREACH message."""
        from src.core.red_lines import get_red_line_message, RED_LINE_IDENTITY_MUTATION
        
        message = get_red_line_message(RED_LINE_IDENTITY_MUTATION)
        
        assert "SECURITY BREACH" in message
        assert "Red-Line violation" in message
