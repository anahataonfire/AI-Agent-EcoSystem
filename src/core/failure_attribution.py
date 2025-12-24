"""
Failure Attribution (DTL-SKILL-FAILATTR v1).

Determine why something failed, not just that it failed.
Deterministic, never reads chat history, never infers intent.
"""

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


class LowConfidenceAttributionError(Exception):
    """Raised when attribution confidence is below threshold (DTL-FAILATTR-002)."""
    pass


# ============================================================================
# FAILURE ATTRIBUTION
# ============================================================================

@dataclass(frozen=True)
class FailureAttribution:
    """Immutable failure attribution record."""
    failure_class: str
    originating_agent: str
    tool_name: Optional[str]
    stage: Literal["think", "sanitize", "execute", "report"]
    root_cause: Literal["tool", "data", "prompt", "policy", "unknown"]
    retryable: bool
    confidence: float  # 0.0–1.0


# Minimum confidence threshold
MIN_ATTRIBUTION_CONFIDENCE = 0.4


# ============================================================================
# ATTRIBUTION RULES (Deterministic)
# ============================================================================

# Stage-to-agent mapping
STAGE_AGENTS: Dict[str, str] = {
    "think": "thinker",
    "sanitize": "sanitizer",
    "execute": "executor",
    "report": "reporter",
}

# Error patterns → (root_cause, confidence, retryable)
ATTRIBUTION_PATTERNS: Dict[str, tuple] = {
    # Tool failures
    "connection timeout": ("tool", 0.9, True),
    "network error": ("tool", 0.9, True),
    "rate limit": ("tool", 0.85, True),
    "api error": ("tool", 0.8, True),
    "tool failed": ("tool", 0.85, True),
    "execution failed": ("tool", 0.75, True),
    
    # Data failures
    "invalid format": ("data", 0.9, False),
    "malformed": ("data", 0.9, False),
    "missing required": ("data", 0.85, False),
    "validation failed": ("data", 0.85, False),
    "empty payload": ("data", 0.8, False),
    "parse error": ("data", 0.8, False),
    
    # Prompt failures
    "grounding failure": ("prompt", 0.9, False),
    "ungrounded": ("prompt", 0.85, False),
    "citation missing": ("prompt", 0.85, False),
    "fabricated": ("prompt", 0.8, False),
    
    # Policy failures
    "kill switch": ("policy", 1.0, False),
    "red-line": ("policy", 1.0, False),
    "capability violation": ("policy", 0.95, False),
    "quarantined": ("policy", 0.95, False),
    "injection detected": ("policy", 0.9, False),
}

# Failure code → root cause mapping
CODE_ROOT_CAUSE: Dict[str, str] = {
    "DTL-REUSE": "policy",
    "DTL-GRND": "prompt",
    "DTL-AGENT": "policy",
    "DTL-SEC": "policy",
    "DTL-SYS": "tool",
}


def determine_stage(
    agent_name: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> Literal["think", "sanitize", "execute", "report"]:
    """
    Determine execution stage from available context.
    """
    if agent_name:
        for stage, agent in STAGE_AGENTS.items():
            if agent == agent_name:
                return stage  # type: ignore
    
    # Infer from tool
    if tool_name:
        if tool_name in ("DataFetchRSS", "DataFetchAPI", "BrowserSearch"):
            return "execute"
        if tool_name == "CompleteTask":
            return "report"
    
    return "unknown"  # type: ignore


def attribute_failure(
    error_message: str,
    error_code: Optional[str] = None,
    agent_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    failure_class: Optional[str] = None,
) -> FailureAttribution:
    """
    Attribute a failure to its root cause.
    
    This is deterministic based on error patterns.
    Never reads chat history. Never infers intent.
    
    Raises:
        LowConfidenceAttributionError: If confidence < 0.4 (DTL-FAILATTR-002)
    """
    msg_lower = error_message.lower()
    
    # Default values
    root_cause: Literal["tool", "data", "prompt", "policy", "unknown"] = "unknown"
    confidence = 0.5
    retryable = False
    
    # Check error code first (highest confidence)
    if error_code:
        for prefix, cause in CODE_ROOT_CAUSE.items():
            if error_code.startswith(prefix):
                root_cause = cause  # type: ignore
                confidence = 0.95
                retryable = False  # Code-based failures are policy
                break
    
    # Check patterns
    if root_cause == "unknown":
        for pattern, (cause, conf, retry) in ATTRIBUTION_PATTERNS.items():
            if pattern in msg_lower:
                root_cause = cause  # type: ignore
                confidence = conf
                retryable = retry
                break
    
    # Determine stage
    stage = determine_stage(agent_name, tool_name)
    if stage == "unknown":
        stage = "execute"  # Default fallback
        confidence = min(confidence, 0.6)  # Reduce confidence
    
    # Determine originating agent
    originating_agent = agent_name or STAGE_AGENTS.get(stage, "unknown")
    
    # Validate confidence threshold
    if confidence < MIN_ATTRIBUTION_CONFIDENCE:
        raise LowConfidenceAttributionError(
            f"# Execution Aborted\n"
            f"Code: DTL-FAILATTR-002\n"
            f"Reason: Attribution confidence ({confidence:.2f}) below threshold ({MIN_ATTRIBUTION_CONFIDENCE})"
        )
    
    return FailureAttribution(
        failure_class=failure_class or root_cause,
        originating_agent=originating_agent,
        tool_name=tool_name,
        stage=stage,
        root_cause=root_cause,
        retryable=retryable,
        confidence=confidence,
    )


def is_retryable(attribution: FailureAttribution) -> bool:
    """Check if failure is retryable based on attribution."""
    return attribution.retryable and attribution.root_cause in ("tool", "data")


def get_attribution_for_ledger(attribution: FailureAttribution) -> Dict:
    """Format attribution for run ledger entry."""
    return {
        "failure_class": attribution.failure_class,
        "originating_agent": attribution.originating_agent,
        "tool_name": attribution.tool_name,
        "stage": attribution.stage,
        "root_cause": attribution.root_cause,
        "retryable": attribution.retryable,
        "confidence": attribution.confidence,
    }
