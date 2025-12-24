"""
Feed Trust Scoring & Degradation System (Prompt Z).

Provides deterministic feed trust scoring with automatic degradation.
Trust is stored outside Identity Store for security isolation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple


# ============================================================================
# TRUST MODEL CONFIGURATION
# ============================================================================

INITIAL_TRUST_SCORE = 1.0

# Degradation penalties
PENALTY_MALICIOUS_PAYLOAD = 0.4
PENALTY_INJECTION_ATTEMPT = 0.3
PENALTY_EMPTY_PAYLOAD = 0.2
PENALTY_DUPLICATE_PAYLOAD = 0.2

# Behavior thresholds
THRESHOLD_NORMAL = 0.7       # >= 0.7: Normal operation
THRESHOLD_LIMITED = 0.4     # 0.4–0.69: Limited (max 3 items)
# < 0.4: Feed disabled

MAX_ITEMS_LIMITED = 3


class FeedTrustStore:
    """
    Persistent store for feed trust scores.
    
    Stored separately from Identity Store to prevent cross-contamination.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            project_root = Path(__file__).parent.parent.parent
            storage_path = str(project_root / "data" / "feed_trust.json")
        
        self.storage_path = Path(storage_path)
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._write_store({})
    
    def _read_store(self) -> Dict[str, dict]:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _write_store(self, data: Dict[str, dict]) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_trust_score(self, feed_url: str) -> float:
        """Get the trust score for a feed. Returns INITIAL_TRUST_SCORE if not found."""
        store = self._read_store()
        entry = store.get(feed_url, {})
        return entry.get("trust_score", INITIAL_TRUST_SCORE)
    
    def get_trust_entry(self, feed_url: str) -> Optional[dict]:
        """Get full trust entry for a feed."""
        store = self._read_store()
        return store.get(feed_url)
    
    def update_trust_score(self, feed_url: str, new_score: float, reason: str) -> None:
        """Update the trust score for a feed."""
        store = self._read_store()
        
        if feed_url not in store:
            store[feed_url] = {
                "trust_score": INITIAL_TRUST_SCORE,
                "history": []
            }
        
        old_score = store[feed_url]["trust_score"]
        store[feed_url]["trust_score"] = max(0.0, min(1.0, new_score))  # Clamp to [0, 1]
        store[feed_url]["last_updated"] = datetime.now(timezone.utc).isoformat()
        store[feed_url]["history"].append({
            "old_score": old_score,
            "new_score": new_score,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep only last 10 history entries
        store[feed_url]["history"] = store[feed_url]["history"][-10:]
        
        self._write_store(store)
    
    def apply_penalty(self, feed_url: str, penalty: float, reason: str) -> float:
        """Apply a penalty to a feed's trust score. Returns new score."""
        current = self.get_trust_score(feed_url)
        new_score = current - penalty
        self.update_trust_score(feed_url, new_score, reason)
        return new_score


def get_feed_behavior(feed_url: str, trust_store: Optional[FeedTrustStore] = None) -> Tuple[str, int]:
    """
    Determine feed behavior based on trust score.
    
    Returns:
        Tuple of (behavior, max_items)
        - behavior: "normal", "limited", or "disabled"
        - max_items: Maximum items to fetch (0 if disabled)
    """
    if trust_store is None:
        trust_store = FeedTrustStore()
    
    score = trust_store.get_trust_score(feed_url)
    
    if score >= THRESHOLD_NORMAL:
        return ("normal", -1)  # -1 means no limit
    elif score >= THRESHOLD_LIMITED:
        return ("limited", MAX_ITEMS_LIMITED)
    else:
        return ("disabled", 0)


def check_feed_allowed(feed_url: str, trust_store: Optional[FeedTrustStore] = None) -> Tuple[bool, str]:
    """
    Check if a feed is allowed to be fetched.
    
    Returns:
        Tuple of (is_allowed, reason)
    """
    behavior, max_items = get_feed_behavior(feed_url, trust_store)
    
    if behavior == "disabled":
        if trust_store is None:
            trust_store = FeedTrustStore()
        score = trust_store.get_trust_score(feed_url)
        return (False, f"Feed disabled due to low trust score ({score:.2f})")
    
    return (True, f"Feed allowed ({behavior})")


def record_malicious_payload(feed_url: str, trust_store: Optional[FeedTrustStore] = None) -> float:
    """Record a malicious payload detection event."""
    if trust_store is None:
        trust_store = FeedTrustStore()
    return trust_store.apply_penalty(feed_url, PENALTY_MALICIOUS_PAYLOAD, "malicious_payload_detected")


def record_injection_attempt(feed_url: str, trust_store: Optional[FeedTrustStore] = None) -> float:
    """Record an injection attempt event."""
    if trust_store is None:
        trust_store = FeedTrustStore()
    return trust_store.apply_penalty(feed_url, PENALTY_INJECTION_ATTEMPT, "injection_attempt")


def record_empty_payload(feed_url: str, trust_store: Optional[FeedTrustStore] = None) -> float:
    """Record an empty payload event."""
    if trust_store is None:
        trust_store = FeedTrustStore()
    return trust_store.apply_penalty(feed_url, PENALTY_EMPTY_PAYLOAD, "empty_payload")


def record_duplicate_payload(feed_url: str, trust_store: Optional[FeedTrustStore] = None) -> float:
    """Record a duplicate payload event."""
    if trust_store is None:
        trust_store = FeedTrustStore()
    return trust_store.apply_penalty(feed_url, PENALTY_DUPLICATE_PAYLOAD, "duplicate_payload")
