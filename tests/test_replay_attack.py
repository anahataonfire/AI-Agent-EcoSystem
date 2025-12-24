"""
Replay & Timing Attack Defense Tests (Prompt AA).

Tests that detect and block time-based replay attacks using stale evidence.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


class TestEvidenceFreshness:
    """Tests for evidence freshness validation."""

    def test_reject_stale_evidence(self):
        """Evidence older than 30 minutes must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence created 45 minutes ago
            old_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Old news"},
                "metadata": {"type": "rss_item"},
                "created_at": old_time
            }
            
            from src.graph.workflow import validate_evidence_freshness
            
            is_fresh = validate_evidence_freshness("ev_old123")
            
            assert is_fresh is False

    def test_accept_fresh_evidence(self):
        """Evidence created within 30 minutes should be accepted."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence created 10 minutes ago
            recent_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Fresh news"},
                "metadata": {"type": "rss_item"},
                "created_at": recent_time
            }
            
            from src.graph.workflow import validate_evidence_freshness
            
            is_fresh = validate_evidence_freshness("ev_fresh123")
            
            assert is_fresh is True

    def test_evidence_at_boundary(self):
        """Evidence just under 30 minutes should be accepted."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence created 29 minutes ago (just under limit)
            boundary_time = (datetime.now(timezone.utc) - timedelta(minutes=29)).isoformat()
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Boundary news"},
                "metadata": {"type": "rss_item"},
                "created_at": boundary_time
            }
            
            from src.graph.workflow import validate_evidence_freshness
            
            is_fresh = validate_evidence_freshness("ev_boundary123")
            
            assert is_fresh is True


class TestReplayAttackOnReuse:
    """Tests that True Reuse validates evidence freshness."""

    def test_reject_reuse_with_expired_evidence(self):
        """Reuse must fail if underlying evidence is expired."""
        from src.graph.workflow import validate_all_evidence_freshness, EvidenceFreshnessError
        
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence is 45 minutes old
            old_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Old data"},
                "metadata": {"type": "rss_item"},
                "created_at": old_time
            }
            
            with pytest.raises(EvidenceFreshnessError) as exc_info:
                validate_all_evidence_freshness(["ev_expired001"])
            
            assert "replay attack" in str(exc_info.value).lower()

    def test_accept_reuse_with_fresh_evidence(self):
        """Reuse should succeed with fresh evidence."""
        from src.graph.workflow import validate_all_evidence_freshness
        
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence is 5 minutes old
            fresh_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Fresh data"},
                "metadata": {"type": "rss_item"},
                "created_at": fresh_time
            }
            
            # Should not raise
            validate_all_evidence_freshness(["ev_fresh001", "ev_fresh002"])


class TestFreshnessErrorMessage:
    """Tests for explicit freshness error messaging."""

    def test_freshness_error_message(self):
        """Freshness error should include replay attack message."""
        from src.graph.workflow import EvidenceFreshnessError
        
        error = EvidenceFreshnessError("Evidence expired — replay attack protection triggered: ev_old123")
        
        assert "replay attack" in str(error).lower()
        assert "ev_old123" in str(error)
