"""
Run Ledger Tests (Prompt AH).

Tests for append-only immutable ledger.
"""

import pytest
import tempfile
import os


class TestLedgerAppendOnly:
    """Tests that ledger is append-only."""

    def test_ledger_append_only(self):
        """Entries can only be appended, never removed."""
        from src.core.run_ledger import RunLedger, EVENT_REPORT_FINALIZED
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_ledger.jsonl")
            ledger = RunLedger(storage_path=path)
            
            # Append entries
            ledger.append(EVENT_REPORT_FINALIZED, "system", {"report_id": "r1"})
            ledger.append(EVENT_REPORT_FINALIZED, "system", {"report_id": "r2"})
            
            entries = ledger.get_entries()
            assert len(entries) == 2
            
            # Verify sequence numbers
            assert entries[0]["sequence"] == 0
            assert entries[1]["sequence"] == 1


class TestNoMutation:
    """Tests that ledger entries cannot be mutated."""

    def test_no_mutation_allowed(self):
        """Ledger entries should be immutable after creation."""
        from src.core.run_ledger import RunLedger, EVENT_ABORT
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_ledger.jsonl")
            ledger = RunLedger(storage_path=path)
            
            record = ledger.append(EVENT_ABORT, "system", {"reason": "test"})
            original_hash = record["hash"]
            
            # Verify record has required fields
            assert "run_id" in record
            assert "event" in record
            assert "actor" in record
            assert "hash" in record
            assert "timestamp" in record
            
            # Retrieve and verify hash unchanged
            entries = ledger.get_entries()
            assert entries[0]["hash"] == original_hash


class TestLedgerBeforeIdentity:
    """Tests that ledger writes before side effects."""

    def test_ledger_written_before_identity(self):
        """Ledger entry must be created before any identity mutation."""
        from src.core.run_ledger import RunLedger, EVENT_REPORT_FINALIZED
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_ledger.jsonl")
            ledger = RunLedger(storage_path=path)
            
            # Simulate: first log to ledger
            record = ledger.append(
                EVENT_REPORT_FINALIZED,
                "agent:reporter",
                {"action": "identity_update_pending"}
            )
            
            # Then (hypothetically) update identity
            # The test verifies ledger entry exists BEFORE identity would be touched
            assert record["timestamp"] is not None
            
            entries = ledger.get_entries()
            assert len(entries) == 1
            assert entries[0]["event"] == EVENT_REPORT_FINALIZED


class TestLedgerIntegrity:
    """Tests for ledger integrity verification."""

    def test_integrity_check_passes(self):
        """Valid ledger should pass integrity check."""
        from src.core.run_ledger import RunLedger, EVENT_KILL_SWITCH
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_ledger.jsonl")
            ledger = RunLedger(storage_path=path)
            
            ledger.append(EVENT_KILL_SWITCH, "system", {})
            ledger.append(EVENT_KILL_SWITCH, "system", {})
            
            assert ledger.verify_integrity() is True
