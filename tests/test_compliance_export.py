"""
Compliance Export Tests (Prompt AL).

Tests for read-only compliance snapshot export.
"""

import pytest
import json


class TestExportComplete:
    """Tests that export contains all required data."""

    def test_export_complete(self):
        """Export must contain all required fields."""
        from src.core.compliance_export import create_compliance_export
        
        export = create_compliance_export(
            run_id="test-run-123",
            ledger_entries=[
                {"sequence": 0, "event": "REPORT_FINALIZED", "timestamp": "2024-01-15T10:00:00Z"}
            ],
            evidence_ids=["ev_001", "ev_002"],
            provenance_footer="### Execution Provenance\n- Mode: Normal",
            kill_switch_state={"TRUE_REUSE": False},
            telemetry={"grounding_failures": 0}
        )
        
        data = export.get_export()
        
        # Verify all required sections present
        assert "metadata" in data
        assert "run_ledger" in data
        assert "evidence_ids" in data
        assert "provenance_footer" in data
        assert "kill_switch_state" in data
        
        # Verify metadata
        assert data["metadata"]["run_id"] == "test-run-123"
        assert "grounding_contract_version" in data["metadata"]


class TestExportReadOnly:
    """Tests that export is read-only."""

    def test_export_read_only(self):
        """Export should return copies, not mutable references."""
        from src.core.compliance_export import create_compliance_export
        
        export = create_compliance_export(
            run_id="test-run",
            ledger_entries=[],
            evidence_ids=["ev_001"],
            provenance_footer="footer",
            kill_switch_state={}
        )
        
        data1 = export.get_export()
        data2 = export.get_export()
        
        # Mutating one should not affect the other
        data1["evidence_ids"].append("ev_rogue")
        
        assert "ev_rogue" not in data2["evidence_ids"]


class TestExportMatchesRun:
    """Tests that export matches actual run."""

    def test_export_matches_run(self):
        """Export should match actual run data."""
        from src.core.compliance_export import create_compliance_export
        
        evidence_ids = ["ev_001", "ev_002", "ev_003"]
        ledger_entries = [{"sequence": 0}, {"sequence": 1}]
        
        export = create_compliance_export(
            run_id="test-run",
            ledger_entries=ledger_entries,
            evidence_ids=evidence_ids,
            provenance_footer="footer",
            kill_switch_state={}
        )
        
        # Should match
        assert export.verify_matches_run(evidence_ids, len(ledger_entries)) is True
        
        # Should not match with different data
        assert export.verify_matches_run(["ev_different"], len(ledger_entries)) is False


class TestExportDeterministicOrdering:
    """Tests that export has deterministic ordering."""

    def test_deterministic_ordering(self):
        """Export should have deterministic ordering."""
        from src.core.compliance_export import create_compliance_export
        
        # Create with unordered evidence
        export = create_compliance_export(
            run_id="test",
            ledger_entries=[{"sequence": 1}, {"sequence": 0}],
            evidence_ids=["ev_c", "ev_a", "ev_b"],
            provenance_footer="",
            kill_switch_state={"z_switch": True, "a_switch": False}
        )
        
        data = export.get_export()
        
        # Evidence should be sorted
        assert data["evidence_ids"] == ["ev_a", "ev_b", "ev_c"]
        
        # Ledger should be sorted by sequence
        assert data["run_ledger"][0]["sequence"] == 0
        
        # Kill switches should be sorted
        keys = list(data["kill_switch_state"].keys())
        assert keys == sorted(keys)
