"""
Deterministic Evidence Ordering Tests.

Tests that ensure stable evidence ordering in all reports and reuse paths
to prevent subtle replay drift.

Runtime target: <0.2s per test
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEvidenceOrdering:
    """Tests for deterministic evidence ordering."""

    def test_get_sorted_citations(self):
        """Citations should be extracted and sorted lexicographically."""
        from src.graph.workflow import get_sorted_citations
        
        report = """# Report
        
        Unsorted citations: [EVID:ev_zebra] [EVID:ev_alpha] [EVID:ev_middle].
        """
        
        sorted_cites = get_sorted_citations(report)
        
        assert sorted_cites == ["ev_alpha", "ev_middle", "ev_zebra"]

    def test_reorder_unsorted_citations(self):
        """Verify sorting produces deterministic order regardless of input."""
        from src.graph.workflow import get_sorted_citations
        
        # Same citations in different orders should produce same sorted output
        report1 = "[EVID:ev_c] [EVID:ev_a] [EVID:ev_b]"
        report2 = "[EVID:ev_b] [EVID:ev_a] [EVID:ev_c]"
        report3 = "[EVID:ev_a] [EVID:ev_b] [EVID:ev_c]"
        
        sorted1 = get_sorted_citations(report1)
        sorted2 = get_sorted_citations(report2)
        sorted3 = get_sorted_citations(report3)
        
        # All should be identical
        assert sorted1 == sorted2 == sorted3
        assert sorted1 == ["ev_a", "ev_b", "ev_c"]

    def test_accept_sorted_order(self):
        """Report with citations in sorted order should pass validation."""
        from src.graph.workflow import validate_evidence_ordering
        
        sorted_report = """# Report
        
        First citation [EVID:ev_001], second [EVID:ev_002], third [EVID:ev_003].
        """
        
        # Should not raise
        validate_evidence_ordering(sorted_report)

    def test_reject_unsorted_order(self):
        """Report with unsorted first-occurrence order should be detected."""
        from src.graph.workflow import validate_evidence_ordering, EvidenceOrderingError
        
        unsorted_report = """# Report
        
        Out of order: [EVID:ev_zzz] first, then [EVID:ev_aaa] second.
        """
        
        with pytest.raises(EvidenceOrderingError) as exc_info:
            validate_evidence_ordering(unsorted_report)
        
        assert "Non-deterministic" in str(exc_info.value)

    def test_empty_citations_passes(self):
        """Report with no citations should pass ordering validation."""
        from src.graph.workflow import validate_evidence_ordering
        
        no_citations = """# Report
        
        This report has no citations.
        """
        
        # Should not raise
        validate_evidence_ordering(no_citations)


class TestReuseOrderingEnforcement:
    """Tests that reuse path verifies ordering before replay."""

    def test_reject_reuse_with_unsorted_order(self):
        """True Reuse must verify ordering before replay."""
        from src.graph.workflow import validate_evidence_ordering, EvidenceOrderingError
        
        # Simulate a cached report with unsorted citations
        cached_report = """# Cached Report
        
        This was cached with [EVID:ev_zzz] before [EVID:ev_aaa].
        
        ### Execution Provenance
        - Mode: Normal
        """
        
        # Reuse path should detect and reject
        with pytest.raises(EvidenceOrderingError):
            validate_evidence_ordering(cached_report)

    def test_accept_reuse_with_sorted_order(self):
        """Reuse of properly sorted report should succeed."""
        from src.graph.workflow import validate_evidence_ordering
        
        cached_report = """# Cached Report
        
        Properly ordered: [EVID:ev_001] then [EVID:ev_002] then [EVID:ev_003].
        
        ### Execution Provenance
        - Mode: Normal
        """
        
        # Should not raise
        validate_evidence_ordering(cached_report)


class TestOrderingDeterminism:
    """Tests that ordering is truly deterministic across runs."""

    def test_duplicate_citations_handled(self):
        """Duplicate citations should be deduplicated in sorted output."""
        from src.graph.workflow import get_sorted_citations
        
        report = """[EVID:ev_a] [EVID:ev_a] [EVID:ev_b] [EVID:ev_a]"""
        
        sorted_cites = get_sorted_citations(report)
        
        # Should deduplicate
        assert sorted_cites == ["ev_a", "ev_b"]

    def test_ordering_stable_across_calls(self):
        """Multiple calls should produce identical ordering."""
        from src.graph.workflow import get_sorted_citations
        
        report = "[EVID:ev_x] [EVID:ev_y] [EVID:ev_z]"
        
        results = [get_sorted_citations(report) for _ in range(10)]
        
        # All results should be identical
        assert all(r == results[0] for r in results)
