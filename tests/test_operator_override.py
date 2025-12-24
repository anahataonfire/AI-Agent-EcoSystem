"""
Operator Override Tests (Prompt AJ).

Tests for operator override gate with signed tokens.
"""

import pytest


class TestOverrideSignature:
    """Tests that overrides require valid signatures."""

    def test_override_requires_signature(self):
        """Override without valid token must be rejected."""
        from src.core.operator_gate import apply_override, InvalidOverrideTokenError
        
        with pytest.raises(InvalidOverrideTokenError):
            apply_override("invalid-token-no-signature")

    def test_valid_token_accepted(self):
        """Valid signed token should be accepted."""
        from src.core.operator_gate import generate_override_token, apply_override
        from src.core.run_ledger import reset_ledger
        import tempfile
        import os
        
        reset_ledger()
        
        token = generate_override_token(
            override_type="reuse_denial",
            reason="Manual investigation required",
            operator_id="admin@example.com"
        )
        
        result = apply_override(token)
        
        assert result["override_applied"] is True
        assert result["override_type"] == "reuse_denial"


class TestOverrideLogging:
    """Tests that overrides are logged to ledger."""

    def test_override_logged(self):
        """Override must be logged to run ledger."""
        from src.core.operator_gate import generate_override_token, apply_override
        from src.core.run_ledger import RunLedger, reset_ledger, EVENT_OPERATOR_OVERRIDE
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Reset and use fresh ledger
            reset_ledger()
            
            token = generate_override_token(
                override_type="kill_switch",
                reason="Emergency maintenance",
                operator_id="ops@example.com"
            )
            
            apply_override(token)
            
            # Check ledger was written
            from src.core.run_ledger import get_ledger
            ledger = get_ledger()
            entries = ledger.get_entries(ledger.run_id)
            
            override_entries = [e for e in entries if e["event"] == EVENT_OPERATOR_OVERRIDE]
            assert len(override_entries) >= 1


class TestOverrideIdentitySafety:
    """Tests that overrides never mutate identity."""

    def test_override_does_not_mutate_identity(self):
        """Override attempting identity mutation must be rejected."""
        from src.core.operator_gate import (
            generate_override_token,
            apply_override,
            OverrideIdentityMutationError
        )
        from src.core.run_ledger import reset_ledger
        
        reset_ledger()
        
        token = generate_override_token(
            override_type="reuse_denial",
            reason="Test",
            operator_id="admin"
        )
        
        with pytest.raises(OverrideIdentityMutationError):
            apply_override(token, mutates_identity=True)
