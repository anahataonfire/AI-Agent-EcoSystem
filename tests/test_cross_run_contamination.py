"""
Cross-Run Evidence Contamination Tests (Prompt Y).

Tests that evidence from one run cannot be cited in another.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestCrossRunContamination:
    """Tests for cross-run evidence contamination prevention."""

    def test_reject_cross_query_citation(self):
        """Evidence from different query_hash must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence was stored with a DIFFERENT query hash
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Some news"},
                "metadata": {
                    "query_hash": "OLD_QUERY_HASH",
                    "lifecycle": "active",
                    "type": "rss_item"
                }
            }
            
            from src.graph.workflow import validate_evidence_scope
            
            # Current query has a DIFFERENT hash
            is_valid = validate_evidence_scope("ev_abc123", current_query_hash="CURRENT_QUERY_HASH")
            
            assert is_valid is False

    def test_allow_global_artifact(self):
        """Global artifacts (query_hash = None) should be allowed."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Global artifact has no query_hash
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "System config"},
                "metadata": {
                    "query_hash": None,  # Global artifact
                    "lifecycle": "active",
                    "type": "system"
                }
            }
            
            from src.graph.workflow import validate_evidence_scope
            
            is_valid = validate_evidence_scope("ev_global001", current_query_hash="ANY_HASH")
            
            assert is_valid is True

    def test_accept_same_query_hash(self):
        """Evidence from same query should be accepted."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Current news"},
                "metadata": {
                    "query_hash": "SAME_HASH",
                    "lifecycle": "active",
                    "type": "rss_item"
                }
            }
            
            from src.graph.workflow import validate_evidence_scope
            
            is_valid = validate_evidence_scope("ev_current001", current_query_hash="SAME_HASH")
            
            assert is_valid is True


class TestCrossRunErrorMessage:
    """Tests for explicit cross-run error messaging."""

    def test_contamination_error_message(self):
        """Cross-run contamination should produce explicit error message."""
        from src.graph.workflow import EvidenceContaminationError
        
        error = EvidenceContaminationError("Evidence contamination detected: ev_cross123")
        
        assert "contamination" in str(error).lower()
        assert "ev_cross123" in str(error)
