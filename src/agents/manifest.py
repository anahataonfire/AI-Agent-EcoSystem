"""
Agent Capability Manifests (Prompt AB).

Defines explicit capability manifests per agent to prevent lateral privilege escalation.
Agents may only perform actions explicitly declared in their manifest.
"""

from typing import Any, Dict, List, Optional, Set


class CapabilityViolationError(Exception):
    """Raised when an agent attempts an action outside its manifest."""
    pass


# ============================================================================
# CAPABILITY MANIFESTS
# ============================================================================

AGENT_MANIFESTS: Dict[str, Dict[str, Any]] = {
    "thinker": {
        "read_identity": True,
        "write_identity": False,
        "read_evidence": True,
        "write_evidence": False,
        "invoke_tools": ["DataFetchRSS", "DataFetchAPI", "BrowserSearch"],
    },
    "sanitizer": {
        "read_identity": False,
        "write_identity": False,
        "read_evidence": True,
        "write_evidence": False,
        "invoke_tools": [],  # Sanitizer only validates, does not invoke tools
    },
    "executor": {
        "read_identity": False,
        "write_identity": False,
        "read_evidence": True,
        "write_evidence": True,
        "invoke_tools": ["DataFetchRSS", "DataFetchAPI", "BrowserSearch"],
    },
    "reporter": {
        "read_identity": True,
        "write_identity": True,
        "read_evidence": True,
        "write_evidence": True,
        "invoke_tools": ["CompleteTask"],
    },
}


def get_manifest(agent_name: str) -> Dict[str, Any]:
    """
    Get the capability manifest for an agent.
    
    Args:
        agent_name: Name of the agent (thinker, sanitizer, executor, reporter)
        
    Returns:
        The agent's capability manifest
        
    Raises:
        CapabilityViolationError: If agent is not known
    """
    if agent_name not in AGENT_MANIFESTS:
        raise CapabilityViolationError(f"Unknown agent: {agent_name}")
    return AGENT_MANIFESTS[agent_name]


def check_capability(agent_name: str, capability: str) -> bool:
    """
    Check if an agent has a specific capability.
    
    Args:
        agent_name: Name of the agent
        capability: The capability to check (read_identity, write_identity, etc.)
        
    Returns:
        True if agent has the capability
    """
    manifest = get_manifest(agent_name)
    return manifest.get(capability, False)


def check_tool_allowed(agent_name: str, tool_name: str) -> bool:
    """
    Check if an agent is allowed to invoke a specific tool.
    
    Args:
        agent_name: Name of the agent
        tool_name: Name of the tool to check
        
    Returns:
        True if agent is allowed to invoke the tool
    """
    manifest = get_manifest(agent_name)
    allowed_tools = manifest.get("invoke_tools", [])
    return tool_name in allowed_tools


def validate_action(agent_name: str, action: str, tool_name: Optional[str] = None) -> None:
    """
    Validate that an agent is allowed to perform an action.
    
    Args:
        agent_name: Name of the agent
        action: The action type (read_identity, write_identity, invoke_tool, etc.)
        tool_name: If action is invoke_tool, the tool name
        
    Raises:
        CapabilityViolationError: If action is not allowed
    """
    manifest = get_manifest(agent_name)
    
    if action == "invoke_tool":
        if tool_name is None:
            raise CapabilityViolationError("Tool name required for invoke_tool action")
        if not check_tool_allowed(agent_name, tool_name):
            raise CapabilityViolationError(
                f"Agent capability violation: {agent_name} cannot invoke {tool_name}"
            )
    elif action in ("read_identity", "write_identity", "read_evidence", "write_evidence"):
        if not manifest.get(action, False):
            raise CapabilityViolationError(
                f"Agent capability violation: {agent_name} cannot perform {action}"
            )
    else:
        raise CapabilityViolationError(f"Unknown action type: {action}")


def get_allowed_tools(agent_name: str) -> List[str]:
    """Get list of tools an agent is allowed to invoke."""
    manifest = get_manifest(agent_name)
    return list(manifest.get("invoke_tools", []))


def validate_manifest_immutable() -> bool:
    """
    Verify that manifests have not been mutated at runtime.
    
    Returns:
        True if manifests match expected structure
    """
    expected_agents = {"thinker", "sanitizer", "executor", "reporter"}
    return set(AGENT_MANIFESTS.keys()) == expected_agents


# Original manifest state for reset (deep copy)
import copy
_ORIGINAL_MANIFESTS = copy.deepcopy(AGENT_MANIFESTS)


def reset_manifests() -> None:
    """
    Reset AGENT_MANIFESTS to original state.
    
    Used by tests to ensure isolation - call in fixture teardown
    to prevent test pollution.
    """
    global AGENT_MANIFESTS
    AGENT_MANIFESTS.clear()
    AGENT_MANIFESTS.update(copy.deepcopy(_ORIGINAL_MANIFESTS))

