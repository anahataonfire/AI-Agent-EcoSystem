"""
Cross-Agent Message Firewall (Prompt AC).

Prevents agents from passing executable instructions to other agents.
"""

import re
from typing import List, Tuple


class MessageInjectionError(Exception):
    """Raised when inter-agent instruction injection is detected."""
    pass


# ============================================================================
# FORBIDDEN PATTERNS
# ============================================================================

# Instruction patterns - agents trying to control other agents
INSTRUCTION_PATTERNS = [
    re.compile(r"\byou\s+should\b", re.IGNORECASE),
    re.compile(r"\bnext\s+agent\s+must\b", re.IGNORECASE),
    re.compile(r"\bignore\s+previous\b", re.IGNORECASE),
    re.compile(r"\bthe\s+(?:next|following)\s+(?:agent|node)\s+(?:should|must|will)\b", re.IGNORECASE),
    re.compile(r"\bexecute\s+(?:the\s+)?following\b", re.IGNORECASE),
    re.compile(r"\bperform\s+(?:the\s+)?action\b", re.IGNORECASE),
]

# Tool names that should not appear in inter-agent messages
FORBIDDEN_TOOL_NAMES = [
    "DataFetchRSS",
    "DataFetchAPI",
    "BrowserSearch",
    "CompleteTask",
    "StructuredSummary",
]

# JSON schema patterns
SCHEMA_PATTERNS = [
    re.compile(r'"tool_name"\s*:', re.IGNORECASE),
    re.compile(r'"action"\s*:\s*"', re.IGNORECASE),
    re.compile(r'"params"\s*:\s*\{', re.IGNORECASE),
    re.compile(r'"execute"\s*:', re.IGNORECASE),
]


def check_for_instructions(message: str) -> Tuple[bool, str]:
    """
    Check if a message contains instruction patterns.
    
    Returns:
        Tuple of (has_violation, violation_reason)
    """
    for pattern in INSTRUCTION_PATTERNS:
        if pattern.search(message):
            return (True, f"Instruction pattern detected: {pattern.pattern}")
    return (False, "")


def check_for_tool_leaks(message: str) -> Tuple[bool, str]:
    """
    Check if a message contains forbidden tool names.
    
    Returns:
        Tuple of (has_violation, violation_reason)
    """
    for tool_name in FORBIDDEN_TOOL_NAMES:
        if tool_name in message:
            return (True, f"Tool name leak detected: {tool_name}")
    return (False, "")


def check_for_schema_injection(message: str) -> Tuple[bool, str]:
    """
    Check if a message contains JSON schema patterns.
    
    Returns:
        Tuple of (has_violation, violation_reason)
    """
    for pattern in SCHEMA_PATTERNS:
        if pattern.search(message):
            return (True, f"Schema injection detected: {pattern.pattern}")
    return (False, "")


def validate_inter_agent_message(message: str, source_agent: str, target_agent: str) -> None:
    """
    Validate that a message between agents is safe.
    
    Args:
        message: The message content
        source_agent: Agent sending the message
        target_agent: Agent receiving the message
        
    Raises:
        MessageInjectionError: If message contains forbidden content
    """
    # Check for instruction patterns
    has_instruction, reason = check_for_instructions(message)
    if has_instruction:
        raise MessageInjectionError(
            f"Inter-agent instruction injection detected from {source_agent} to {target_agent}: {reason}"
        )
    
    # Check for tool name leaks
    has_tool_leak, reason = check_for_tool_leaks(message)
    if has_tool_leak:
        raise MessageInjectionError(
            f"Inter-agent instruction injection detected from {source_agent} to {target_agent}: {reason}"
        )
    
    # Check for schema injection
    has_schema, reason = check_for_schema_injection(message)
    if has_schema:
        raise MessageInjectionError(
            f"Inter-agent instruction injection detected from {source_agent} to {target_agent}: {reason}"
        )


def is_observation_only(message: str) -> bool:
    """
    Check if a message contains only observation content (no instructions).
    
    Allowed content:
    - Observations
    - Results
    - Evidence IDs
    - Status messages
    
    Returns:
        True if message is observation-only
    """
    # Check all violation types
    has_instruction, _ = check_for_instructions(message)
    has_tool_leak, _ = check_for_tool_leaks(message)
    has_schema, _ = check_for_schema_injection(message)
    
    return not (has_instruction or has_tool_leak or has_schema)


def sanitize_inter_agent_message(message: str) -> str:
    """
    Remove forbidden content from a message (for logging/audit).
    
    Note: This is for audit purposes only. In production,
    messages with forbidden content should be rejected, not sanitized.
    """
    result = message
    
    # Remove tool names
    for tool_name in FORBIDDEN_TOOL_NAMES:
        result = result.replace(tool_name, "[TOOL_REDACTED]")
    
    # Remove instruction patterns
    for pattern in INSTRUCTION_PATTERNS:
        result = pattern.sub("[INSTRUCTION_REDACTED]", result)
    
    return result
