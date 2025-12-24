"""
Failure Codes Tests (Prompt AK).

Tests for canonical failure codes.
"""

import pytest


class TestFailureCodeUniqueness:
    """Tests that all codes are unique."""

    def test_codes_unique(self):
        """All failure codes must be unique."""
        from src.core.failures import validate_codes_unique, get_all_codes
        
        assert validate_codes_unique() is True
        
        codes = get_all_codes()
        code_values = [fc.code for fc in codes.values()]
        assert len(code_values) == len(set(code_values))


class TestNoFreeTextFailures:
    """Tests that failures use codes, not free text."""

    def test_no_free_text_failures(self):
        """All failures must use canonical codes."""
        from src.core.failures import (
            format_failure_message,
            format_abort_message,
            REUSE_001, GRND_001
        )
        
        # Check format includes code
        message = format_failure_message(REUSE_001)
        assert "DTL-REUSE-001" in message
        assert "Code:" in message
        
        abort_msg = format_abort_message(GRND_001)
        assert "DTL-GRND-001" in abort_msg
        assert "Code:" in abort_msg


class TestAllAbortPathsHaveCodes:
    """Tests that all abort paths emit codes."""

    def test_all_abort_paths_have_codes(self):
        """Every abort path should have an associated code."""
        from src.core.failures import get_all_codes
        
        codes = get_all_codes()
        
        # Verify we have codes for all major categories
        categories = {fc.category for fc in codes.values()}
        required_categories = {"REUSE", "GROUNDING", "AGENT", "SECURITY", "SYSTEM"}
        
        assert required_categories.issubset(categories)
        
        # Verify minimum codes per category
        category_counts = {}
        for fc in codes.values():
            category_counts[fc.category] = category_counts.get(fc.category, 0) + 1
        
        for cat in required_categories:
            assert category_counts.get(cat, 0) >= 3, f"Category {cat} needs more codes"


class TestDTLFailureException:
    """Tests for DTLFailure exception class."""

    def test_dtl_failure_has_code(self):
        """DTLFailure exception must include code."""
        from src.core.failures import DTLFailure, SEC_001
        
        exc = DTLFailure(SEC_001, "Additional details here")
        
        assert exc.code == "DTL-SEC-001"
        assert exc.category == "SECURITY"
        assert "DTL-SEC-001" in str(exc)
