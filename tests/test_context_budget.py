"""
Context Budget Tests (DTL-SKILL-CONTEXT v1).
"""

import pytest


class TestPrioritySelection:
    """Tests for priority-based selection."""

    def test_highest_priority_wins(self):
        """Highest priority slices should be selected first."""
        from src.core.context_budget import ContextSlice, select_context_slices
        
        slices = [
            ContextSlice("low", priority=1, token_estimate=100, content="low"),
            ContextSlice("high", priority=10, token_estimate=100, content="high"),
            ContextSlice("med", priority=5, token_estimate=100, content="med"),
        ]
        
        selected = select_context_slices(slices, max_tokens=150)
        
        # Should select highest priority only
        assert len(selected) == 1
        assert selected[0].source == "high"


class TestStableOrdering:
    """Tests for stable ordering."""

    def test_stable_ordering(self):
        """Same priority should preserve original order."""
        from src.core.context_budget import ContextSlice, select_context_slices
        
        slices = [
            ContextSlice("a", priority=5, token_estimate=50, content="first"),
            ContextSlice("b", priority=5, token_estimate=50, content="second"),
            ContextSlice("c", priority=5, token_estimate=50, content="third"),
        ]
        
        selected = select_context_slices(slices, max_tokens=120)
        
        # Should maintain original order
        sources = [s.source for s in selected]
        assert sources == ["a", "b"]


class TestNoMidSliceTruncation:
    """Tests that slices are never truncated."""

    def test_no_truncation(self):
        """Slices should never be truncated mid-content."""
        from src.core.context_budget import ContextSlice, select_context_slices
        
        slices = [
            ContextSlice("big", priority=10, token_estimate=150, content="x" * 600),
        ]
        
        # Budget can't fit the slice
        selected = select_context_slices(slices, max_tokens=100)
        
        # Should return empty, not truncated
        assert len(selected) == 0


class TestBudgetTripwire:
    """Tests for budget exceeded tripwire."""

    def test_tripwire_raises(self):
        """Exceeding budget should raise error."""
        from src.core.context_budget import (
            ContextSlice, validate_context_budget, ContextBudgetExceededError
        )
        
        slices = [
            ContextSlice("a", priority=5, token_estimate=100, content="a"),
            ContextSlice("b", priority=5, token_estimate=100, content="b"),
        ]
        
        with pytest.raises(ContextBudgetExceededError):
            validate_context_budget(slices, max_tokens=150)
