"""
Kill-Switch Registry for Operator-Controlled Runtime Shutdown.

Provides central control over dangerous execution paths.
Switches are read once per run and cannot be modified mid-execution.

Usage:
    from src.core.kill_switches import check_kill_switch, KillSwitchError
    
    halted, reason = check_kill_switch("TRUE_REUSE")
    if halted:
        raise KillSwitchError(reason)
"""

from typing import Tuple, Optional


class KillSwitchError(Exception):
    """Raised when a kill switch is activated."""
    pass


# ============================================================================
# KILL SWITCH REGISTRY
# ============================================================================
# These switches provide operator-level control over execution paths.
# Set to True to disable the corresponding feature.

DISABLE_TRUE_REUSE = False
DISABLE_EVIDENCE_REUSE = False
DISABLE_GROUNDING = False
DISABLE_LEARNING = False  # Strategic Autonomy learning

# ============================================================================
# Switch Metadata
# ============================================================================

_SWITCH_MESSAGES = {
    "TRUE_REUSE": "True Reuse is currently disabled by operator.",
    "EVIDENCE_REUSE": "Evidence Reuse is currently disabled by operator.",
    "GROUNDING": "Grounding validation is currently disabled by operator.",
    "LEARNING": "Strategic Autonomy learning is currently disabled by operator.",
}

_SWITCH_REGISTRY = {
    "TRUE_REUSE": lambda: DISABLE_TRUE_REUSE,
    "EVIDENCE_REUSE": lambda: DISABLE_EVIDENCE_REUSE,
    "GROUNDING": lambda: DISABLE_GROUNDING,
    "LEARNING": lambda: DISABLE_LEARNING,
}


def check_kill_switch(switch_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a kill switch is activated.
    
    Args:
        switch_name: One of "TRUE_REUSE", "EVIDENCE_REUSE", "GROUNDING"
    
    Returns:
        Tuple of (is_halted, halt_message).
        If is_halted is True, the path should abort with the provided message.
        If is_halted is False, halt_message will be None.
    
    Example:
        halted, reason = check_kill_switch("TRUE_REUSE")
        if halted:
            return {"messages": [AIMessage(content=f"# Execution Halted\\nReason: {reason}")]}
    """
    if switch_name not in _SWITCH_REGISTRY:
        raise ValueError(f"Unknown kill switch: {switch_name}. Valid: {list(_SWITCH_REGISTRY.keys())}")
    
    is_disabled = _SWITCH_REGISTRY[switch_name]()
    
    if is_disabled:
        message = _SWITCH_MESSAGES.get(switch_name, f"{switch_name} is disabled by operator.")
        return (True, message)
    
    return (False, None)


def get_all_switch_states() -> dict:
    """
    Get the current state of all kill switches.
    
    Returns:
        Dict mapping switch names to their current enabled/disabled state.
    """
    return {
        "TRUE_REUSE": DISABLE_TRUE_REUSE,
        "EVIDENCE_REUSE": DISABLE_EVIDENCE_REUSE,
        "GROUNDING": DISABLE_GROUNDING,
    }


def build_halt_message(reason: str) -> str:
    """
    Build a standardized halt message for kill switch activation.
    
    Args:
        reason: The reason for halting (from check_kill_switch)
    
    Returns:
        Formatted markdown message for the final report.
    """
    return f"# Execution Halted\nReason: {reason}"


# ============================================================================
# AGENT COMPROMISE QUARANTINE (Prompt AF)
# ============================================================================

# Quarantined agents - set by trigger_agent_compromised
_QUARANTINED_AGENTS: set = set()

# Reasons for quarantine
_QUARANTINE_REASONS: dict = {}


class AgentCompromisedError(Exception):
    """Raised when an agent has been quarantined due to a security violation."""
    pass


def trigger_agent_compromised(agent_name: str, reason: str) -> None:
    """
    Quarantine an agent due to a security violation.
    
    This triggers an immediate pipeline abort.
    
    Args:
        agent_name: Name of the compromised agent
        reason: The reason for quarantine
    """
    _QUARANTINED_AGENTS.add(agent_name)
    _QUARANTINE_REASONS[agent_name] = reason


def is_agent_quarantined(agent_name: str) -> bool:
    """Check if an agent is quarantined."""
    return agent_name in _QUARANTINED_AGENTS


def get_quarantine_reason(agent_name: str) -> Optional[str]:
    """Get the reason an agent was quarantined."""
    return _QUARANTINE_REASONS.get(agent_name)


def check_agent_allowed(agent_name: str) -> Tuple[bool, Optional[str]]:
    """
    Check if an agent is allowed to execute.
    
    Returns:
        Tuple of (is_allowed, block_reason)
    """
    if is_agent_quarantined(agent_name):
        reason = get_quarantine_reason(agent_name) or "Unknown violation"
        return (False, f"Agent {agent_name} is quarantined: {reason}")
    return (True, None)


def get_all_quarantined_agents() -> dict:
    """Get all quarantined agents and their reasons."""
    return {agent: _QUARANTINE_REASONS.get(agent, "Unknown") for agent in _QUARANTINED_AGENTS}


def reset_quarantine() -> None:
    """Reset the quarantine state (for testing)."""
    _QUARANTINED_AGENTS.clear()
    _QUARANTINE_REASONS.clear()


def build_quarantine_message(agent_name: str, reason: str) -> str:
    """Build a standardized message for agent quarantine."""
    return f"# Execution Aborted\nReason: Agent {agent_name} compromised - {reason}"

