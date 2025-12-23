"""
Sanitizer middleware node for the LangGraph pipeline.

This module validates and sanitizes proposed actions before execution:
- Parses current_plan into ProposedAction
- Validates URLs against allowlist
- Detects infinite loops via fingerprint comparison
- Enforces budget constraints
"""

import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage

from src.core.schemas import ProposedAction
from src.graph.state import RunState


# Allowlist of permitted RSS feed URL prefixes
ALLOWLIST = [
    "https://rss.nytimes.com",
    "https://feeds.bbci.co.uk",
    "https://feeds.reuters.com",
    "https://techcrunch.com",
    "https://www.reddit.com/r/",
    "https://www.reddit.com/search",
    "https://news.google.com/rss",
]

# Allowed URL shortcuts (resolved by rss_fetcher)
ALLOWED_SHORTCUTS = ["google_news", "reddit_search"]

# Budget constraints
MAX_ITEMS_LIMIT = 25
MAX_TIMEOUT_SEC = 30


def is_url_allowed(url: str) -> bool:
    """Check if a URL matches any prefix in the allowlist or is an allowed shortcut."""
    if not url or not isinstance(url, str):
        return False
    # Check shortcuts first
    if url in ALLOWED_SHORTCUTS:
        return True
    return any(url.startswith(prefix) for prefix in ALLOWLIST)


def is_valid_url_format(url: str) -> bool:
    """Validate URL format (HTTPS only, no private IPs)."""
    if not url:
        return False
    
    # Must be HTTPS
    if not url.startswith("https://"):
        return False
    
    # Basic URL pattern
    pattern = r'^https://[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+(/.*)?$'
    return bool(re.match(pattern, url))


def validate_params(params: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate action parameters against budget constraints.
    
    Returns:
        (is_valid, error_message)
    """
    # Check max_items
    max_items = params.get("max_items", 10)
    if isinstance(max_items, int) and max_items > MAX_ITEMS_LIMIT:
        return False, f"max_items ({max_items}) exceeds limit ({MAX_ITEMS_LIMIT})"
    
    # Check timeout
    timeout = params.get("timeout_sec", 10)
    if isinstance(timeout, int) and timeout > MAX_TIMEOUT_SEC:
        return False, f"timeout_sec ({timeout}) exceeds limit ({MAX_TIMEOUT_SEC})"
    
    return True, ""


def sanitizer_node(state: RunState) -> Dict[str, Any]:
    """
    Sanitize and validate the current plan before execution.
    
    This node:
    1. Parses state.current_plan into a ProposedAction
    2. Validates URLs for DataFetchRSS actions
    3. Checks for infinite loops via plan fingerprint
    4. Enforces budget constraints
    
    Args:
        state: Current RunState with current_plan
        
    Returns:
        State update dict with either:
        - approved_action: The validated ProposedAction
        - messages: Rejection message if validation fails
    """
    # No plan to validate
    if not state.current_plan:
        return {
            "messages": [HumanMessage(
                content="No plan provided to sanitize."
            )]
        }
    
    # Step 1: Parse into ProposedAction
    try:
        action = ProposedAction(**state.current_plan)
    except Exception as e:
        return {
            "messages": [HumanMessage(
                content=f"Failed to parse plan into ProposedAction: {e}"
            )],
            "current_plan": None,
        }
    
    # Step 2: Loop detection - compare fingerprints
    current_fingerprint = action.plan_fingerprint
    previous_fingerprint = state.circuit_breaker.plan_fingerprint
    
    if current_fingerprint and current_fingerprint == previous_fingerprint:
        # Increment retry count for loop detection
        new_cb = state.circuit_breaker.increment_retry()
        
        if new_cb.should_trip():
            return {
                "messages": [HumanMessage(
                    content=f"Circuit breaker tripped: identical plan detected "
                            f"({new_cb.retry_count} retries). Stopping to prevent infinite loop."
                )],
                "circuit_breaker": new_cb,
                "current_plan": None,
            }
        
        return {
            "messages": [HumanMessage(
                content=f"Warning: Identical plan fingerprint detected "
                        f"(retry {new_cb.retry_count}/{new_cb.max_retries}). "
                        f"Please provide a different approach."
            )],
            "circuit_breaker": new_cb,
        }
    
    # Step 3: URL allowlist check for DataFetchRSS
    if action.tool_name == "DataFetchRSS":
        url = action.params.get("url", "")
        
        # Skip format validation for allowed shortcuts
        if url not in ALLOWED_SHORTCUTS:
            # Validate URL format
            if not is_valid_url_format(url):
                return {
                    "messages": [HumanMessage(
                        content=f"Invalid URL format: {url}. Must be HTTPS with valid domain."
                    )],
                    "current_plan": None,
                }
        
        # Check allowlist (includes shortcuts)
        if not is_url_allowed(url):
            allowed_str = ", ".join(ALLOWLIST + ALLOWED_SHORTCUTS)
            return {
                "messages": [HumanMessage(
                    content=f"URL not in allowlist: {url}\n"
                            f"Allowed: {allowed_str}"
                )],
                "current_plan": None,
            }
    # Step 4: Zero-Trust Validation for CompleteTask
    if action.tool_name == "CompleteTask":
        source_ids = action.params.get("source_ids", [])
        if not isinstance(source_ids, list):
             # Let normal schema validation handle this, or reject here
             pass
        else:
            # Check against evidence_map
            phantom_ids = [sid for sid in source_ids if sid not in state.evidence_map]
            if phantom_ids:
                # Update telemetry
                telemetry = dict(state.telemetry)
                telemetry["sanitizer_reject_count"] = telemetry.get("sanitizer_reject_count", 0) + 1
                
                return {
                    "messages": [HumanMessage(
                        content=f"REJECTED: Phantom Source IDs detected: {phantom_ids}. "
                                f"You cited evidence IDs that do not exist in the state. "
                                f"Only use IDs from the 'Evidence collected' messages."
                    )],
                    "telemetry": telemetry,
                    "current_plan": None,
                }

    # Step 5: Validate params against budget constraints
    is_valid, error_msg = validate_params(action.params)
    if not is_valid:
        return {
            "messages": [HumanMessage(
                content=f"Parameter validation failed: {error_msg}"
            )],
            "current_plan": None,
        }
    
    # All checks passed - approve the action
    # Update circuit breaker with new fingerprint and increment step
    new_cb = state.circuit_breaker.model_copy(update={
        "plan_fingerprint": current_fingerprint,
        "step_count": state.circuit_breaker.step_count + 1,
        "retry_count": 0,  # Reset retries on successful validation
    })
    
    return {
        "messages": [HumanMessage(
            content=f"✓ Plan approved: {action.tool_name} with params {action.params}"
        )],
        "approved_action": action.model_dump(),
        "circuit_breaker": new_cb,
    }
