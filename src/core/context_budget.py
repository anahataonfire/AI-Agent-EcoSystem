"""
Context Budget Optimization (DTL-SKILL-CONTEXT v1).

Context budget management to prevent token overruns.
Highest priority wins, stable ordering, never truncate mid-slice.
"""

from dataclasses import dataclass
from typing import List


class ContextBudgetExceededError(Exception):
    """Raised when context exceeds max_tokens silently (tripwire)."""
    pass


@dataclass
class ContextSlice:
    """A slice of context with priority and token estimate."""
    source: str
    priority: int  # Higher = more important
    token_estimate: int
    content: str


def select_context_slices(
    slices: List[ContextSlice],
    max_tokens: int,
) -> List[ContextSlice]:
    """
    Select context slices within budget.
    
    Rules:
    - Highest priority wins
    - Stable ordering (preserves relative order among same priority)
    - Never truncate mid-slice
    
    Args:
        slices: List of context slices
        max_tokens: Maximum token budget
        
    Returns:
        Selected slices within budget
    """
    if not slices:
        return []
    
    # Sort by priority descending, then by original index for stability
    indexed_slices = list(enumerate(slices))
    sorted_slices = sorted(
        indexed_slices,
        key=lambda x: (-x[1].priority, x[0])
    )
    
    selected = []
    total_tokens = 0
    
    for original_idx, slice in sorted_slices:
        if total_tokens + slice.token_estimate <= max_tokens:
            selected.append((original_idx, slice))
            total_tokens += slice.token_estimate
    
    # Restore original ordering among selected slices
    selected.sort(key=lambda x: x[0])
    
    return [s[1] for s in selected]


def validate_context_budget(
    slices: List[ContextSlice],
    max_tokens: int,
) -> None:
    """
    Validate that total context is within budget (tripwire).
    
    Raises:
        ContextBudgetExceededError: If total exceeds max
    """
    total = sum(s.token_estimate for s in slices)
    
    if total > max_tokens:
        raise ContextBudgetExceededError(
            f"Context budget exceeded: {total} > {max_tokens} tokens"
        )


def estimate_tokens(content: str) -> int:
    """
    Estimate token count for content.
    
    Uses simple character-based heuristic (4 chars ≈ 1 token).
    """
    return max(1, len(content) // 4)


def build_context_slice(
    source: str,
    content: str,
    priority: int = 5,
) -> ContextSlice:
    """Build a context slice with automatic token estimation."""
    return ContextSlice(
        source=source,
        priority=priority,
        token_estimate=estimate_tokens(content),
        content=content,
    )


def get_total_tokens(slices: List[ContextSlice]) -> int:
    """Get total token estimate for slices."""
    return sum(s.token_estimate for s in slices)
