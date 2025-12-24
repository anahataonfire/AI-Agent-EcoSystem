"""
Kill-Switch Registry Tests.

Tests that kill switches properly halt execution paths
without mutating identity or state.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestKillSwitchHalts:
    """Tests that kill switches halt the appropriate execution paths."""

    def test_reuse_disabled_halts(self):
        """When TRUE_REUSE is disabled, reuse path must halt."""
        with patch("src.core.kill_switches.DISABLE_TRUE_REUSE", True):
            from src.core.kill_switches import check_kill_switch, build_halt_message
            
            halted, reason = check_kill_switch("TRUE_REUSE")
            
            assert halted is True
            assert "True Reuse" in reason
            assert "disabled by operator" in reason
            
            # Verify halt message format
            message = build_halt_message(reason)
            assert "# Execution Halted" in message
            assert "True Reuse" in message

    def test_grounding_disabled_halts(self):
        """When GROUNDING is disabled, grounding path must halt."""
        with patch("src.core.kill_switches.DISABLE_GROUNDING", True):
            from src.core.kill_switches import check_kill_switch, build_halt_message
            
            halted, reason = check_kill_switch("GROUNDING")
            
            assert halted is True
            assert "Grounding" in reason
            assert "disabled by operator" in reason
            
            message = build_halt_message(reason)
            assert "# Execution Halted" in message

    def test_evidence_reuse_disabled_halts(self):
        """When EVIDENCE_REUSE is disabled, evidence reuse must halt."""
        with patch("src.core.kill_switches.DISABLE_EVIDENCE_REUSE", True):
            from src.core.kill_switches import check_kill_switch
            
            halted, reason = check_kill_switch("EVIDENCE_REUSE")
            
            assert halted is True
            assert "Evidence Reuse" in reason

    def test_switches_enabled_by_default(self):
        """All switches should be disabled (False) by default."""
        from src.core.kill_switches import get_all_switch_states
        
        states = get_all_switch_states()
        
        assert states["TRUE_REUSE"] is False
        assert states["EVIDENCE_REUSE"] is False
        assert states["GROUNDING"] is False

    def test_enabled_switch_returns_false(self):
        """When switch is not disabled, check returns (False, None)."""
        with patch("src.core.kill_switches.DISABLE_TRUE_REUSE", False):
            from src.core.kill_switches import check_kill_switch
            
            halted, reason = check_kill_switch("TRUE_REUSE")
            
            assert halted is False
            assert reason is None


class TestKillSwitchSafety:
    """Tests that kill switches do not mutate identity or state."""

    def test_switches_do_not_mutate_identity(self):
        """Kill switch activation must not write to identity store."""
        with patch("src.core.kill_switches.DISABLE_TRUE_REUSE", True):
            from src.core.kill_switches import check_kill_switch
            
            # Track if identity_manager is called
            with patch("src.core.identity_manager.update_identity") as mock_update:
                halted, reason = check_kill_switch("TRUE_REUSE")
                
                # Identity manager should NOT be called during switch check
                mock_update.assert_not_called()

    def test_switches_do_not_mutate_evidence_store(self):
        """Kill switch activation must not write to evidence store."""
        with patch("src.core.kill_switches.DISABLE_GROUNDING", True):
            from src.core.kill_switches import check_kill_switch
            
            with patch("src.core.evidence_store.EvidenceStore") as mock_store:
                halted, reason = check_kill_switch("GROUNDING")
                
                # Evidence store should NOT be instantiated during switch check
                mock_store.assert_not_called()

    def test_invalid_switch_name_raises(self):
        """Unknown switch name must raise ValueError."""
        from src.core.kill_switches import check_kill_switch
        
        with pytest.raises(ValueError) as exc_info:
            check_kill_switch("INVALID_SWITCH")
        
        assert "Unknown kill switch" in str(exc_info.value)
        assert "INVALID_SWITCH" in str(exc_info.value)


class TestKillSwitchTelemetry:
    """Tests that kill switch events are properly tracked."""

    def test_halt_message_format(self):
        """Halt messages must follow the specified format."""
        from src.core.kill_switches import build_halt_message
        
        message = build_halt_message("Test reason")
        
        assert message.startswith("# Execution Halted")
        assert "Reason:" in message
        assert "Test reason" in message
