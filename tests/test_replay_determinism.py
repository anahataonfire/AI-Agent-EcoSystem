"""
Replay Determinism Tests (Prompt AI).

Tests for byte-for-byte replay verification.
"""

import pytest


class TestReplayDeterminism:
    """Tests for replay determinism verification."""

    def test_identical_replay_passes(self):
        """Identical outputs should pass verification."""
        from src.core.replay_verifier import verify_replay_determinism
        
        original_state = {
            "final_report": "# Report\n\nFindings: X happened [EVID:ev_001].",
            "telemetry": {"grounding_failures": 0, "evidence_rejections": 0},
            "ledger_hashes": ["abc123", "def456"],
        }
        
        replay_state = {
            "final_report": "# Report\n\nFindings: X happened [EVID:ev_001].",
            "telemetry": {"grounding_failures": 0, "evidence_rejections": 0},
            "ledger_hashes": ["abc123", "def456"],
        }
        
        # Should not raise
        verify_replay_determinism(original_state, replay_state)

    def test_mutated_replay_fails(self):
        """Different report content should fail verification."""
        from src.core.replay_verifier import verify_replay_determinism, DeterminismViolationError
        
        original_state = {
            "final_report": "# Report\n\nFindings: X happened.",
            "telemetry": {},
        }
        
        replay_state = {
            "final_report": "# Report\n\nFindings: Y happened.",  # Different!
            "telemetry": {},
        }
        
        with pytest.raises(DeterminismViolationError) as exc_info:
            verify_replay_determinism(original_state, replay_state)
        
        assert "mismatch" in str(exc_info.value).lower()

    def test_ledger_hash_mismatch_fails(self):
        """Different ledger hashes should fail verification."""
        from src.core.replay_verifier import verify_replay_determinism, DeterminismViolationError
        
        original_state = {
            "final_report": "# Report",
            "telemetry": {},
            "ledger_hashes": ["abc123", "def456"],
        }
        
        replay_state = {
            "final_report": "# Report",
            "telemetry": {},
            "ledger_hashes": ["abc123", "DIFFERENT"],  # Hash mismatch!
        }
        
        with pytest.raises(DeterminismViolationError) as exc_info:
            verify_replay_determinism(original_state, replay_state)
        
        assert "ledger" in str(exc_info.value).lower()


class TestTimestampTolerance:
    """Tests for timestamp tolerance handling."""

    def test_timestamp_tolerance(self):
        """Reports differing only in timestamps should pass."""
        from src.core.replay_verifier import compare_reports
        
        original = "Report generated at 2024-01-15T10:00:00Z"
        replay = "Report generated at 2024-01-15T10:00:01Z"  # 1 second later
        
        is_same, _ = compare_reports(original, replay)
        assert is_same is True
