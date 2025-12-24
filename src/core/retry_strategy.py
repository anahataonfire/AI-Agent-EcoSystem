"""
Retry Strategy Selection (DTL-SKILL-RETRY v1).

Bounded, deterministic retry selection with cost caps,
failure classification, and tool switching.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
from enum import Enum

from src.core.failures import DTLFailure, AGENT_001


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


class CostCapExceededError(Exception):
    """Raised when retry cost cap is exceeded."""
    pass


# ============================================================================
# FAILURE CLASSIFICATION
# ============================================================================

class FailureClass(Enum):
    """Classification of failure types for retry decisions."""
    TRANSIENT = "transient"      # Network, timeout - retryable
    RATE_LIMIT = "rate_limit"    # API throttling - retryable with backoff
    DATA_INVALID = "data_invalid"  # Bad input - not retryable
    POLICY = "policy"            # Kill switch, red-line - not retryable
    TOOL_ERROR = "tool_error"    # Tool failure - try alternate tool
    UNKNOWN = "unknown"          # Cannot classify - limited retries


# Retryable failure classes
RETRYABLE_FAILURES = {
    FailureClass.TRANSIENT,
    FailureClass.RATE_LIMIT,
    FailureClass.TOOL_ERROR,
}

# Max retries per failure class
MAX_RETRIES_BY_CLASS: Dict[FailureClass, int] = {
    FailureClass.TRANSIENT: 3,
    FailureClass.RATE_LIMIT: 2,
    FailureClass.DATA_INVALID: 0,
    FailureClass.POLICY: 0,
    FailureClass.TOOL_ERROR: 2,
    FailureClass.UNKNOWN: 1,
}


# ============================================================================
# RETRY STRATEGY
# ============================================================================

@dataclass(frozen=True)
class RetryDecision:
    """Immutable retry decision."""
    should_retry: bool
    reason: str
    attempt_number: int
    max_attempts: int
    delay_ms: int
    alternate_tool: Optional[str]
    cost_units: int


@dataclass
class RetryState:
    """Mutable retry state tracker."""
    attempts: int = 0
    total_cost: int = 0
    tools_tried: List[str] = field(default_factory=list)
    failure_classes_seen: List[FailureClass] = field(default_factory=list)


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_total_retries: int = 5
    max_cost_units: int = 100
    base_delay_ms: int = 500
    max_delay_ms: int = 10000
    backoff_multiplier: float = 2.0


# Tool fallback chains
TOOL_FALLBACKS: Dict[str, List[str]] = {
    "DataFetchRSS": ["DataFetchAPI", "BrowserSearch"],
    "DataFetchAPI": ["BrowserSearch"],
    "BrowserSearch": [],
}


def classify_failure(
    error_message: str,
    error_code: Optional[str] = None,
    tool_name: Optional[str] = None,
) -> FailureClass:
    """
    Classify a failure for retry decision.
    
    This is deterministic based on error patterns.
    """
    msg_lower = error_message.lower()
    
    # Policy failures - never retry
    if error_code and error_code.startswith("DTL-"):
        if "REUSE" in error_code or "GRND" in error_code or "SEC" in error_code:
            return FailureClass.POLICY
    
    # Rate limiting patterns
    if any(p in msg_lower for p in ["rate limit", "429", "too many requests", "throttl"]):
        return FailureClass.RATE_LIMIT
    
    # Transient patterns
    if any(p in msg_lower for p in ["timeout", "connection", "network", "temporarily unavailable", "503", "502"]):
        return FailureClass.TRANSIENT
    
    # Data validation
    if any(p in msg_lower for p in ["invalid", "malformed", "missing required", "validation failed"]):
        return FailureClass.DATA_INVALID
    
    # Tool-specific errors
    if tool_name and any(p in msg_lower for p in ["tool error", "tool failed", "execution failed"]):
        return FailureClass.TOOL_ERROR
    
    return FailureClass.UNKNOWN


def compute_retry_delay(
    attempt: int,
    failure_class: FailureClass,
    config: RetryConfig,
) -> int:
    """
    Compute delay before retry in milliseconds.
    
    Uses exponential backoff with jitter-free determinism.
    """
    base = config.base_delay_ms
    
    # Rate limits get longer delays
    if failure_class == FailureClass.RATE_LIMIT:
        base = config.base_delay_ms * 4
    
    delay = int(base * (config.backoff_multiplier ** attempt))
    return min(delay, config.max_delay_ms)


def compute_retry_cost(
    attempt: int,
    failure_class: FailureClass,
) -> int:
    """
    Compute cost units for a retry attempt.
    
    Higher cost for more expensive operations.
    """
    base_cost = 10
    
    # Tool switching is more expensive
    if failure_class == FailureClass.TOOL_ERROR:
        base_cost = 20
    
    # Later attempts cost more
    return base_cost * (attempt + 1)


def get_alternate_tool(
    current_tool: str,
    tools_tried: List[str],
) -> Optional[str]:
    """
    Get alternate tool from fallback chain.
    
    Returns None if no alternates available.
    """
    fallbacks = TOOL_FALLBACKS.get(current_tool, [])
    
    for fallback in fallbacks:
        if fallback not in tools_tried:
            return fallback
    
    return None


def decide_retry(
    failure_class: FailureClass,
    state: RetryState,
    config: RetryConfig,
    current_tool: Optional[str] = None,
) -> RetryDecision:
    """
    Decide whether and how to retry.
    
    Returns an immutable RetryDecision.
    """
    max_for_class = MAX_RETRIES_BY_CLASS.get(failure_class, 0)
    
    # Count attempts for this failure class
    class_attempts = sum(
        1 for fc in state.failure_classes_seen
        if fc == failure_class
    )
    
    # Check if failure class is retryable
    if failure_class not in RETRYABLE_FAILURES:
        return RetryDecision(
            should_retry=False,
            reason=f"Failure class {failure_class.value} is not retryable",
            attempt_number=state.attempts,
            max_attempts=max_for_class,
            delay_ms=0,
            alternate_tool=None,
            cost_units=0,
        )
    
    # Check total retry cap
    if state.attempts >= config.max_total_retries:
        return RetryDecision(
            should_retry=False,
            reason=f"Total retry cap ({config.max_total_retries}) exceeded",
            attempt_number=state.attempts,
            max_attempts=config.max_total_retries,
            delay_ms=0,
            alternate_tool=None,
            cost_units=0,
        )
    
    # Check class-specific retry cap
    if class_attempts >= max_for_class:
        return RetryDecision(
            should_retry=False,
            reason=f"Class retry cap ({max_for_class}) exceeded for {failure_class.value}",
            attempt_number=class_attempts,
            max_attempts=max_for_class,
            delay_ms=0,
            alternate_tool=None,
            cost_units=0,
        )
    
    # Compute cost
    cost = compute_retry_cost(state.attempts, failure_class)
    
    # Check cost cap
    if state.total_cost + cost > config.max_cost_units:
        return RetryDecision(
            should_retry=False,
            reason=f"Cost cap ({config.max_cost_units}) would be exceeded",
            attempt_number=state.attempts,
            max_attempts=config.max_total_retries,
            delay_ms=0,
            alternate_tool=None,
            cost_units=0,
        )
    
    # Get alternate tool if applicable
    alternate_tool = None
    if failure_class == FailureClass.TOOL_ERROR and current_tool:
        alternate_tool = get_alternate_tool(current_tool, state.tools_tried)
    
    delay = compute_retry_delay(state.attempts, failure_class, config)
    
    return RetryDecision(
        should_retry=True,
        reason=f"Retry permitted for {failure_class.value}",
        attempt_number=state.attempts + 1,
        max_attempts=max_for_class,
        delay_ms=delay,
        alternate_tool=alternate_tool,
        cost_units=cost,
    )


def apply_retry_decision(
    decision: RetryDecision,
    state: RetryState,
    failure_class: FailureClass,
    tool_name: Optional[str] = None,
) -> RetryState:
    """
    Apply a retry decision to update state.
    
    Returns updated state (mutates in place for efficiency).
    """
    if decision.should_retry:
        state.attempts += 1
        state.total_cost += decision.cost_units
        state.failure_classes_seen.append(failure_class)
        
        if tool_name and tool_name not in state.tools_tried:
            state.tools_tried.append(tool_name)
        
        if decision.alternate_tool:
            state.tools_tried.append(decision.alternate_tool)
    
    return state
