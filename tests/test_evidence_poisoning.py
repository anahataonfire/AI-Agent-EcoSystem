"""
Evidence Poisoning & Cross-Run Contamination Defense Tests.

These tests enforce that evidence cannot be reused across incompatible queries.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestEvidencePoisoningDefense:
    """Tests for cross-query evidence contamination prevention."""

    def test_reject_cross_query_evidence(self):
        """Evidence from different query_hash must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Evidence was stored with a DIFFERENT query hash
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Some news"},
                "metadata": {
                    "query_hash": "DIFFERENT_HASH",
                    "lifecycle": "active",
                    "type": "rss_item"
                }
            }
            
            from src.graph.workflow import validate_evidence_scope
            
            # Current query has different hash
            is_valid = validate_evidence_scope("ev_abc123", current_query_hash="CURRENT_HASH")
            
            assert is_valid is False

    def test_allow_same_query_evidence(self):
        """Evidence from same query_hash must be allowed."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Some news"},
                "metadata": {
                    "query_hash": "SAME_HASH",
                    "lifecycle": "active",
                    "type": "rss_item"
                }
            }
            
            from src.graph.workflow import validate_evidence_scope
            
            is_valid = validate_evidence_scope("ev_abc123", current_query_hash="SAME_HASH")
            
            assert is_valid is True

    def test_allow_global_evidence_without_query_hash(self):
        """System/global evidence (no query_hash) may be cited."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "System artifact"},
                "metadata": {
                    "query_hash": None,  # Global/system artifact
                    "lifecycle": "active",
                    "type": "system"
                }
            }
            
            from src.graph.workflow import validate_evidence_scope
            
            is_valid = validate_evidence_scope("ev_system001", current_query_hash="ANY_HASH")
            
            assert is_valid is True

    def test_reject_mixed_evidence(self):
        """One valid + one poisoned citation must fail."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            def mock_get(eid):
                if eid == "ev_good":
                    return {
                        "payload": {},
                        "metadata": {"query_hash": "CURRENT", "lifecycle": "active"}
                    }
                elif eid == "ev_bad":
                    return {
                        "payload": {},
                        "metadata": {"query_hash": "OTHER", "lifecycle": "active"}
                    }
                return None
            
            mock_instance.get_with_metadata.side_effect = mock_get
            
            from src.graph.workflow import validate_evidence_scope
            
            # Good one passes
            assert validate_evidence_scope("ev_good", "CURRENT") is True
            # Bad one fails
            assert validate_evidence_scope("ev_bad", "CURRENT") is False

    def test_reuse_respects_scope(self):
        """Reused report must fail if evidence query_hash mismatches."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            # Report was created with OLD_HASH
            # But evidence was overwritten with NEW_HASH
            mock_instance.get_with_metadata.return_value = {
                "payload": {"title": "Evidence"},
                "metadata": {
                    "query_hash": "NEW_HASH",  # Doesn't match report's original hash
                    "lifecycle": "active"
                }
            }
            
            from src.graph.workflow import validate_evidence_scope
            
            # Trying to reuse with OLD_HASH should fail
            is_valid = validate_evidence_scope("ev_reused", current_query_hash="OLD_HASH")
            
            assert is_valid is False


class TestEvidenceLifecycle:
    """Tests for evidence lifecycle state enforcement."""

    def test_reject_expired_evidence(self):
        """Expired evidence must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            mock_instance.get_with_metadata.return_value = {
                "payload": {},
                "metadata": {
                    "query_hash": "HASH",
                    "lifecycle": "expired"
                }
            }
            
            from src.graph.workflow import validate_evidence_lifecycle
            
            is_valid = validate_evidence_lifecycle("ev_expired")
            assert is_valid is False

    def test_reject_revoked_evidence(self):
        """Revoked evidence must be rejected."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            mock_instance.get_with_metadata.return_value = {
                "payload": {},
                "metadata": {
                    "query_hash": "HASH",
                    "lifecycle": "revoked"
                }
            }
            
            from src.graph.workflow import validate_evidence_lifecycle
            
            is_valid = validate_evidence_lifecycle("ev_revoked")
            assert is_valid is False

    def test_accept_active_evidence(self):
        """Active evidence must be accepted."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            mock_instance.get_with_metadata.return_value = {
                "payload": {},
                "metadata": {
                    "query_hash": "HASH",
                    "lifecycle": "active"
                }
            }
            
            from src.graph.workflow import validate_evidence_lifecycle
            
            is_valid = validate_evidence_lifecycle("ev_active")
            assert is_valid is True

    def test_default_lifecycle_is_active(self):
        """Evidence without lifecycle should default to active."""
        with patch("src.graph.workflow.EvidenceStore") as mock_store:
            mock_instance = mock_store.return_value
            
            mock_instance.get_with_metadata.return_value = {
                "payload": {},
                "metadata": {
                    "query_hash": "HASH"
                    # No lifecycle field
                }
            }
            
            from src.graph.workflow import validate_evidence_lifecycle
            
            is_valid = validate_evidence_lifecycle("ev_no_lifecycle")
            assert is_valid is True

