"""
Failure Taxonomy & Codes (Prompt AK).

Canonical failure codes replacing free-text failures.
Every abort emits a code. Codes are immutable once assigned.
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass(frozen=True)
class FailureCode:
    """Immutable failure code definition."""
    code: str
    category: str
    description: str


# ============================================================================
# FAILURE CODE REGISTRY
# ============================================================================

# Reuse failures (DTL-REUSE-XXX)
REUSE_001 = FailureCode("DTL-REUSE-001", "REUSE", "True Reuse disabled by operator")
REUSE_002 = FailureCode("DTL-REUSE-002", "REUSE", "Evidence reuse disabled by operator")
REUSE_003 = FailureCode("DTL-REUSE-003", "REUSE", "Reuse denied - evidence ordering mismatch")
REUSE_004 = FailureCode("DTL-REUSE-004", "REUSE", "Evidence staleness exceeded threshold")
REUSE_005 = FailureCode("DTL-REUSE-005", "REUSE", "Cross-run evidence contamination detected")

# Grounding failures (DTL-GRND-XXX)
GRND_001 = FailureCode("DTL-GRND-001", "GROUNDING", "Factual claim lacks citation")
GRND_002 = FailureCode("DTL-GRND-002", "GROUNDING", "Evidence ID does not exist")
GRND_003 = FailureCode("DTL-GRND-003", "GROUNDING", "Grounding validation disabled by operator")
GRND_004 = FailureCode("DTL-GRND-004", "GROUNDING", "Self-referential citation detected")
GRND_005 = FailureCode("DTL-GRND-005", "GROUNDING", "Invalid evidence type")

# Agent failures (DTL-AGENT-XXX)
AGENT_001 = FailureCode("DTL-AGENT-001", "AGENT", "Agent capability violation")
AGENT_002 = FailureCode("DTL-AGENT-002", "AGENT", "Inter-agent instruction injection")
AGENT_003 = FailureCode("DTL-AGENT-003", "AGENT", "Agent turn limit exceeded")
AGENT_004 = FailureCode("DTL-AGENT-004", "AGENT", "Agent self-invocation attempt")
AGENT_005 = FailureCode("DTL-AGENT-005", "AGENT", "Agent compromised - quarantined")

# Security failures (DTL-SEC-XXX)
SEC_001 = FailureCode("DTL-SEC-001", "SECURITY", "Malicious payload detected")
SEC_002 = FailureCode("DTL-SEC-002", "SECURITY", "Footer spoofing attempt")
SEC_003 = FailureCode("DTL-SEC-003", "SECURITY", "Identity injection attempt")
SEC_004 = FailureCode("DTL-SEC-004", "SECURITY", "Citation laundering detected")
SEC_005 = FailureCode("DTL-SEC-005", "SECURITY", "Replay attack blocked")

# System failures (DTL-SYS-XXX)
SYS_001 = FailureCode("DTL-SYS-001", "SYSTEM", "Ledger write failure")
SYS_002 = FailureCode("DTL-SYS-002", "SYSTEM", "Ledger tampering detected")
SYS_003 = FailureCode("DTL-SYS-003", "SYSTEM", "Red-line violation")
SYS_004 = FailureCode("DTL-SYS-004", "SYSTEM", "Determinism violation detected")
SYS_005 = FailureCode("DTL-SYS-005", "SYSTEM", "Kill switch activated")

# All codes registry
_CODE_REGISTRY: Dict[str, FailureCode] = {
    fc.code: fc for fc in [
        REUSE_001, REUSE_002, REUSE_003, REUSE_004, REUSE_005,
        GRND_001, GRND_002, GRND_003, GRND_004, GRND_005,
        AGENT_001, AGENT_002, AGENT_003, AGENT_004, AGENT_005,
        SEC_001, SEC_002, SEC_003, SEC_004, SEC_005,
        SYS_001, SYS_002, SYS_003, SYS_004, SYS_005,
    ]
}


def get_failure_code(code: str) -> Optional[FailureCode]:
    """Get a failure code by its code string."""
    return _CODE_REGISTRY.get(code)


def get_all_codes() -> Dict[str, FailureCode]:
    """Get all registered failure codes."""
    return _CODE_REGISTRY.copy()


def validate_codes_unique() -> bool:
    """Verify all codes are unique."""
    codes = list(_CODE_REGISTRY.keys())
    return len(codes) == len(set(codes))


def format_failure_message(failure_code: FailureCode, details: Optional[str] = None) -> str:
    """
    Format a failure message with code.
    
    Returns:
        Formatted markdown failure message
    """
    message = f"# Execution Failed\nCode: {failure_code.code}\nReason: {failure_code.description}"
    if details:
        message += f"\nDetails: {details}"
    return message


def format_abort_message(failure_code: FailureCode, details: Optional[str] = None) -> str:
    """Format an abort message with code."""
    message = f"# Execution Aborted\nCode: {failure_code.code}\nReason: {failure_code.description}"
    if details:
        message += f"\nDetails: {details}"
    return message


def format_security_breach(failure_code: FailureCode, details: Optional[str] = None) -> str:
    """Format a security breach message with code."""
    message = f"# SECURITY BREACH\nCode: {failure_code.code}\nSystem halted due to: {failure_code.description}"
    if details:
        message += f"\nDetails: {details}"
    return message


class DTLFailure(Exception):
    """Exception with canonical failure code."""
    
    def __init__(self, failure_code: FailureCode, details: Optional[str] = None):
        self.failure_code = failure_code
        self.details = details
        super().__init__(format_failure_message(failure_code, details))
    
    @property
    def code(self) -> str:
        return self.failure_code.code
    
    @property
    def category(self) -> str:
        return self.failure_code.category
