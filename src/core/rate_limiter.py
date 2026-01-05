"""
API Rate Limiter with exponential backoff.

Provides centralized rate limiting for API calls to prevent 429 errors
and implement graceful backoff when limits are exceeded.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict


@dataclass
class RateLimitState:
    """State for a single API key."""
    request_count: int = 0
    window_start: float = 0.0
    backoff_until: float = 0.0
    consecutive_429s: int = 0


class RateLimiter:
    """
    Thread-safe rate limiter with per-key tracking.
    
    Features:
    - Sliding window rate limiting (requests per minute)
    - Exponential backoff on 429 errors
    - Thread-safe for concurrent access
    """
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute per key
        """
        self.rpm = requests_per_minute
        self._state: Dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._lock = Lock()
    
    def acquire(self, api_key: str) -> bool:
        """
        Request permission to make an API call.
        
        Args:
            api_key: The API key identifier
            
        Returns:
            True if the request is allowed, False if rate limited
        """
        with self._lock:
            now = time.time()
            state = self._state[api_key]
            
            # Check if we're in backoff period
            if now < state.backoff_until:
                remaining = state.backoff_until - now
                print(f"Rate limit backoff: {remaining:.1f}s remaining")
                return False
            
            # Reset window if expired (1 minute window)
            if now - state.window_start > 60:
                state.request_count = 0
                state.window_start = now
                state.consecutive_429s = 0  # Reset on new window
            
            # Check if we've exceeded the limit
            if state.request_count >= self.rpm:
                return False
            
            # Allow the request
            state.request_count += 1
            return True
    
    def wait_if_needed(self, api_key: str, timeout: float = 60.0) -> bool:
        """
        Wait until rate limit allows a request, or timeout.
        
        Args:
            api_key: The API key identifier
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if request is now allowed, False if timed out
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.acquire(api_key):
                return True
            time.sleep(0.5)
        return False
    
    def report_429(self, api_key: str):
        """
        Report a 429 error, triggering exponential backoff.
        
        Args:
            api_key: The API key that received the 429
        """
        with self._lock:
            state = self._state[api_key]
            state.consecutive_429s += 1
            
            # Exponential backoff: 2^n seconds, capped at 60
            backoff_seconds = min(60, 2 ** state.consecutive_429s)
            state.backoff_until = time.time() + backoff_seconds
            
            print(f"Rate limit 429 received. Backoff for {backoff_seconds}s")
    
    def get_stats(self, api_key: str) -> dict:
        """Get rate limit statistics for an API key."""
        with self._lock:
            state = self._state[api_key]
            now = time.time()
            
            return {
                "requests_this_minute": state.request_count,
                "limit": self.rpm,
                "in_backoff": now < state.backoff_until,
                "backoff_remaining": max(0, state.backoff_until - now),
                "consecutive_429s": state.consecutive_429s,
            }


# Singleton instance
_limiter = RateLimiter(requests_per_minute=60)


def acquire_rate_limit(api_key: str = "default") -> bool:
    """
    Check if an API call is allowed under rate limits.
    
    Args:
        api_key: API key identifier (defaults to "default")
        
    Returns:
        True if allowed, False if rate limited
    """
    return _limiter.acquire(api_key)


def wait_for_rate_limit(api_key: str = "default", timeout: float = 60.0) -> bool:
    """
    Wait until rate limit allows a request.
    
    Args:
        api_key: API key identifier
        timeout: Maximum wait time in seconds
        
    Returns:
        True if request allowed, False if timed out
    """
    return _limiter.wait_if_needed(api_key, timeout)


def report_rate_limit_exceeded(api_key: str = "default"):
    """
    Report a 429 error to trigger backoff.
    
    Args:
        api_key: API key that received the 429
    """
    _limiter.report_429(api_key)


def get_rate_limit_stats(api_key: str = "default") -> dict:
    """
    Get current rate limit statistics.
    
    Args:
        api_key: API key to check
        
    Returns:
        Dict with current stats
    """
    return _limiter.get_stats(api_key)
