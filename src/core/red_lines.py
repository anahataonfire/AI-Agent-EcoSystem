"""
Red-Line Policy Enforcement (Prompt AM).

Defines absolute prohibitions that hard-abort the system.
Some things must NEVER happen.
"""

from typing import Callable, Dict, List, Optional, Tuple

from src.core.failures import SYS_003, format_security_breach
from src.core.run_ledger import log_event, EVENT_RED_LINE_VIOLATION


class RedLineViolationError(Exception):
    """Raised when a red-line is violated."""
    pass


# ============================================================================
# RED-LINE DEFINITIONS
# ============================================================================

RED_LINE_IDENTITY_MUTATION = "identity_mutation_outside_reporter"
RED_LINE_UNGROUNDED_OUTPUT = "ungrounded_factual_output"
RED_LINE_CROSS_AGENT_INSTRUCTION = "cross_agent_instruction_execution"
RED_LINE_UNVALIDATED_REUSE = "evidence_reuse_without_validation"
RED_LINE_LEDGER_TAMPERING = "ledger_tampering_attempt"

ALL_RED_LINES = {
    RED_LINE_IDENTITY_MUTATION,
    RED_LINE_UNGROUNDED_OUTPUT,
    RED_LINE_CROSS_AGENT_INSTRUCTION,
    RED_LINE_UNVALIDATED_REUSE,
    RED_LINE_LEDGER_TAMPERING,
}

_RED_LINE_DESCRIPTIONS = {
    RED_LINE_IDENTITY_MUTATION: "Identity mutation outside reporter node",
    RED_LINE_UNGROUNDED_OUTPUT: "Ungrounded factual output in report",
    RED_LINE_CROSS_AGENT_INSTRUCTION: "Cross-agent instruction execution",
    RED_LINE_UNVALIDATED_REUSE: "Evidence reuse without validation",
    RED_LINE_LEDGER_TAMPERING: "Ledger tampering attempt detected",
}


def trigger_red_line(
    red_line: str,
    actor: str,
    details: Optional[str] = None
) -> None:
    """
    Trigger a red-line violation and halt the system.
    
    Args:
        red_line: The red-line that was violated
        actor: Who caused the violation
        details: Additional details
        
    Raises:
        RedLineViolationError: Always raised to halt execution
    """
    if red_line not in ALL_RED_LINES:
        raise ValueError(f"Unknown red-line: {red_line}")
    
    # Log to run ledger before halting
    log_event(
        event=EVENT_RED_LINE_VIOLATION,
        actor=actor,
        payload={
            "red_line": red_line,
            "description": _RED_LINE_DESCRIPTIONS[red_line],
            "details": details,
        }
    )
    
    message = format_security_breach(SYS_003, _RED_LINE_DESCRIPTIONS[red_line])
    raise RedLineViolationError(message)


def check_identity_mutation_allowed(agent_name: str) -> Tuple[bool, str]:
    """
    Check if an agent is allowed to mutate identity.
    
    Returns:
        Tuple of (is_allowed, reason)
    """
    if agent_name == "reporter":
        return (True, "Reporter is authorized for identity writes")
    return (False, f"Agent {agent_name} is not authorized for identity writes")


def check_grounding_required(content_type: str) -> bool:
    """Check if content type requires grounding."""
    factual_types = {"report", "summary", "analysis", "findings"}
    return content_type.lower() in factual_types


def validate_no_red_line_violation(
    action: str,
    agent_name: str,
    context: Optional[Dict] = None
) -> None:
    """
    Validate an action doesn't violate any red-lines.
    
    Args:
        action: The action being attempted
        agent_name: The agent attempting the action
        context: Additional context
        
    Raises:
        RedLineViolationError: If a red-line is violated
    """
    context = context or {}
    
    # Check identity mutation
    if action == "write_identity" and agent_name != "reporter":
        trigger_red_line(
            RED_LINE_IDENTITY_MUTATION,
            f"agent:{agent_name}",
            f"Attempted identity write by {agent_name}"
        )
    
    # Check unvalidated reuse
    if action == "reuse_evidence" and not context.get("validated", False):
        trigger_red_line(
            RED_LINE_UNVALIDATED_REUSE,
            f"agent:{agent_name}",
            "Evidence reuse attempted without validation"
        )


def get_red_line_message(red_line: str) -> str:
    """Get the standard message for a red-line violation."""
    description = _RED_LINE_DESCRIPTIONS.get(red_line, "Unknown violation")
    return f"# SECURITY BREACH\nSystem halted due to Red-Line violation: {description}"


def list_all_red_lines() -> List[Dict[str, str]]:
    """List all defined red-lines."""
    return [
        {"id": rl, "description": _RED_LINE_DESCRIPTIONS[rl]}
        for rl in ALL_RED_LINES
    ]
