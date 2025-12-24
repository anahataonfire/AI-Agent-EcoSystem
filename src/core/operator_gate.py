"""
Human Override Gate (Prompt AJ).

Allows explicit operator override of reuse denial, kill-switch, and fallback abort.
Overrides require signed tokens and are logged to the Run Ledger.
Overrides NEVER mutate identity.
"""

import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.core.run_ledger import log_event, EVENT_OPERATOR_OVERRIDE


class InvalidOverrideTokenError(Exception):
    """Raised when override token is invalid or missing."""
    pass


class OverrideIdentityMutationError(Exception):
    """Raised when an override attempts to mutate identity."""
    pass


# Override types
OVERRIDE_REUSE_DENIAL = "reuse_denial"
OVERRIDE_KILL_SWITCH = "kill_switch"
OVERRIDE_FALLBACK_ABORT = "fallback_abort"

VALID_OVERRIDE_TYPES = {
    OVERRIDE_REUSE_DENIAL,
    OVERRIDE_KILL_SWITCH,
    OVERRIDE_FALLBACK_ABORT,
}

# Secret key for token signing (in production, load from environment)
_OVERRIDE_SECRET_KEY = os.environ.get("DTL_OVERRIDE_SECRET", "default-dev-secret-key")


def generate_override_token(
    override_type: str,
    reason: str,
    operator_id: str,
) -> str:
    """
    Generate a signed override token.
    
    Args:
        override_type: Type of override (reuse_denial, kill_switch, etc.)
        reason: Reason for the override
        operator_id: ID of the operator
        
    Returns:
        Signed token string
    """
    if override_type not in VALID_OVERRIDE_TYPES:
        raise ValueError(f"Invalid override type: {override_type}")
    
    timestamp = datetime.now(timezone.utc).isoformat()
    # Use | as delimiter to avoid conflicts with timestamp colons
    payload = f"{override_type}|{operator_id}|{reason}|{timestamp}"
    
    signature = hmac.new(
        _OVERRIDE_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    
    return f"{payload}::{signature}"


def validate_override_token(token: str) -> Tuple[bool, Dict[str, str]]:
    """
    Validate an override token.
    
    Args:
        token: The token to validate
        
    Returns:
        Tuple of (is_valid, parsed_data)
    """
    try:
        parts = token.split("::")
        if len(parts) != 2:
            return (False, {})
        
        payload, signature = parts
        # Use | as delimiter
        payload_parts = payload.split("|")
        
        if len(payload_parts) != 4:
            return (False, {})
        
        override_type, operator_id, reason, timestamp = payload_parts
        
        # Verify signature
        expected_signature = hmac.new(
            _OVERRIDE_SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        if not hmac.compare_digest(signature, expected_signature):
            return (False, {})
        
        return (True, {
            "override_type": override_type,
            "operator_id": operator_id,
            "reason": reason,
            "timestamp": timestamp,
        })
    except Exception:
        return (False, {})


def apply_override(
    token: str,
    mutates_identity: bool = False,
) -> Dict[str, Any]:
    """
    Apply an operator override.
    
    Args:
        token: Signed override token
        mutates_identity: Whether this override would mutate identity
        
    Returns:
        Override result with logged details
        
    Raises:
        InvalidOverrideTokenError: If token is invalid
        OverrideIdentityMutationError: If override attempts identity mutation
    """
    # Validate token
    is_valid, data = validate_override_token(token)
    if not is_valid:
        raise InvalidOverrideTokenError("Override requires valid signed token")
    
    # Block identity mutations
    if mutates_identity:
        raise OverrideIdentityMutationError(
            "Operator overrides NEVER mutate identity"
        )
    
    # Log to run ledger
    log_event(
        event=EVENT_OPERATOR_OVERRIDE,
        actor=f"operator:{data['operator_id']}",
        payload={
            "override_type": data["override_type"],
            "reason": data["reason"],
            "token_timestamp": data["timestamp"],
        }
    )
    
    return {
        "override_applied": True,
        "override_type": data["override_type"],
        "reason": data["reason"],
        "operator_id": data["operator_id"],
    }


def build_override_footer(reason: str) -> str:
    """Build footer addition for operator override."""
    return f"Operator Override: YES\nOverride Reason: {reason}"


def check_override_allowed(override_type: str) -> bool:
    """Check if a specific override type is allowed."""
    return override_type in VALID_OVERRIDE_TYPES
