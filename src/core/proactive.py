"""
Proactive Decision Triggering (DTL-SKILL-PROACTIVE v1).

Allows agents to act without explicit user prompts under constraints.
Must log to run ledger before action. Never writes identity.
"""

from dataclasses import dataclass
from typing import Optional

from src.core.run_ledger import log_event
from src.core.kill_switches import get_all_switch_states


class ProactiveActionBlockedError(Exception):
    """Raised when proactive action is blocked."""
    pass


@dataclass(frozen=True)
class ProactiveDecision:
    """A proactive action decision."""
    action_type: str
    confidence: float
    reason: str
    blocked: bool
    block_reason: Optional[str] = None


# Minimum confidence for proactive action
MIN_PROACTIVE_CONFIDENCE = 0.85

# Proactive event type for ledger
EVENT_PROACTIVE_ACTION = "PROACTIVE_ACTION"


def check_proactive_allowed() -> tuple:
    """
    Check if proactive actions are allowed.
    
    Returns:
        Tuple of (is_allowed, block_reason)
    """
    switch_states = get_all_switch_states()
    
    # Any active kill switch blocks proactive actions
    for switch_name, is_disabled in switch_states.items():
        if is_disabled:
            return (False, f"Kill switch active: {switch_name}")
    
    return (True, None)


def evaluate_proactive_action(
    action_type: str,
    confidence: float,
    reason: str,
) -> ProactiveDecision:
    """
    Evaluate whether a proactive action should proceed.
    
    Requirements:
    - Confidence > 0.85
    - No kill switches active
    """
    # Check confidence
    if confidence < MIN_PROACTIVE_CONFIDENCE:
        return ProactiveDecision(
            action_type=action_type,
            confidence=confidence,
            reason=reason,
            blocked=True,
            block_reason=f"Confidence {confidence:.2f} below threshold {MIN_PROACTIVE_CONFIDENCE}",
        )
    
    # Check kill switches
    allowed, block_reason = check_proactive_allowed()
    if not allowed:
        return ProactiveDecision(
            action_type=action_type,
            confidence=confidence,
            reason=reason,
            blocked=True,
            block_reason=block_reason,
        )
    
    return ProactiveDecision(
        action_type=action_type,
        confidence=confidence,
        reason=reason,
        blocked=False,
    )


def execute_proactive_action(
    decision: ProactiveDecision,
    actor: str,
    payload: Optional[dict] = None,
) -> None:
    """
    Execute a proactive action.
    
    Logs to run ledger BEFORE taking action.
    
    Raises:
        ProactiveActionBlockedError: If action is blocked
    """
    if decision.blocked:
        raise ProactiveActionBlockedError(
            f"Proactive action blocked: {decision.block_reason}"
        )
    
    # Log to ledger BEFORE action
    log_event(
        event=EVENT_PROACTIVE_ACTION,
        actor=actor,
        payload={
            "action_type": decision.action_type,
            "confidence": decision.confidence,
            "reason": decision.reason,
            **(payload or {}),
        }
    )


def suppress_false_positive(
    action_type: str,
    context: dict,
) -> bool:
    """
    Check if this is likely a false positive.
    
    Returns:
        True if action should be suppressed
    """
    # Suppress if action was recently taken for same context
    if context.get("recently_executed"):
        return True
    
    # Suppress if context uncertainty is high
    if context.get("context_uncertainty", 0) > 0.3:
        return True
    
    return False
