"""
Adaptation Engine (DTL-SKILL-ADAPT v1).

Mid-run adaptation when execution deviates.
Detects repeated failures and step timeout drift.
Never mutates identity.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
from datetime import datetime, timezone


class AdaptationAbortError(Exception):
    """Raised when adaptation results in abort."""
    pass


@dataclass
class ExecutionMetrics:
    """Metrics for a running execution."""
    step_count: int = 0
    failure_count: int = 0
    failures_by_attribution: Dict[str, int] = field(default_factory=dict)
    step_durations_ms: List[int] = field(default_factory=list)
    expected_duration_ms: int = 5000
    start_time: Optional[datetime] = None


@dataclass(frozen=True)
class AdaptationDecision:
    """Decision from adaptation engine."""
    action: Literal["continue", "replan", "switch_skill", "abort"]
    reason: str
    new_skill: Optional[str] = None


# Thresholds
MAX_REPEATED_FAILURES = 3
TIMEOUT_DRIFT_THRESHOLD = 2.0  # 2x expected duration


def detect_repeated_failures(metrics: ExecutionMetrics) -> Optional[str]:
    """
    Detect repeated failures with same attribution.
    
    Returns:
        Attribution key if repeated, None otherwise
    """
    for attr, count in metrics.failures_by_attribution.items():
        if count >= MAX_REPEATED_FAILURES:
            return attr
    return None


def detect_timeout_drift(metrics: ExecutionMetrics) -> bool:
    """
    Detect if step durations are drifting.
    
    Returns:
        True if significant drift detected
    """
    if len(metrics.step_durations_ms) < 2:
        return False
    
    avg_duration = sum(metrics.step_durations_ms) / len(metrics.step_durations_ms)
    threshold = metrics.expected_duration_ms * TIMEOUT_DRIFT_THRESHOLD
    
    return avg_duration > threshold


def record_failure(
    metrics: ExecutionMetrics,
    attribution_key: str,
) -> ExecutionMetrics:
    """Record a failure in metrics."""
    metrics.failure_count += 1
    metrics.failures_by_attribution[attribution_key] = (
        metrics.failures_by_attribution.get(attribution_key, 0) + 1
    )
    return metrics


def record_step(
    metrics: ExecutionMetrics,
    duration_ms: int,
) -> ExecutionMetrics:
    """Record a step completion in metrics."""
    metrics.step_count += 1
    metrics.step_durations_ms.append(duration_ms)
    return metrics


def adapt(
    metrics: ExecutionMetrics,
    available_skills: List[str],
    current_skill: Optional[str] = None,
) -> AdaptationDecision:
    """
    Decide adaptation based on execution metrics.
    
    Allowed actions:
    - continue: No adaptation needed
    - replan: Re-plan current task
    - switch_skill: Switch to different skill
    - abort: Abort execution
    
    Never mutates identity.
    """
    # Check for repeated failures
    repeated_attr = detect_repeated_failures(metrics)
    if repeated_attr:
        # Try switching skills
        for skill in available_skills:
            if skill != current_skill:
                return AdaptationDecision(
                    action="switch_skill",
                    reason=f"Repeated failures ({repeated_attr}): switching skill",
                    new_skill=skill,
                )
        
        # No alternative skills - abort
        return AdaptationDecision(
            action="abort",
            reason=f"Repeated failures ({repeated_attr}): no alternative skills",
        )
    
    # Check for timeout drift
    if detect_timeout_drift(metrics):
        # Try replanning
        if metrics.step_count < 5:  # Early in execution
            return AdaptationDecision(
                action="replan",
                reason="Timeout drift detected: replanning",
            )
        else:
            # Late in execution - abort
            return AdaptationDecision(
                action="abort",
                reason="Timeout drift detected: too late to replan",
            )
    
    return AdaptationDecision(
        action="continue",
        reason="No adaptation needed",
    )


def apply_adaptation(
    decision: AdaptationDecision,
) -> None:
    """
    Apply an adaptation decision.
    
    Raises:
        AdaptationAbortError: If decision is abort
    """
    if decision.action == "abort":
        raise AdaptationAbortError(
            f"# Execution Aborted\n"
            f"Code: DTL-ADAPT-001\n"
            f"Reason: {decision.reason}"
        )
