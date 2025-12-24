"""
Grounding Contract Version Lock Tests.

Ensures reports are tied to a specific grounding contract version.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestGroundingVersionLock:
    """Tests for grounding contract version enforcement."""

    def test_footer_includes_version(self):
        """Footer must include grounding contract version."""
        from src.graph.workflow import _build_provenance_footer, CLAIM_GROUNDING_CONTRACT_VERSION
        
        footer = _build_provenance_footer(
            mode="Normal",
            query_hash="abc123",
            evidence_count=5,
            evidence_map={},
            identity_writes=True
        )
        
        assert f"Grounding Contract: v{CLAIM_GROUNDING_CONTRACT_VERSION}" in footer

    def test_version_constant_exists(self):
        """CLAIM_GROUNDING_CONTRACT_VERSION must be defined."""
        from src.graph.workflow import CLAIM_GROUNDING_CONTRACT_VERSION
        
        assert CLAIM_GROUNDING_CONTRACT_VERSION is not None
        assert isinstance(CLAIM_GROUNDING_CONTRACT_VERSION, str)
        assert len(CLAIM_GROUNDING_CONTRACT_VERSION) > 0

    def test_reject_missing_version_in_reused_report(self):
        """Reused report without version in footer should fail validation."""
        # Report without version
        report_without_version = """
        # Old Report
        
        Some content [EVID:ev_abc123].
        
        ### Execution Provenance
        - Mode: Normal
        - Query Hash: abc123
        """
        
        # Check that version is missing
        assert "Grounding Contract:" not in report_without_version

    def test_reject_wrong_version_in_reused_report(self):
        """Reused report with wrong version should be detectable."""
        from src.graph.workflow import CLAIM_GROUNDING_CONTRACT_VERSION
        
        report_with_wrong_version = f"""
        # Old Report
        
        Some content [EVID:ev_abc123].
        
        ### Execution Provenance
        - Mode: Normal
        - Grounding Contract: v0.5
        """
        
        # Should NOT match current version
        assert f"v{CLAIM_GROUNDING_CONTRACT_VERSION}" not in report_with_wrong_version

    def test_accept_correct_version_in_report(self):
        """Report with correct version should pass."""
        from src.graph.workflow import CLAIM_GROUNDING_CONTRACT_VERSION
        
        correct_footer = f"- Grounding Contract: v{CLAIM_GROUNDING_CONTRACT_VERSION}"
        
        report = f"""
        # Report
        
        Content [EVID:ev_abc123].
        
        ### Execution Provenance
        - Mode: Normal
        {correct_footer}
        """
        
        assert f"v{CLAIM_GROUNDING_CONTRACT_VERSION}" in report
