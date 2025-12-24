"""
Tests for reset frequency guard.

Verifies:
- Reset tracking works
- Warnings emitted at threshold
- No automatic reset loops
- Ledger logging before reset
"""

import pytest
from src.core.reset_guard import (
    ResetGuard, 
    DTL_STRAT_014,
    MAX_RESETS_PER_WINDOW
)


class TestResetGuard:
    """Tests for reset frequency guard."""

    def test_reset_logged_to_ledger(self):
        """Every reset is logged to ledger."""
        guard = ResetGuard()
        
        guard.record_reset(
            reason="weight_collapse",
            weights_before={"a": 0.1},
            weights_after={"a": 1.0}
        )
        
        events = [e["event"] for e in guard._ledger_entries]
        assert "POLICY_MEMORY_RESET" in events

    def test_warning_at_threshold(self):
        """Warning emitted when threshold exceeded."""
        guard = ResetGuard()
        
        # Exceed threshold
        warnings = guard.simulate_instability(count=MAX_RESETS_PER_WINDOW + 1)
        
        assert len(warnings) > 0
        assert warnings[-1].failure_code == DTL_STRAT_014

    def test_no_warning_below_threshold(self):
        """No warning when under threshold."""
        guard = ResetGuard()
        
        # Stay under threshold
        for i in range(MAX_RESETS_PER_WINDOW - 1):
            guard.increment_run()
            warning = guard.record_reset(
                reason=f"test_{i}",
                weights_before={"a": 0.5},
                weights_after={"a": 1.0}
            )
        
        # No warnings yet
        warning_events = [e for e in guard._ledger_entries if e["event"] == "RESET_INSTABILITY_WARNING"]
        assert len(warning_events) == 0

    def test_reset_stats_tracked(self):
        """Reset statistics are tracked."""
        guard = ResetGuard()
        guard._run_count = 100
        
        guard.record_reset("test", {"a": 0.1}, {"a": 1.0})
        guard.record_reset("test2", {"a": 0.1}, {"a": 1.0})
        
        stats = guard.get_reset_stats()
        
        assert stats["total_resets"] == 2
        assert stats["run_count"] == 100
        assert stats["reset_rate"] == 0.02

    def test_provenance_section_generated(self):
        """Provenance footer section can be generated."""
        guard = ResetGuard()
        guard._run_count = 50
        guard.record_reset("collapse", {"a": 0.1}, {"a": 1.0})
        
        provenance = guard.generate_provenance_section()
        
        assert "Reset Statistics" in provenance
        assert "Total Resets: 1" in provenance

    def test_compliance_export(self):
        """Data can be exported for compliance."""
        guard = ResetGuard()
        guard.simulate_instability(3)
        
        export = guard.export_for_compliance()
        
        assert "reset_guard" in export
        assert "stats" in export["reset_guard"]
        assert "history" in export["reset_guard"]

    def test_no_automatic_reset_loops(self):
        """Reset guard does not auto-reset."""
        guard = ResetGuard()
        
        # Trigger many resets
        for i in range(20):
            guard.record_reset(
                reason=f"loop_test_{i}",
                weights_before={"a": 0.1},
                weights_after={"a": 1.0}
            )
        
        # Guard only records, never auto-triggers reset
        # (Implementation must be manual or external)
        assert len(guard._reset_history) == 20
