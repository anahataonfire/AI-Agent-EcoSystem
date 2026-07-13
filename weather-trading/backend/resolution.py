"""Honest market resolution loop with injectable/offline outcome providers."""
from typing import Callable, Dict, List, Optional

from database import load_positions, resolve_position


OutcomeProvider = Callable[[Dict], Optional[str]]


def resolve_pending(outcome_provider: OutcomeProvider, source: str = "resolution_provider") -> List[Dict]:
    """Resolve only positions whose confirmed fills are awaiting resolution.

    Unknown outcomes remain RESOLUTION_PENDING and retain NULL P&L.
    """
    resolved = []
    for position in load_positions("RESOLUTION_PENDING"):
        outcome = outcome_provider(position)
        if outcome is None:
            continue
        normalized = outcome.upper()
        if normalized not in {"WON", "LOST"}:
            raise ValueError(f"Unsupported binary outcome: {outcome}")
        resolved.append(resolve_position(position["id"], normalized, source=source))
    return resolved
